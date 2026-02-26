import json
import re
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_secret
from app.models.models import Comment, Post, Reply, SocialAccount

GRAPH_BASE = "https://graph.facebook.com/v22.0"


@dataclass
class Classification:
    intent: str
    risk: str
    confidence: float


def classify_comment(text: str) -> Classification:
    t = (text or "").lower()
    if any(x in t for x in ["mierda", "estafa", "denuncia", "demand", "fraude"]):
        return Classification(intent="complaint", risk="high", confidence=0.9)
    if any(x in t for x in ["precio", "cuánto", "reserva", "disponibilidad", "book"]):
        return Classification(intent="lead", risk="low", confidence=0.86)
    if re.search(r"http[s]?://|gratis|crypto|dm me", t):
        return Classification(intent="spam", risk="high", confidence=0.92)
    return Classification(intent="general", risk="low", confidence=0.65)


def _openai_chat(api_key: str, prompt: str) -> str:
    with httpx.Client(timeout=20.0) as client:
        res = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a concise social media assistant. Reply in Spanish unless user wrote in English."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            },
        )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()


def _decide_and_generate(account: SocialAccount, post: Post, comment: Comment) -> tuple[bool, str, str]:
    """Returns: (should_reply, reply_text, reason)"""
    fallback_reply = f"¡Gracias por comentar! {comment.text[:120]}"

    if not account.openai_key_encrypted:
        # Without AI key, basic decision policy
        c = classify_comment(comment.text)
        if c.risk == "high":
            return False, "", "high_risk_without_ai"
        return True, fallback_reply, "heuristic"

    try:
        openai_key = decrypt_secret(account.openai_key_encrypted)
        prompt = (
            "Devuelve SOLO JSON válido con claves: should_reply (bool), reply (string), reason (string corto).\n"
            f"Persona/criterio de marca:\n{account.prompt_persona}\n\n"
            f"Caption del post:\n{post.caption or ''}\n\n"
            f"Comentario del usuario:\n{comment.text}\n\n"
            "Reglas:\n"
            "- Si es spam, ofensivo o irrelevante: should_reply=false.\n"
            "- Si requiere respuesta útil/comercial/reputacional: should_reply=true.\n"
            "- reply debe ser breve, natural y en tono de marca.\n"
        )
        raw = _openai_chat(openai_key, prompt)
        data = json.loads(raw)
        should_reply = bool(data.get("should_reply", False))
        reply = str(data.get("reply", "")).strip()
        reason = str(data.get("reason", "ai_decision")).strip()[:120]
        if should_reply and not reply:
            reply = fallback_reply
        return should_reply, reply, reason
    except Exception:
        c = classify_comment(comment.text)
        if c.risk == "high":
            return False, "", "high_risk_fallback"
        return True, fallback_reply, "fallback"


def _publish_reply_to_instagram(platform_comment_id: str, text: str, token: str) -> tuple[bool, str]:
    with httpx.Client(timeout=20.0) as client:
        res = client.post(
            f"{GRAPH_BASE}/{platform_comment_id}/replies",
            data={"message": text, "access_token": token},
        )
        if res.status_code != 200:
            return False, res.text
        return True, res.text


def generate_reply_for_comment(db: Session, comment_id: int, publish_immediately: bool = True) -> dict:
    comment = db.get(Comment, comment_id)
    if not comment:
        return {"ok": False, "reason": "comment_not_found"}

    post = db.get(Post, comment.post_id)
    if not post:
        return {"ok": False, "reason": "post_not_found"}

    account = db.get(SocialAccount, post.account_id)
    if not account:
        return {"ok": False, "reason": "account_not_found"}

    c = classify_comment(comment.text)
    if c.risk == "high":
        reply = Reply(comment_id=comment.id, text="Revisión humana requerida por riesgo.", status="escalated")
        db.add(reply)
        db.commit()
        return {"ok": True, "status": "escalated", "intent": c.intent, "risk": c.risk}

    should_reply, reply_text, decision_reason = _decide_and_generate(account, post, comment)
    if not should_reply:
        reply = Reply(comment_id=comment.id, text=f"[SKIPPED] {decision_reason}", status="skipped")
        db.add(reply)
        db.commit()
        return {"ok": True, "status": "skipped", "intent": c.intent, "risk": c.risk, "decision_reason": decision_reason}

    status = "draft"
    publish_detail = ""

    if publish_immediately:
        if not account.instagram_token_encrypted:
            status = "failed"
            publish_detail = "missing_instagram_token"
        else:
            try:
                token = decrypt_secret(account.instagram_token_encrypted)
                ok, detail = _publish_reply_to_instagram(comment.platform_comment_id, reply_text, token)
                status = "sent" if ok else "failed"
                publish_detail = detail[:500]
            except Exception as exc:
                status = "failed"
                publish_detail = str(exc)[:500]

    reply = Reply(comment_id=comment.id, text=reply_text, status=status)
    db.add(reply)
    db.commit()

    return {
        "ok": True,
        "status": status,
        "intent": c.intent,
        "risk": c.risk,
        "confidence": c.confidence,
        "publish_detail": publish_detail,
        "decision_reason": decision_reason,
    }

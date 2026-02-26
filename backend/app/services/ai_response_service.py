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
                "temperature": 0.4,
            },
        )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()


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

    reply_text = f"¡Gracias por comentar! {comment.text[:120]}"
    if account.openai_key_encrypted:
        try:
            openai_key = decrypt_secret(account.openai_key_encrypted)
            prompt = (
                f"Persona: {account.prompt_persona}\n"
                f"Post caption: {post.caption or ''}\n"
                f"Comentario: {comment.text}\n"
                f"Genera una respuesta breve, útil y natural."
            )
            reply_text = _openai_chat(openai_key, prompt)
        except Exception:
            pass

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
    }

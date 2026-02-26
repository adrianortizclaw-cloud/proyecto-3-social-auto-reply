from datetime import datetime
import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_secret
from app.models.models import SocialAccount, Post, Comment

GRAPH_BASE = "https://graph.facebook.com/v22.0"


def _to_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def sync_instagram(db: Session, account: SocialAccount) -> dict:
    if not account.instagram_token_encrypted:
        return {"ok": False, "reason": "missing_instagram_token"}

    try:
        token = decrypt_secret(account.instagram_token_encrypted)
    except Exception:
        return {"ok": False, "reason": "invalid_encrypted_token"}

    # account_handle can be either IG User ID or Facebook Page ID (numeric).
    candidate_id = account.account_handle.strip().lstrip("@")
    if not candidate_id.isdigit():
        return {
            "ok": False,
            "reason": "account_handle_must_be_numeric_id",
            "hint": "Use Instagram User ID or Facebook Page ID (numeric)",
        }

    ig_user_id = candidate_id

    created_posts = 0
    created_comments = 0

    with httpx.Client(timeout=20.0) as client:
        media_res = client.get(
            f"{GRAPH_BASE}/{ig_user_id}/media",
            params={
                "fields": "id,caption,timestamp,media_type",
                "limit": 10,
                "access_token": token,
            },
        )

        if media_res.status_code != 200:
            # Common case: candidate_id is a Facebook Page ID, not IG User ID.
            # Try resolving IG account from page and retry.
            retry_done = False
            try:
                page_res = client.get(
                    f"{GRAPH_BASE}/{candidate_id}",
                    params={"fields": "instagram_business_account", "access_token": token},
                )
                if page_res.status_code == 200:
                    page_data = page_res.json() or {}
                    ig_obj = page_data.get("instagram_business_account") or {}
                    resolved_ig_id = str(ig_obj.get("id") or "").strip()
                    if resolved_ig_id.isdigit():
                        ig_user_id = resolved_ig_id
                        media_res = client.get(
                            f"{GRAPH_BASE}/{ig_user_id}/media",
                            params={
                                "fields": "id,caption,timestamp,media_type",
                                "limit": 10,
                                "access_token": token,
                            },
                        )
                        retry_done = True
            except Exception:
                pass

            if media_res.status_code != 200:
                suffix = " (retried via page->ig resolution)" if retry_done else ""
                return {"ok": False, "reason": "graph_media_error", "detail": f"{media_res.text}{suffix}"}

        media_items = media_res.json().get("data", [])

        for item in media_items:
            media_id = str(item.get("id"))
            if not media_id:
                continue

            existing_post = (
                db.query(Post)
                .filter(Post.account_id == account.id, Post.platform_post_id == media_id)
                .first()
            )

            kind = "reel" if str(item.get("media_type", "")).upper() in {"REEL", "VIDEO"} else "post"
            caption = item.get("caption") or ""
            published_at = _to_datetime(item.get("timestamp"))

            if not existing_post:
                existing_post = Post(
                    account_id=account.id,
                    platform_post_id=media_id,
                    kind=kind,
                    caption=caption,
                    published_at=published_at,
                )
                db.add(existing_post)
                db.flush()
                created_posts += 1

            comments_res = client.get(
                f"{GRAPH_BASE}/{media_id}/comments",
                params={
                    "fields": "id,text,username,timestamp",
                    "limit": 25,
                    "access_token": token,
                },
            )

            if comments_res.status_code != 200:
                continue

            for c in comments_res.json().get("data", []):
                comment_id = str(c.get("id"))
                if not comment_id:
                    continue

                exists_comment = (
                    db.query(Comment)
                    .filter(Comment.post_id == existing_post.id, Comment.platform_comment_id == comment_id)
                    .first()
                )
                if exists_comment:
                    continue

                db.add(
                    Comment(
                        post_id=existing_post.id,
                        platform_comment_id=comment_id,
                        author_handle=c.get("username") or "unknown",
                        text=c.get("text") or "",
                        created_at=_to_datetime(c.get("timestamp")),
                    )
                )
                created_comments += 1

    db.commit()
    return {
        "ok": True,
        "created_posts": created_posts,
        "created_comments": created_comments,
        "media_seen": len(media_items),
    }

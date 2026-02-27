from datetime import datetime
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_secret
from app.models.models import SocialAccount, Post, Comment

logger = logging.getLogger(__name__)
INSTAGRAM_GRAPH_BASE = "https://graph.instagram.com"


def _to_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def _fetch_insights(client: httpx.Client, user_id: str, token: str) -> dict[str, Any]:
    try:
        res = client.get(
            f"{INSTAGRAM_GRAPH_BASE}/{user_id}/insights",
            params={
                "metric": "impressions,reach,profile_views,engagement,follower_count",
                "period": "day",
                "access_token": token,
            },
        )
        res.raise_for_status()
        data = res.json().get("data", [])
        return {item.get("name"): item.get("values", []) for item in data}
    except Exception as exc:  # noqa: BLE001
        logger.warning("unable to fetch instagram insights for %s: %s", user_id, exc)
        return {}


def _normalize_media_details(item: dict[str, Any], fetched_comments: int) -> dict[str, Any]:
    caption = (item.get("caption") or "").strip()
    return {
        "id": item.get("id"),
        "type": item.get("media_type"),
        "permalink": item.get("permalink"),
        "caption": caption[:160],
        "comment_count": int(item.get("comments_count") or 0),
        "comments_fetched": fetched_comments,
        "like_count": int(item.get("like_count") or 0),
        "media_url": item.get("media_url") or item.get("thumbnail_url"),
    }


def _normalize_story(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "permalink": item.get("permalink"),
        "media_type": item.get("media_type"),
        "timestamp": item.get("timestamp"),
        "caption": item.get("caption") or "",
        "media_url": item.get("media_url"),
    }





def _fetch_comments_for_media(client: httpx.Client, media_id: str, token: str, limit: int = 50, max_comments: int = 200) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    url = f"{INSTAGRAM_GRAPH_BASE}/{media_id}/comments"
    params = {
        "fields": "id,text,username,timestamp",
        "limit": limit,
        "filter": "stream",
        "order": "reverse_chronological",
        "access_token": token,
    }
    while url and len(comments) < max_comments:
        request_params = params if params else None
        try:
            res = client.get(url, params=request_params)
        except Exception as exc:
            logger.warning('comment fetch error for %s: %s', media_id, exc)
            break
        if res.status_code != 200:
            logger.warning('comments fetch failed for %s status=%s', media_id, res.status_code)
            break
        page = res.json() or {}
        batch = page.get('data', [])
        comments.extend(batch)
        paging = page.get('paging', {})
        url = paging.get('next')
        params = None
    return comments
def sync_instagram(db: Session, account: SocialAccount) -> dict[str, Any]:
    if not account.instagram_token_encrypted:
        return {"ok": False, "reason": "missing_instagram_token"}

    try:
        token = decrypt_secret(account.instagram_token_encrypted)
    except Exception:
        return {"ok": False, "reason": "invalid_encrypted_token"}

    ig_user_id = account.account_handle.strip().lstrip("@")
    if not ig_user_id.isdigit():
        return {
            "ok": False,
            "reason": "account_handle_must_be_numeric_id",
            "hint": "Use the Instagram Business Account ID",
        }

    created_posts = 0
    created_comments = 0
    story_count = 0
    reel_count = 0
    post_count = 0
    total_likes = 0
    media_items: list[dict[str, Any]] = []
    media_details: list[dict[str, Any]] = []
    stories_data: list[dict[str, Any]] = []
    insights_data: dict[str, Any] = {}

    with httpx.Client(timeout=20.0) as client:
        media_res = client.get(
            f"{INSTAGRAM_GRAPH_BASE}/{ig_user_id}/media",
            params={
                "fields": "id,caption,timestamp,media_type,like_count,comments_count,permalink,comments.limit(50){id,text,username,timestamp}",
                "limit": 10,
                "access_token": token,
            },
        )

        if media_res.status_code != 200:
            logger.error("media fetch failed %s %s", ig_user_id, media_res.text)
            return {
                "ok": False,
                "reason": "graph_media_error",
                "detail": media_res.text,
            }

        media_items = media_res.json().get("data", [])
        logger.debug("fetched %s media items for %s", len(media_items), ig_user_id)

        for item in media_items:
            media_id = str(item.get("id"))
            if not media_id:
                continue

            kind = (item.get("media_type") or "").upper()
            if kind in {"REEL", "VIDEO"}:
                reel_count += 1
            else:
                post_count += 1

            total_likes += int(item.get("like_count") or 0)

            existing_post = (
                db.query(Post)
                .filter(Post.account_id == account.id, Post.platform_post_id == media_id)
                .first()
            )

            caption = item.get("caption") or ""
            published_at = _to_datetime(item.get("timestamp"))

            if not existing_post:
                existing_post = Post(
                    account_id=account.id,
                    platform_post_id=media_id,
                    kind="reel" if kind in {"REEL", "VIDEO"} else "post",
                    caption=caption,
                    published_at=published_at,
                )
                db.add(existing_post)
                db.flush()
                created_posts += 1

            comment_count = int(item.get("comments_count") or 0)
            comments_data = []
            if comment_count > 0:
                comments_data = _fetch_comments_for_media(client, media_id, token)
            logger.debug("media=%s fetched %s comments", media_id, len(comments_data))

            for c in comments_data:
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

            media_details.append(_normalize_media_details(item, len(comments_data)))
        try:
            stories_res = client.get(
                f"{INSTAGRAM_GRAPH_BASE}/{ig_user_id}/stories",
                params={
                    "fields": "id,media_url,permalink,media_type,timestamp,caption",
                    "access_token": token,
                },
            )
            if stories_res.status_code == 200:
                for story in stories_res.json().get("data", []):
                    stories_data.append(_normalize_story(story))
        except Exception as exc:  # noqa: BLE001
            logger.warning("stories fetch failed for %s: %s", ig_user_id, exc)

        insights_data = _fetch_insights(client, ig_user_id, token)
        story_count = len(stories_data)

    summary = {
        "stories": story_count,
        "reels": reel_count,
        "posts": post_count,
        "total_likes": total_likes,
        "synced_comments": created_comments,
    }

    db.commit()
    return {
        "ok": True,
        "created_posts": created_posts,
        "created_comments": created_comments,
        "media_seen": len(media_items),
        "media_summary": summary,
        "insights": insights_data,
        "media_details": media_details,
        "stories": stories_data,
    }

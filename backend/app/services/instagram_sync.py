from datetime import datetime, timezone
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_secret
from app.models.models import Comment, OAuthConnection, Post, SocialAccount

logger = logging.getLogger(__name__)
INSTAGRAM_GRAPH_BASE = "https://graph.instagram.com"


def _to_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


def _normalize_media_details(item: dict[str, Any], fetched_comments: int, comment_error: str = "") -> dict[str, Any]:
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
        "comment_error": comment_error,
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


def _fetch_comments_for_media(
    client: httpx.Client,
    media_id: str,
    token: str,
    limit: int = 50,
    max_comments: int = 200,
) -> tuple[list[dict[str, Any]], str]:
    comments: list[dict[str, Any]] = []
    last_error = ""

    # Strategy A: direct comments edge
    url = f"{INSTAGRAM_GRAPH_BASE}/{media_id}/comments"
    params = {
        "fields": "id,text,username,timestamp,replies{id,text,username,timestamp}",
        "limit": limit,
        "access_token": token,
    }
    while url and len(comments) < max_comments:
        request_params = params if params else None
        try:
            res = client.get(url, params=request_params)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            break

        if res.status_code != 200:
            last_error = res.text[:260]
            break

        page = res.json() or {}
        batch = page.get("data", [])
        comments.extend(batch)
        paging = page.get("paging", {})
        url = paging.get("next")
        params = None

    if comments:
        return comments[:max_comments], ""

    # Strategy B: request media with embedded comments and replies
    try:
        res = client.get(
            f"{INSTAGRAM_GRAPH_BASE}/{media_id}",
            params={
                "fields": "comments_count,comments.limit(100){id,text,username,timestamp,replies{id,text,username,timestamp}}",
                "access_token": token,
            },
        )
        if res.status_code == 200:
            payload = res.json() or {}
            nested = (payload.get("comments") or {}).get("data", [])
            merged: list[dict[str, Any]] = []
            for c in nested:
                merged.append(c)
                replies = (c.get("replies") or {}).get("data", [])
                merged.extend(replies)
            if merged:
                return merged[:max_comments], ""
            if int(payload.get("comments_count") or 0) > 0:
                last_error = "comments_count>0 pero API devolvió data vacía"
        else:
            last_error = res.text[:260]
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)

    return [], last_error


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

    connection = db.query(OAuthConnection).filter(OAuthConnection.social_account_id == account.id).first()
    granted_scopes = set()
    if connection and connection.scopes:
        granted_scopes = {s.strip() for s in connection.scopes.split(",") if s.strip()}

    created_posts = 0
    created_comments = 0
    reel_count = 0
    post_count = 0
    total_likes = 0

    media_items: list[dict[str, Any]] = []
    media_details: list[dict[str, Any]] = []
    stories_data: list[dict[str, Any]] = []
    user_profile: dict[str, Any] = {}

    with httpx.Client(timeout=20.0) as client:
        media_res = client.get(
            f"{INSTAGRAM_GRAPH_BASE}/{ig_user_id}/media",
            params={
                "fields": "id,caption,timestamp,media_type,like_count,comments_count,permalink,media_url,thumbnail_url",
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

        try:
            profile_res = client.get(
                f"{INSTAGRAM_GRAPH_BASE}/{ig_user_id}",
                params={"fields": "username,profile_picture_url", "access_token": token},
            )
            if profile_res.status_code == 200:
                user_profile = profile_res.json() or {}
        except Exception as exc:  # noqa: BLE001
            logger.info("failed to fetch instagram profile %s: %s", ig_user_id, exc)

        for item in media_items:
            media_id = str(item.get("id") or "")
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
            comments_data: list[dict[str, Any]] = []
            comment_error = ""
            has_comment_scope = (
                "instagram_business_manage_comments" in granted_scopes
                or "instagram_manage_comments" in granted_scopes
            )
            if comment_count > 0 and not has_comment_scope:
                comment_error = "missing_scope:instagram_business_manage_comments"
            elif comment_count > 0:
                comments_data, comment_error = _fetch_comments_for_media(client, media_id, token)

            for c in comments_data:
                comment_id = str(c.get("id") or "")
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

            media_details.append(_normalize_media_details(item, len(comments_data), comment_error=comment_error))

        try:
            stories_res = client.get(
                f"{INSTAGRAM_GRAPH_BASE}/{ig_user_id}/stories",
                params={
                    "fields": "id,media_url,permalink,media_type,timestamp,caption",
                    "access_token": token,
                },
            )
            if stories_res.status_code == 200:
                stories_data = [_normalize_story(story) for story in stories_res.json().get("data", [])]
        except Exception as exc:  # noqa: BLE001
            logger.info("stories fetch failed for %s: %s", ig_user_id, exc)

    summary = {
        "stories": len(stories_data),
        "reels": reel_count,
        "posts": post_count,
        "total_likes": total_likes,
        "synced_comments": created_comments,
    }

    synced_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return {
        "ok": True,
        "created_posts": created_posts,
        "created_comments": created_comments,
        "media_seen": len(media_items),
        "media_summary": summary,
        "media_details": media_details,
        "stories": stories_data,
        "synced_at": synced_at,
        "user": user_profile,
        "granted_scopes": sorted(granted_scopes),
    }

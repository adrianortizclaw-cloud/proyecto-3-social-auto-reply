from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.models import Comment, OAuthConnection, Post, Reply, SocialAccount, SyncRun, User
from app.services.instagram_sync import INSTAGRAM_GRAPH_BASE, sync_instagram
from app.services.audit_service import log_action
from app.services.auto_reply_service import auto_reply_for_account

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _check_ownership(account_id: int, current_user: User, db: Session) -> SocialAccount:
    account = db.get(SocialAccount, account_id)
    if not account or account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _fetch_instagram_profile(ig_user_id: str, token: str) -> dict[str, str]:
    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.get(
                f"{INSTAGRAM_GRAPH_BASE}/{ig_user_id}",
                params={"fields": "username,profile_picture_url", "access_token": token},
            )
            if res.status_code == 200:
                return res.json() or {}
    except Exception:
        pass
    return {}


@router.post("/{account_id}/sync")
def sync_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = _check_ownership(account_id, current_user, db)
    result = sync_instagram(db, account)
    if not result.get("ok"):
        log_action(db, action="sync_failed", user_id=current_user.id, entity_type="social_account", entity_id=str(account.id), detail=str(result))
        reason = result.get("reason", "sync_error")
        run = SyncRun(
            social_account_id=account.id,
            status="failed",
            created_posts=0,
            created_comments=0,
            error_reason=reason,
            error_detail=str(result.get("detail", "")),
        )
        db.add(run)
        db.commit()
        status_code = 400
        if "token" in reason:
            status_code = 401
        raise HTTPException(status_code=status_code, detail=result)
    auto_report = auto_reply_for_account(db, account.id)
    result["auto_reply"] = auto_report
    synced_at = result.get("synced_at")
    run = SyncRun(
        social_account_id=account.id,
        status="success",
        created_posts=result.get("created_posts", 0),
        created_comments=result.get("created_comments", 0),
        error_reason="",
        error_detail="",
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    result["last_synced_at"] = synced_at or f"{datetime.utcnow().isoformat()}Z"
    log_action(db, action="sync_success", user_id=current_user.id, entity_type="social_account", entity_id=str(account.id), detail=str(result))
    return result


@router.get("/{account_id}")
def get_dashboard(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ownership(account_id, current_user, db)

    latest_posts = (
        db.query(Post)
        .filter(Post.account_id == account_id, Post.kind == "post")
        .order_by(Post.published_at.desc())
        .limit(10)
        .all()
    )
    latest_reels = (
        db.query(Post)
        .filter(Post.account_id == account_id, Post.kind == "reel")
        .order_by(Post.published_at.desc())
        .limit(10)
        .all()
    )
    latest_comments = (
        db.query(Comment)
        .join(Post, Comment.post_id == Post.id)
        .filter(Post.account_id == account_id)
        .order_by(Comment.created_at.desc())
        .limit(20)
        .all()
    )
    latest_replies = (
        db.query(Reply)
        .join(Comment, Reply.comment_id == Comment.id)
        .join(Post, Comment.post_id == Post.id)
        .filter(Post.account_id == account_id)
        .order_by(Reply.created_at.desc())
        .limit(20)
        .all()
    )

    connection = (
        db.query(OAuthConnection)
        .filter(OAuthConnection.social_account_id == account_id)
        .first()
    )
    profile: dict[str, str] = {}
    if connection:
        try:
            token = decrypt_secret(connection.access_token_encrypted)
            profile = _fetch_instagram_profile(connection.ig_business_account_id, token)
        except Exception:
            profile = {}

    last_run = (
        db.query(SyncRun)
        .filter(SyncRun.social_account_id == account_id, SyncRun.status == "success")
        .order_by(SyncRun.created_at.desc())
        .first()
    )
    last_synced_at = f"{last_run.created_at.isoformat()}Z" if last_run else None

    return {
        "latest_posts": [
            {"id": p.platform_post_id, "text": p.caption or "", "created_at": p.published_at.isoformat()} for p in latest_posts
        ],
        "latest_reels": [
            {"id": r.platform_post_id, "text": r.caption or "", "created_at": r.published_at.isoformat()} for r in latest_reels
        ],
        "latest_comments": [
            {
                "id": c.platform_comment_id,
                "comment_id": c.id,
                "text": c.text,
                "author_handle": c.author_handle,
                "created_at": c.created_at.isoformat(),
            }
            for c in latest_comments
        ],
        "latest_replies": [
            {"id": str(x.id), "text": x.text, "created_at": x.created_at.isoformat()} for x in latest_replies
        ],
        "last_synced_at": last_synced_at,
        "profile": profile,
    }

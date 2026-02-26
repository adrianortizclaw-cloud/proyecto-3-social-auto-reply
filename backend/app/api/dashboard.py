from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import User, SocialAccount, Post, Comment, Reply
from app.services.instagram_sync import sync_instagram
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _check_ownership(account_id: int, current_user: User, db: Session) -> SocialAccount:
    account = db.get(SocialAccount, account_id)
    if not account or account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


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
        status_code = 400
        if "token" in reason:
            status_code = 401
        raise HTTPException(status_code=status_code, detail=result)
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
                "created_at": c.created_at.isoformat(),
            }
            for c in latest_comments
        ],
        "latest_replies": [
            {"id": str(x.id), "text": x.text, "created_at": x.created_at.isoformat()} for x in latest_replies
        ],
    }

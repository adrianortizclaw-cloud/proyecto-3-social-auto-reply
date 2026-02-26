from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import Comment, Post, SocialAccount, User, Reply
from app.services.ai_response_service import generate_reply_for_comment

router = APIRouter(prefix="/api/replies", tags=["replies"])


def _ensure_comment_owner(db: Session, comment_id: int, user_id: int) -> Comment:
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="comment_not_found")
    post = db.get(Post, comment.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="post_not_found")
    account = db.get(SocialAccount, post.account_id)
    if not account or account.owner_id != user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return comment


@router.post("/generate/{comment_id}")
def generate_reply(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_comment_owner(db, comment_id, current_user.id)
    result = generate_reply_for_comment(db, comment_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/pending")
def list_pending_replies(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Reply)
        .join(Comment, Reply.comment_id == Comment.id)
        .join(Post, Comment.post_id == Post.id)
        .join(SocialAccount, Post.account_id == SocialAccount.id)
        .filter(SocialAccount.owner_id == current_user.id, Reply.status.in_(["draft", "escalated"]))
        .order_by(Reply.created_at.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return [
        {
            "reply_id": r.id,
            "status": r.status,
            "text": r.text,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

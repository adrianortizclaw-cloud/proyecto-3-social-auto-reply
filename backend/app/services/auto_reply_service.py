from sqlalchemy.orm import Session

from app.models.models import Comment, Post, Reply, SocialAccount
from app.services.ai_response_service import generate_reply_for_comment


def auto_reply_for_account(db: Session, account_id: int, limit: int = 20) -> dict:
    account = db.get(SocialAccount, account_id)
    if not account:
        return {"ok": False, "reason": "account_not_found"}

    # Only auto-run when account is in auto mode
    if account.auto_mode != "auto":
        return {"ok": True, "skipped": True, "reason": f"auto_mode={account.auto_mode}"}

    comments = (
        db.query(Comment)
        .join(Post, Comment.post_id == Post.id)
        .outerjoin(Reply, Reply.comment_id == Comment.id)
        .filter(Post.account_id == account_id, Reply.id.is_(None))
        .order_by(Comment.created_at.asc())
        .limit(min(max(limit, 1), 100))
        .all()
    )

    report = {"ok": True, "processed": 0, "sent": 0, "skipped": 0, "failed": 0}
    for c in comments:
        result = generate_reply_for_comment(db, c.id, publish_immediately=True)
        report["processed"] += 1
        status = result.get("status")
        if status == "sent":
            report["sent"] += 1
        elif status == "failed":
            report["failed"] += 1
        else:
            report["skipped"] += 1

    return report

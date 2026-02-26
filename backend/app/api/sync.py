from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import SyncRun, SocialAccount, User
from app.services.sync_service import run_sync_for_owner

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/run-all")
def run_all_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return run_sync_for_owner(db, current_user.id)


@router.get("/history")
def sync_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(SyncRun)
        .join(SocialAccount, SyncRun.social_account_id == SocialAccount.id)
        .filter(SocialAccount.owner_id == current_user.id)
        .order_by(SyncRun.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    return [
        {
            "id": r.id,
            "social_account_id": r.social_account_id,
            "status": r.status,
            "created_posts": r.created_posts,
            "created_comments": r.created_comments,
            "error_reason": r.error_reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

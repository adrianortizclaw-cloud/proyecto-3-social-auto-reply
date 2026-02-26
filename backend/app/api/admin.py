from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_owner_or_admin
from app.db.session import get_db
from app.models.models import AuditLog, User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit")
def audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner_or_admin),
):
    _ = current_user
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

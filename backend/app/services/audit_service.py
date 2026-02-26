from sqlalchemy.orm import Session

from app.models.models import AuditLog


def log_action(
    db: Session,
    action: str,
    user_id: int | None = None,
    entity_type: str = "",
    entity_id: str = "",
    detail: str = "",
):
    row = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        detail=detail[:2000],
    )
    db.add(row)
    db.commit()
    return row

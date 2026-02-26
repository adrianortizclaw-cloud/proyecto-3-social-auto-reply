from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User, WebhookEvent
from app.services.webhook_service import persist_meta_webhook, process_webhook_event

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("/meta")
def verify_meta_webhook(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
):
    if mode == "subscribe" and token == settings.meta_webhook_verify_token:
        return int(challenge)
    raise HTTPException(status_code=403, detail="webhook_verification_failed")


@router.post("/meta")
async def receive_meta_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    event_id = persist_meta_webhook(db, payload)
    process_webhook_event(db, event_id)
    return {"ok": True, "event_id": event_id}


@router.get("/events")
def list_events(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user  # requires auth for internal observability endpoint
    rows = db.query(WebhookEvent).order_by(WebhookEvent.created_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [
        {
            "id": r.id,
            "ig_business_account_id": r.ig_business_account_id,
            "processed": r.processed,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

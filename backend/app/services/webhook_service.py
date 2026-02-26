import json
from sqlalchemy.orm import Session

from app.models.models import SocialAccount, WebhookEvent
from app.services.sync_service import run_sync_for_account


def persist_meta_webhook(db: Session, payload: dict) -> int:
    ig_id = None
    for entry in payload.get("entry", []):
        if entry.get("id"):
            ig_id = str(entry.get("id"))
            break

    row = WebhookEvent(
        source="meta",
        ig_business_account_id=ig_id,
        payload_json=json.dumps(payload, ensure_ascii=False),
        processed=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def process_webhook_event(db: Session, event_id: int) -> dict:
    event = db.get(WebhookEvent, event_id)
    if not event:
        return {"ok": False, "reason": "event_not_found"}

    if event.processed:
        return {"ok": True, "message": "already_processed"}

    if not event.ig_business_account_id:
        event.processed = 1
        db.commit()
        return {"ok": True, "message": "processed_without_ig_id"}

    account = (
        db.query(SocialAccount)
        .filter(SocialAccount.account_handle == event.ig_business_account_id)
        .first()
    )
    if account:
        run_sync_for_account(db, account)

    event.processed = 1
    db.commit()
    return {"ok": True, "message": "processed"}

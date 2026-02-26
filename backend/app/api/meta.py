from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import SocialAccount, User
from app.services.meta_oauth_service import (
    build_oauth_url,
    consume_oauth_state,
    create_oauth_state,
    discover_page_and_ig,
    exchange_code_for_long_lived_token,
    upsert_oauth_connection,
)
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/meta", tags=["meta-oauth"])


@router.get("/oauth/start/{account_id}")
def oauth_start(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = db.get(SocialAccount, account_id)
    if not account or account.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")

    state = create_oauth_state(db, account)
    log_action(db, action="oauth_start", user_id=current_user.id, entity_type="social_account", entity_id=str(account.id))
    return {"url": build_oauth_url(account_id, state)}


@router.get("/oauth/callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    state_row = consume_oauth_state(db, state)
    if not state_row:
        raise HTTPException(status_code=400, detail="invalid_or_expired_state")

    try:
        token, expires_in = exchange_code_for_long_lived_token(code)
        page_id, ig_business_account_id = discover_page_and_ig(token)
        upsert_oauth_connection(
            db=db,
            social_account_id=state_row.social_account_id,
            token=token,
            expires_in=expires_in,
            page_id=page_id,
            ig_business_account_id=ig_business_account_id,
        )
        log_action(db, action="oauth_connected", entity_type="social_account", entity_id=str(state_row.social_account_id), detail=f"page_id={page_id},ig_id={ig_business_account_id}")
    except Exception as exc:
        log_action(db, action="oauth_failed", entity_type="social_account", entity_id=str(state_row.social_account_id), detail=str(exc))
        raise HTTPException(status_code=400, detail=f"oauth_callback_failed: {exc}")

    return {
        "ok": True,
        "social_account_id": state_row.social_account_id,
        "page_id": page_id,
        "ig_business_account_id": ig_business_account_id,
    }

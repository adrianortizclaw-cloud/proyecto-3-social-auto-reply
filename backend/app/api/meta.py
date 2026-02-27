from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import json

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.models import SocialAccount, User
from app.services.meta_oauth_service import (
    build_oauth_url,
    consume_oauth_state,
    create_oauth_state,
    exchange_code_for_short_lived_token,
    exchange_short_lived_for_long_lived_token,
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
        short_token, instagram_user_id, permissions = exchange_code_for_short_lived_token(code)
        long_token, expires_in = exchange_short_lived_for_long_lived_token(short_token)
        upsert_oauth_connection(
            db=db,
            social_account_id=state_row.social_account_id,
            token=long_token,
            expires_in=expires_in,
            page_id="",
            ig_business_account_id=instagram_user_id,
        )
        detail_scopes = ",".join(permissions) if permissions else ""
        log_action(
            db,
            action="oauth_connected",
            entity_type="social_account",
            entity_id=str(state_row.social_account_id),
            detail=f"ig_id={instagram_user_id}{' scopes=' + detail_scopes if detail_scopes else ''}",
        )
    except Exception as exc:
        log_action(db, action="oauth_failed", entity_type="social_account", entity_id=str(state_row.social_account_id), detail=str(exc))
        raise HTTPException(status_code=400, detail=f"oauth_callback_failed: {exc}")

    account = db.get(SocialAccount, state_row.social_account_id)
    if not account or not account.owner_id:
        raise HTTPException(status_code=400, detail="Account owner missing")
    owner = db.get(User, account.owner_id)
    if not owner:
        raise HTTPException(status_code=400, detail="Owner not found")

    access_token = create_access_token(str(owner.id))
    payload = json.dumps({"token": access_token, "social_account_id": str(account.id)})
    frontend_origin = settings.frontend_origin
    html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Conexión terminada</title>
  </head>
  <body>
    <p>¡Cuenta vinculada! Puedes cerrar esta ventana.</p>
    <script>
      const data = {payload};
      if (window.opener) {{
        window.opener.postMessage(data, '{frontend_origin}');
      }}
      window.close();
    </script>
  </body>
</html>"""
    return HTMLResponse(html)

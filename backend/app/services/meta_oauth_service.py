import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import encrypt_secret
from app.models.models import OAuthConnection, OAuthState, SocialAccount

INSTAGRAM_AUTH_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_SHORT_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_INSTAGRAM = "https://graph.instagram.com"
logger = logging.getLogger(__name__)


def build_oauth_url(account_id: int, state: str) -> str:
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise ValueError('META_APP_ID (and META_APP_SECRET) must be configured to build the OAuth URL')
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": ",".join(settings.meta_scopes),
    }
    logger.debug("building instagram business login url account=%s state=%s client_id=%s", account_id, state, settings.meta_app_id)
    return f"{INSTAGRAM_AUTH_URL}?{urlencode(params)}"


def create_oauth_state(db: Session, account: SocialAccount) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.add(OAuthState(state=token, social_account_id=account.id, expires_at=expires_at))
    db.commit()
    return token


def consume_oauth_state(db: Session, state: str) -> OAuthState | None:
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not row:
        return None
    db.delete(row)
    db.commit()
    if row.expires_at < datetime.utcnow():
        return None
    return row


def _extract_short_token_payload(payload: dict) -> tuple[str, str, list[str]]:
    data_nodes = payload.get("data")
    if isinstance(data_nodes, list) and data_nodes:
        info = data_nodes[0] or {}
    else:
        info = payload
    access_token = info.get("access_token")
    user_id = str(info.get("user_id") or info.get("instagram_user_id") or "").strip()
    permissions_raw = info.get("permissions") or ""
    permissions = [scope.strip() for scope in permissions_raw.split(",") if scope.strip()]
    return access_token, user_id, permissions


def exchange_code_for_short_lived_token(code: str) -> tuple[str, str, list[str]]:
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            INSTAGRAM_SHORT_TOKEN_URL,
            data={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": settings.meta_redirect_uri,
                "code": code,
            },
        )
        response.raise_for_status()
        access_token, user_id, permissions = _extract_short_token_payload(response.json() or {})
        if not access_token:
            raise ValueError("short_lived_token_missing")
        if not user_id:
            raise ValueError("instagram_user_id_missing")
        return access_token, user_id, permissions


def exchange_short_lived_for_long_lived_token(short_token: str) -> tuple[str, int]:
    with httpx.Client(timeout=20.0) as client:
        long_res = client.get(
            f"{GRAPH_INSTAGRAM}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": settings.meta_app_secret,
                "access_token": short_token,
            },
        )
        long_res.raise_for_status()
        payload = long_res.json() or {}
        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 0))
        if not access_token:
            raise ValueError("long_lived_token_missing")
        return access_token, expires_in


def upsert_oauth_connection(
    db: Session,
    social_account_id: int,
    token: str,
    expires_in: int,
    page_id: str,
    ig_business_account_id: str,
):
    expires_at = datetime.utcnow() + timedelta(seconds=max(expires_in, 0))
    row = db.query(OAuthConnection).filter(OAuthConnection.social_account_id == social_account_id).first()
    if not row:
        row = OAuthConnection(
            social_account_id=social_account_id,
            access_token_encrypted=encrypt_secret(token),
            expires_at=expires_at,
            page_id=page_id,
            ig_business_account_id=ig_business_account_id,
            scopes=",".join(settings.meta_scopes),
        )
        db.add(row)
    else:
        row.access_token_encrypted = encrypt_secret(token)
        row.expires_at = expires_at
        row.page_id = page_id
        row.ig_business_account_id = ig_business_account_id
        row.scopes = ",".join(settings.meta_scopes)

    account = db.get(SocialAccount, social_account_id)
    if account:
        account.account_handle = ig_business_account_id
        account.instagram_token_encrypted = encrypt_secret(token)

    db.commit()
    return row

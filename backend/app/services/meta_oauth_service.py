import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import encrypt_secret
from app.models.models import OAuthConnection, OAuthState, SocialAccount

GRAPH_BASE = "https://graph.facebook.com/v22.0"
OAUTH_BASE = "https://www.facebook.com/v22.0/dialog/oauth"


def build_oauth_url(account_id: int, state: str) -> str:
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": ",".join(settings.meta_scopes),
    }
    return f"{OAUTH_BASE}?{urlencode(params)}"


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


def exchange_code_for_long_lived_token(code: str) -> tuple[str, int]:
    with httpx.Client(timeout=20.0) as client:
        short_res = client.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "redirect_uri": settings.meta_redirect_uri,
                "client_secret": settings.meta_app_secret,
                "code": code,
            },
        )
        short_res.raise_for_status()
        short_token = short_res.json().get("access_token")
        if not short_token:
            raise ValueError("short_lived_token_missing")

        long_res = client.get(
            f"{GRAPH_BASE}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "fb_exchange_token": short_token,
            },
        )
        long_res.raise_for_status()
        payload = long_res.json()
        return payload["access_token"], int(payload.get("expires_in", 0))


def discover_page_and_ig(token: str) -> tuple[str, str]:
    with httpx.Client(timeout=20.0) as client:
        pages_res = client.get(f"{GRAPH_BASE}/me/accounts", params={"access_token": token})
        pages_res.raise_for_status()
        pages = pages_res.json().get("data", [])
        if not pages:
            raise ValueError("no_pages_found")

        for page in pages:
            page_id = str(page.get("id", ""))
            if not page_id:
                continue
            ig_res = client.get(
                f"{GRAPH_BASE}/{page_id}",
                params={"fields": "instagram_business_account", "access_token": token},
            )
            if ig_res.status_code != 200:
                continue
            ig_obj = (ig_res.json() or {}).get("instagram_business_account") or {}
            ig_id = str(ig_obj.get("id", ""))
            if ig_id:
                return page_id, ig_id

    raise ValueError("no_instagram_business_account_found")


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

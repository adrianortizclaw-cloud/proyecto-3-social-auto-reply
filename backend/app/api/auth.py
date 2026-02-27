import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import secrets
from urllib.parse import urlparse

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.db.session import get_db
from app.models.models import User, SocialAccount
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    InstagramLoginRequest,
    InstagramStartResponse,
)
from app.services.meta_oauth_service import build_oauth_url, create_oauth_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


def _normalize_handle(value: str) -> str:
    return value.strip().lstrip("@").lower()


def _ensure_owner_for_handle(db: Session, handle: str) -> User:
    if not handle:
        raise HTTPException(status_code=400, detail="Instagram handle is required")
    alias_email = f"ig_{handle}@instagram.local"
    user = db.query(User).filter(User.email == alias_email).first()
    if user:
        logger.debug("reuse owner for handle=%s email=%s", handle, alias_email)
        return user
    user = User(email=alias_email, password_hash=hash_password(secrets.token_urlsafe()))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.debug("created owner id=%s handle=%s", user.id, handle)
    return user


def _ensure_account_for_owner(db: Session, owner: User, handle: str) -> SocialAccount:
    account = (
        db.query(SocialAccount)
        .filter(SocialAccount.owner_id == owner.id, SocialAccount.account_handle == handle)
        .first()
    )
    if account:
        return account
    account = SocialAccount(
        owner_id=owner.id,
        platform="instagram",
        account_handle=handle,
        prompt_persona="Tono cercano y profesional.",
        auto_mode="auto",
    )
    logger.debug("created social account id=%s owner=%s handle=%s", account.id, owner.id, handle)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.post("/instagram/start", response_model=InstagramStartResponse)
def instagram_start(payload: InstagramLoginRequest, db: Session = Depends(get_db)):
    handle = _normalize_handle(payload.handle)
    if not handle:
        raise HTTPException(status_code=400, detail="Instagram handle is required")

    owner = _ensure_owner_for_handle(db, handle)
    account = _ensure_account_for_owner(db, owner, handle)
    state = create_oauth_state(db, account)
    logger.debug("instagram_start handle=%s owner_id=%s social_account=%s", handle, owner.id, account.id)
    try:
        url = build_oauth_url(account.id, state)
    except ValueError as exc:
        logger.error("build oauth failed: %s", str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    parsed_redirect = urlparse(settings.meta_redirect_uri)
    callback_origin = None
    if parsed_redirect.scheme and parsed_redirect.netloc:
        callback_origin = f"{parsed_redirect.scheme}://{parsed_redirect.netloc}"
    return InstagramStartResponse(url=url, account_id=account.id, callback_origin=callback_origin)

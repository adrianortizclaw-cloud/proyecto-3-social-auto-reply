from __future__ import annotations

from secrets import token_urlsafe
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_secret, encrypt_secret
from app.db.session import get_db
from app.models.models import InstagramAuthState, InstagramSession
from app.services.instagram_wrapper import Instagram, InstagramError, exchange_code_for_token, get_login_url

router = APIRouter(prefix="/api/instagram", tags=["instagram"])


class MessageBody(BaseModel):
    message: str


class VisibilityBody(BaseModel):
    hide: bool = True


class RawRequestBody(BaseModel):
    endpoint: str


def _require_session(db: Session, x_session_id: str | None) -> InstagramSession:
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Missing X-Session-Id header")
    session = db.query(InstagramSession).filter(InstagramSession.session_id == x_session_id).first()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    return session


def _ig_from_session(session: InstagramSession) -> Instagram:
    return Instagram(decrypt_secret(session.access_token_encrypted))


@router.get("/login-url")
def login_url(db: Session = Depends(get_db)):
    state = token_urlsafe(24)
    db.add(InstagramAuthState(state=state))
    db.commit()
    return {"url": get_login_url(state=state), "state": state}


@router.get("/callback")
def callback(code: str = "", state: str = "", db: Session = Depends(get_db)):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    auth_state = db.query(InstagramAuthState).filter(InstagramAuthState.state == state).first()
    if not auth_state or auth_state.used:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    auth_state.used = True

    try:
        token_data = exchange_code_for_token(code)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_id = token_urlsafe(32)
    db.add(
        InstagramSession(
            session_id=session_id,
            ig_user_id=str(token_data.get("id", "")),
            username=token_data.get("username"),
            name=token_data.get("name"),
            access_token_encrypted=encrypt_secret(token_data["access_token"]),
        )
    )
    db.commit()

    redirect_query = urlencode({"session": session_id})
    return RedirectResponse(url=f"{settings.frontend_origin}/?{redirect_query}")


@router.get("/session")
def get_session(
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    return {
        "session_id": session.session_id,
        "ig_user_id": session.ig_user_id,
        "username": session.username,
        "name": session.name,
        "created_at": session.created_at.isoformat(),
    }


@router.get("/me")
def me(
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).me()
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/media")
def media(
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).get_media()
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comments/{media_id}")
def comments(
    media_id: str,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).get_comments(media_id)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comment/{comment_id}")
def comment(
    comment_id: str,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).get_comment(comment_id)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/replies/{comment_id}")
def replies(
    comment_id: str,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).get_replies(comment_id)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/comments/{media_id}")
def add_comment(
    media_id: str,
    payload: MessageBody,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).add_comment(media_id, payload.message)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reply/{comment_id}")
def reply(
    comment_id: str,
    payload: MessageBody,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).reply_to_comment(comment_id, payload.message)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/comments/{comment_id}/visibility")
def visibility(
    comment_id: str,
    payload: VisibilityBody,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).hide_comment(comment_id, payload.hide)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    try:
        return _ig_from_session(session).delete_comment(comment_id)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/raw")
def raw_get(
    payload: RawRequestBody,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    session = _require_session(db, x_session_id)
    endpoint = payload.endpoint if payload.endpoint.startswith("/") else f"/{payload.endpoint}"
    try:
        return _ig_from_session(session).get(endpoint)
    except InstagramError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

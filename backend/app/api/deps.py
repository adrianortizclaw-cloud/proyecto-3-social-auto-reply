from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

RATE_LIMIT_PER_MINUTE = 120
_rate_window = defaultdict(lambda: {"count": 0, "reset_at": datetime.utcnow() + timedelta(minutes=1)})


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)
    if not user:
        raise credentials_exception
    return user


def rate_limit_user(current_user: User = Depends(get_current_user)) -> User:
    now = datetime.utcnow()
    bucket = _rate_window[current_user.id]
    if now >= bucket["reset_at"]:
        bucket["count"] = 0
        bucket["reset_at"] = now + timedelta(minutes=1)
    bucket["count"] += 1
    if bucket["count"] > RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="rate_limit_exceeded")
    return current_user


def require_owner_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="insufficient_role")
    return current_user

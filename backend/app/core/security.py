from datetime import datetime, timedelta, timezone
import base64
import hashlib

import bcrypt
from cryptography.fernet import Fernet
from jose import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def _password_material(password: str) -> bytes:
    # Pre-hash to avoid bcrypt 72-byte limit and keep deterministic verification.
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_material(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_password_material(plain), hashed.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def _fernet_key() -> bytes:
    digest = hashlib.sha256(settings.app_secret_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str) -> str:
    f = Fernet(_fernet_key())
    return f.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    f = Fernet(_fernet_key())
    return f.decrypt(value.encode()).decode()

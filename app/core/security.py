from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt is great but can be finicky across platforms/interpreters.
# For MVP we use PBKDF2-SHA256 which is widely supported and still secure.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

PASSWORD_RE = re.compile(r"^(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")

JWT_ALG = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def is_password_valid(password: str) -> bool:
    return bool(PASSWORD_RE.match(password))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALG])

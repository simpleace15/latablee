# Argon2id hashing + JWT (HS256) sessions — no auth shortcuts
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.engine import get_session
from app.models import User

_pwd = PasswordHasher(
    time_cost=get_settings().argon2_time_cost,
    memory_cost=get_settings().argon2_memory_cost,
    parallelism=get_settings().argon2_parallelism,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user: User, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": user.public_id, "iat": now, "exp": exp, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    payload = decode_token(token)
    user = session.exec(select(User).where(User.public_id == payload["sub"])).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def require_household(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.household_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No household yet — finish onboarding")
    return user

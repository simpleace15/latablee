# Auth: register (admin-invite-only), login, me, invite links
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db.engine import get_session
from app.models import InviteLink, User, _aware_utc, utcnow

router = APIRouter()


def _first_user_exists(session: Session) -> bool:
    return session.exec(select(User)).first() is not None


@router.post("/register", status_code=201)
def register(
    name: str,
    password: str,
    invite_token: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """First ever user becomes admin; later users need a valid invite token."""
    if len(password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    first = not _first_user_exists(session)
    if not first and not invite_token:
        raise HTTPException(403, "Registration is admin-invite-only — ask for an invite link")
    invite = None
    if not first:
        invite = session.exec(select(InviteLink).where(InviteLink.token == invite_token)).first()
        if invite is None or invite.used_at is not None:
            raise HTTPException(403, "Invalid or already-used invite expiry")
        expires = _aware_utc(invite.expires_at)
        if expires is not None and expires < utcnow():
            raise HTTPException(403, "Invite expired")
        invite.used_at = utcnow()
    role = "admin" if first else "user"
    user = User(public_id=secrets.token_urlsafe(16), name=name, role=role,
                password_hash=hash_password(password),
                household_id=None if first else (invite.household_id if invite else None))
    session.add(user)
    if invite is not None:
        session.add(invite)
    session.commit()
    session.refresh(user)
    return {"token": create_access_token(user),
            "user": {"public_id": user.public_id, "name": user.name, "role": user.role}}


@router.post("/token")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    user = session.exec(select(User).where(User.name == form.username)).first()
    if user is None or user.disabled or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong name or password")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(user: Annotated[User, Depends(get_current_user)]) -> dict:
    return {"public_id": user.public_id, "name": user.name, "role": user.role,
            "household_id": user.household_id}


@router.post("/invite")
def create_invite(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    expires_days: int = 14,
) -> dict:
    """Admin creates an invite link for the spouse/roommates."""
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    if user.household_id is None:
        raise HTTPException(409, "Finish household onboarding before inviting members")
    token = secrets.token_urlsafe(24)
    link = InviteLink(
        token=token,
        household_id=user.household_id,
        created_by=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=expires_days),
    )
    session.add(link)
    session.commit()
    return {"invite_url": f"{get_settings().public_origin}/register?invite={token}",
            "expires_days": expires_days}

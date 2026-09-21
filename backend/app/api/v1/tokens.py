# Device/API tokens for integrations (Home Assistant, scripts, repo 2)
import hashlib
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import get_current_user
from app.db.engine import get_session
from app.models import ApiToken, User, utcnow

router = APIRouter()


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class TokenIn(BaseModel):
    name: str


@router.post("", status_code=201)
def create_token(
    payload: TokenIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Mint a device token. The raw value is returned ONCE — store it now."""
    if not payload.name.strip():
        raise HTTPException(422, "Name required")
    raw = f"lat_{secrets.token_hex(20)}"
    row = ApiToken(
        token_hash=_hash(raw), name=payload.name.strip()[:60],
        user_id=user.id, household_id=user.household_id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id, "name": row.name, "token": raw,
            "created_at": row.created_at.isoformat(),
            "note": "Copy it now — it is never shown again"}


@router.get("")
def list_tokens(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    rows = session.exec(select(ApiToken).where(ApiToken.user_id == user.id)).all()
    return {"tokens": [
        {"id": r.id, "name": r.name, "created_at": r.created_at.isoformat(),
         "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
         "revoked": r.revoked_at is not None}
        for r in sorted(rows, key=lambda x: x.id or 0, reverse=True)
    ]}


@router.delete("/{token_id}", status_code=204)
def revoke_token(
    token_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    row = session.get(ApiToken, token_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Token not found")
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        session.add(row)
        session.commit()

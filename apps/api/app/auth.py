"""Single-org JWT auth (ADR-0005).

HS256 token carrying ``sub`` (user id) + ``role`` (no tenant claim). Verification is the same
path whether the token came from local login or (future) OIDC. Passwords are hashed with
PBKDF2-HMAC-SHA256 (stdlib — no native bcrypt dep). The pipeline receives principals
``{role, sub}``; ``admin`` is unrestricted (`app.repository.PostgresAuthorizer`).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings

_PBKDF2_ROUNDS = 240_000
# auto_error=False so endpoints can choose how to handle a missing token.
_bearer = HTTPBearer(auto_error=False)


# --- passwords ---


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _algo, rounds, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


# --- tokens ---


def create_access_token(*, sub: str, role: str) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.idp_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.idp_jwt_secret, algorithm=settings.idp_jwt_alg)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.idp_jwt_secret, algorithms=[settings.idp_jwt_alg])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc


# --- dependencies ---


class Principal:
    def __init__(self, sub: str, role: str) -> None:
        self.sub = sub
        self.role = role

    def as_set(self) -> set[str]:
        """Principals for the ACL double-check: role token + subject id."""
        return {self.role, self.sub}


def get_current_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if creds is None:
        raise HTTPException(status_code=401, detail="missing bearer token")
    claims = decode_token(creds.credentials)
    return Principal(sub=str(claims.get("sub", "")), role=str(claims.get("role", "user")))


def require_roles(*roles: str) -> Callable[..., Principal]:
    """Dependency factory enforcing the caller holds one of ``roles``."""

    def _dep(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        if principal.role not in roles:
            raise HTTPException(status_code=403, detail=f"requires role in {roles}")
        return principal

    return _dep


def ensure_bootstrap_admin(session: Session) -> None:
    """Idempotently ensure the env-configured bootstrap admin exists (single-org setup)."""
    from db import User
    from hybrid_idp_shared import Role
    from sqlalchemy import select

    email = settings.idp_bootstrap_admin_email
    password = settings.idp_bootstrap_admin_password
    if not email or not password:
        return
    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        if existing.password_hash is None:
            existing.password_hash = hash_password(password)
            session.commit()
        return
    session.add(User(email=email, role=Role.ADMIN.value, password_hash=hash_password(password)))
    session.commit()

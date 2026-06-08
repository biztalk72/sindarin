"""Auth endpoints (ADR-0005): local login + current-user. OIDC is the optional alt path."""

from __future__ import annotations

from typing import Annotated

from db import User
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, create_access_token, get_current_principal, verify_password
from app.db import get_session

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    sub: str


class MeResponse(BaseModel):
    sub: str
    role: str


@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, session: Annotated[Session, Depends(get_session)]) -> TokenResponse:
    user = session.execute(select(User).where(User.email == req.email)).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(sub=str(user.id), role=user.role)
    return TokenResponse(access_token=token, role=user.role, sub=str(user.id))


@router.get("/auth/me", response_model=MeResponse)
def me(principal: Annotated[Principal, Depends(get_current_principal)]) -> MeResponse:
    return MeResponse(sub=principal.sub, role=principal.role)

"""ADR-0005: JWT auth — password hashing + token create/verify."""

import jwt
import pytest
from app.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from fastapi import HTTPException


def test_password_hash_roundtrip() -> None:
    h = hash_password("s3cret!")
    assert h != "s3cret!"
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)
    assert not verify_password("s3cret!", None)


def test_token_roundtrip_carries_sub_and_role() -> None:
    token = create_access_token(sub="u-1", role="admin")
    claims = decode_token(token)
    assert claims["sub"] == "u-1"
    assert claims["role"] == "admin"


def test_decode_rejects_tampered_token() -> None:
    with pytest.raises(HTTPException) as exc:
        decode_token("not.a.jwt")
    assert exc.value.status_code == 401


def test_decode_rejects_wrong_signature() -> None:
    forged = jwt.encode({"sub": "x", "role": "admin"}, "different-secret", algorithm="HS256")
    with pytest.raises(HTTPException):
        decode_token(forged)


def test_no_tenant_claim() -> None:
    # Single-org: the token must not carry a tenant claim (ADR-0005).
    claims = decode_token(create_access_token(sub="u", role="user"))
    assert "tenant" not in claims
    assert claims["role"] == "user"
    assert settings.idp_jwt_alg == "HS256"

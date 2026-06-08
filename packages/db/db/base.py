"""Declarative base + shared column helpers."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def pk_uuid() -> Mapped[uuid.UUID]:
    """UUID primary key, generated server-side (pg ``gen_random_uuid()``, core since pg13)."""
    return mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))


def created_at() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

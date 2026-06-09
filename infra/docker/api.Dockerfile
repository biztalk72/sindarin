# Hybrid IDP API image. Built by Harness build-images stage (PRD2 §13.2).
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

# uv for fast, reproducible workspace installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Full workspace source (uv workspace needs every member present to resolve).
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY workers ./workers
COPY apps/api ./apps/api
# Migration assets so the container self-migrates on startup (alembic targets db.Base).
COPY alembic.ini ./
COPY infra/migrations ./infra/migrations
# Install only the api package + its (workspace + external) deps into /srv/.venv.
RUN uv sync --frozen --no-dev --package hybrid-idp-api

# Pre-fetch the chat-model tokenizer (ADR-0011 Phase 2: token-aware pack_context). This
# is a tiny tokenizer.json (~3–10 MB) — NOT the model weights, which vLLM serves separately.
# Build-time fetch means /api/chat's first request stays fast instead of paying a one-time
# HuggingFace download. CHAT_MODEL is a build-arg so swapping models doesn't require a
# Dockerfile change.
ARG CHAT_MODEL=nvidia/Llama-3.1-Nemotron-Nano-8B-v1
ENV CHAT_MODEL=${CHAT_MODEL}
RUN uv run --no-dev --package hybrid-idp-api python -c \
    "from tokenizers import Tokenizer; Tokenizer.from_pretrained('${CHAT_MODEL}')" \
    || echo "tokenizer prefetch failed for ${CHAT_MODEL} — first request will retry"

EXPOSE 8000
# Self-migrating: apply schema (alembic) then serve. DATABASE_URL is built from the
# in-container POSTGRES_* so migrations hit the compose-network DB; the app lifespan then
# bootstraps the admin (ADR-0005) against the migrated schema.
CMD ["sh", "-c", "DATABASE_URL=\"postgresql+psycopg://${POSTGRES_USER:-hybrid_idp}:${POSTGRES_PASSWORD:-hybrid_idp}@${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-hybrid_idp}\" uv run --no-dev --package hybrid-idp-api alembic upgrade head && exec uv run --no-dev --package hybrid-idp-api uvicorn app.main:app --host 0.0.0.0 --port 8000"]

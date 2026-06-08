# Migrations (Alembic)

PostgreSQL schema migrations for the relational model (PRD2 §6.2). Models live in
`packages/db` (`db.Base.metadata`); this directory is the Alembic environment.

- **Config:** `alembic.ini` (repo root) → `script_location = infra/migrations`.
- **URL:** resolved in `env.py` from `DATABASE_URL`, else built from `POSTGRES_*`
  (host-run migrations use `POSTGRES_PUBLISHED_PORT`, not the in-container `POSTGRES_PORT`).
- **Tables:** `users`, `documents`, `document_versions`, `document_blocks`,
  `document_tables`, `document_keywords`, `document_entities`, `keyword_edges`,
  `ingestion_jobs`, `acl_entries`, `audit_logs`, `eval_runs`.

## Commands

```bash
make migrate                      # alembic upgrade head (loads .env)
make migration m="add x column"   # autogenerate a new revision from packages/db models
# direct (host), pointing at the published port:
DATABASE_URL=postgresql+psycopg://hybrid_idp:<pw>@localhost:5433/hybrid_idp \
  uv run alembic upgrade head
```

New vector payload fields require a migration + retrieval test (CLAUDE.md §5 / ADR-0008).
Enum-like columns are stored as strings (`hybrid_idp_shared` values), not native PG enums.

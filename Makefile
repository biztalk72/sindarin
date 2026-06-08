# Hybrid IDP — developer entrypoints. See docs/PRD2.md §12, §13.
.DEFAULT_GOAL := help
# --env-file .env so compose interpolation reads repo-root .env (the -f path's dir is NOT
# the interpolation source). Keeps postgres init creds consistent with the api's env_file.
COMPOSE := docker compose --env-file .env -f infra/compose/dev.yml

.PHONY: help install lint typecheck test test-int test-e2e eval up down fmt migrate migration \
        ci security-scan deploy smoke rollback

# Load .env (if present) so DB env vars reach Alembic's env.py.
LOAD_ENV := set -a; [ -f .env ] && . ./.env; set +a;

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install Python workspace (uv) + web deps
	uv sync --all-extras --dev
	cd apps/web && npm install

lint: ## ruff (Python) + eslint (web) — both blocking
	uv run ruff check .
	cd apps/web && npm run lint

typecheck: ## tsc (web) + mypy --strict (Python) — both blocking
	cd apps/web && npm run typecheck
	uv run mypy packages apps/api workers

fmt: ## Format Python
	uv run ruff format .
	uv run ruff check --fix .

test: ## Unit tests (Python + web)
	uv run pytest tests/unit apps/api/tests
	cd apps/web && npm test --if-present

test-int: ## Integration tests (spins up test compose)
	docker compose -f infra/compose/test.yml up -d
	uv run pytest -m integration tests/integration; \
	  status=$$?; docker compose -f infra/compose/test.yml down -v; exit $$status

test-e2e: ## E2E smoke (upload→ingest→chat→citation)
	uv run pytest -m e2e tests/e2e

eval: ## Golden-query eval gate (release-gated)
	uv run pytest -m eval tests/eval

up: ## Start dev stack
	$(COMPOSE) up -d

down: ## Stop dev stack
	$(COMPOSE) down

migrate: ## Apply DB migrations (alembic upgrade head)
	@$(LOAD_ENV) uv run alembic upgrade head

migration: ## Autogenerate a migration: make migration m="add x"
	@$(LOAD_ENV) uv run alembic revision --autogenerate -m "$(m)"

# --- CI/CD (PRD2 §13) ---

ci: ## CI gate: lint + typecheck + unit + eval (what the pipeline runs)
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) eval

security-scan: ## Dependency + secret scan (best-effort; non-blocking locally)
	uv run pip-audit || true
	cd apps/web && npm audit --audit-level high || true
	command -v gitleaks >/dev/null && gitleaks detect --no-git -v || echo "gitleaks not installed"

deploy: ## Deploy an env: make deploy ENV=staging IMAGE_TAG=abc123
	infra/scripts/deploy.sh $(ENV) $(IMAGE_TAG)

smoke: ## Smoke-test a deployment: make smoke BASE=http://host:8000
	infra/scripts/smoke.sh $(BASE)

rollback: ## Roll back: make rollback ENV=prod PREV=previous-tag
	infra/scripts/rollback.sh $(ENV) $(PREV)

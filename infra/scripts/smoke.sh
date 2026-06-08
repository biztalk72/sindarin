#!/usr/bin/env bash
# Run post-deploy smoke tests against a deployment (PRD2 §13 smoke-tests step).
# Usage: infra/scripts/smoke.sh [base_url]
set -euo pipefail
export SMOKE_BASE_URL="${1:-${SMOKE_BASE_URL:-http://localhost:8000}}"
echo "→ smoke testing $SMOKE_BASE_URL"
uv run pytest -m e2e tests/e2e/smoke -q

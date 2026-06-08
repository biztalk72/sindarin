#!/usr/bin/env bash
# Deploy a compose environment and wait for the API healthcheck (PRD2 §13 deploy step).
# Usage: infra/scripts/deploy.sh <env> [image_tag]
#   env       = staging | prod | dev   (selects infra/compose/<env>.yml + .env.<env>)
#   image_tag = registry image tag to roll out (default: $IMAGE_TAG or "latest")
set -euo pipefail

ENV="${1:?usage: deploy.sh <env> [image_tag]}"
export IMAGE_TAG="${2:-${IMAGE_TAG:-latest}}"

COMPOSE_FILE="infra/compose/${ENV}.yml"
ENV_FILE=".env.${ENV}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/api/health}"

[ -f "$COMPOSE_FILE" ] || { echo "missing $COMPOSE_FILE"; exit 1; }
ENV_ARG=()
[ -f "$ENV_FILE" ] && ENV_ARG=(--env-file "$ENV_FILE")

echo "→ deploying env=$ENV tag=$IMAGE_TAG"
docker compose "${ENV_ARG[@]}" -f "$COMPOSE_FILE" pull 2>/dev/null || true
docker compose "${ENV_ARG[@]}" -f "$COMPOSE_FILE" up -d

echo "→ waiting for healthcheck at $HEALTH_URL"
for i in $(seq 1 45); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "✓ healthy after ~$((i * 2))s"
    exit 0
  fi
  sleep 2
done
echo "✗ healthcheck failed — see: docker compose -f $COMPOSE_FILE logs"
exit 1

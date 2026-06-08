#!/usr/bin/env bash
# Roll an environment back to a previous image tag (PRD2 §13 rollback / continuous-verification
# failure strategy). Usage: infra/scripts/rollback.sh <env> <previous_image_tag>
set -euo pipefail

ENV="${1:?usage: rollback.sh <env> <previous_image_tag>}"
PREV_TAG="${2:?usage: rollback.sh <env> <previous_image_tag>}"

echo "→ rolling back env=$ENV to tag=$PREV_TAG"
# DB migrations must be backward-compatible (expand/contract) so a rollback never needs a
# down-migration — see docs/runbooks/release-gate.md. Image rollback only:
exec infra/scripts/deploy.sh "$ENV" "$PREV_TAG"

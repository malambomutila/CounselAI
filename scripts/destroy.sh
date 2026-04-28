#!/usr/bin/env bash
# Tear down the CounselAI showcase. Safe to re-run; idempotent.
#
# 1. Drain ECR (terraform destroy can't remove a repo with images unless
#    force_delete is set — we have it set, but emptying first makes the
#    destroy faster and the intent explicit).
# 2. terraform destroy.
# 3. Best-effort delete any lingering App Runner CloudWatch log groups.
#
# Pass --yes to skip the interactive confirmation.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd)"
TF_DIR="$REPO_ROOT/terraform"
ENV_FILE="$REPO_ROOT/.env"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "✗ $1 is required but not on PATH" >&2
    exit 1
  }
}

require terraform
require aws

read_env() {
  local key="$1"
  awk -v k="$key" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      sub(/^[[:space:]]+/, "")
      n = index($0, "=")
      if (n == 0) next
      key = substr($0, 1, n-1)
      gsub(/[[:space:]]+$/, "", key)
      if (key != k) next
      val = substr($0, n+1)
      sub(/^[[:space:]]+/, "", val)
      sub(/[[:space:]]+$/, "", val)
      if (val ~ /^".*"$/) val = substr(val, 2, length(val)-2)
      print val
      exit
    }
  ' "$ENV_FILE"
}

AWS_REGION="$(read_env DEFAULT_AWS_REGION 2>/dev/null || true)"
AWS_REGION="${AWS_REGION:-eu-west-2}"

# Confirmation gate — destruction is irreversible.
if [[ "${1:-}" != "--yes" ]]; then
  echo "About to destroy CounselAI infra in region $AWS_REGION:"
  echo "  - App Runner service"
  echo "  - DynamoDB table (data will be lost)"
  echo "  - ECR repository + all images"
  echo "  - IAM roles"
  read -r -p "Proceed? [y/N] " confirm
  if [[ "${confirm,,}" != "y" && "${confirm,,}" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# We need *some* value for the sensitive vars to satisfy terraform's variable
# requirements during destroy. The values are not used (no resource is
# created), but terraform still parses them.
export TF_VAR_openai_api_key="${TF_VAR_openai_api_key:-destroy-placeholder}"
export TF_VAR_clerk_publishable_key="${TF_VAR_clerk_publishable_key:-destroy-placeholder}"
export TF_VAR_clerk_secret_key="${TF_VAR_clerk_secret_key:-destroy-placeholder}"
export TF_VAR_aws_region="$AWS_REGION"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — empty ECR.
# ─────────────────────────────────────────────────────────────────────────────
ECR_URL="$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url 2>/dev/null || true)"
if [[ -n "$ECR_URL" ]]; then
  ECR_NAME="${ECR_URL##*/}"
  echo "▸ Emptying ECR repository: $ECR_NAME"
  IMAGE_IDS="$(aws ecr list-images \
    --repository-name "$ECR_NAME" \
    --region "$AWS_REGION" \
    --query 'imageIds[*]' \
    --output json 2>/dev/null || echo '[]')"
  if [[ "$IMAGE_IDS" != "[]" ]]; then
    aws ecr batch-delete-image \
      --repository-name "$ECR_NAME" \
      --region "$AWS_REGION" \
      --image-ids "$IMAGE_IDS" \
      >/dev/null
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — terraform destroy.
# ─────────────────────────────────────────────────────────────────────────────
echo "▸ terraform destroy"
terraform -chdir="$TF_DIR" destroy -input=false -auto-approve

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — best-effort log group cleanup.
# App Runner creates log groups outside terraform's awareness; they keep
# billing $0.50/GB-month forever if left.
# ─────────────────────────────────────────────────────────────────────────────
echo "▸ Cleaning up CloudWatch log groups"
LOG_GROUPS="$(aws logs describe-log-groups \
  --log-group-name-prefix /aws/apprunner/counselai \
  --region "$AWS_REGION" \
  --query 'logGroups[*].logGroupName' \
  --output text 2>/dev/null || true)"

for lg in $LOG_GROUPS; do
  echo "  delete $lg"
  aws logs delete-log-group --log-group-name "$lg" --region "$AWS_REGION" || true
done

echo
echo "✓ Destroy complete."

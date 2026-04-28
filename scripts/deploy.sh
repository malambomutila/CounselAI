#!/usr/bin/env bash
# Build → push → terraform apply for CounselAI.
#
# Reads .env at repo root, exports the secrets we care about as TF_VAR_*, then:
#   1. terraform init + targeted apply for ECR (so the repo URL exists),
#   2. docker build (linux/amd64) + ECR login + push,
#   3. full terraform apply (creates / updates DynamoDB + App Runner),
#   4. (optional) start a fresh App Runner deployment to pick up the new :latest,
#   5. echo the service URL.

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Locate repo root regardless of where the script is invoked from.
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd)"
TF_DIR="$REPO_ROOT/terraform"
ENV_FILE="$REPO_ROOT/.env"

cd "$REPO_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Sanity checks
# ─────────────────────────────────────────────────────────────────────────────
require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "✗ $1 is required but not on PATH" >&2
    exit 1
  }
}

require docker
require terraform
require aws

if [[ ! -f "$ENV_FILE" ]]; then
  echo "✗ Missing $ENV_FILE — copy .env.example to .env and fill in secrets." >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Parse .env and re-export the entries we care about as TF_VAR_*.
# Only the secrets-and-tweakable-config keys are mapped; anything else in .env
# is ignored.
# ─────────────────────────────────────────────────────────────────────────────
read_env() {
  local key="$1"
  # Match "KEY=value" with optional spaces around =, ignoring comments and
  # blanks. Strip surrounding quotes if present. Stops at first match.
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
      else if (val ~ /^'\''.*'\''$/) val = substr(val, 2, length(val)-2)
      print val
      exit
    }
  ' "$ENV_FILE"
}

require_env() {
  local key="$1"
  local val
  val="$(read_env "$key")"
  if [[ -z "$val" ]]; then
    echo "✗ $key is missing or empty in $ENV_FILE" >&2
    exit 1
  fi
  printf '%s' "$val"
}

OPENAI_API_KEY="$(require_env OPENAI_API_KEY)"
CLERK_PUBLISHABLE_KEY="$(require_env NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)"
CLERK_SECRET_KEY="$(require_env CLERK_SECRET_KEY)"
AWS_REGION="$(read_env DEFAULT_AWS_REGION)"
AWS_REGION="${AWS_REGION:-eu-west-2}"
AWS_ACCOUNT_ID="$(read_env AWS_ACCOUNT_ID)"
if [[ -z "$AWS_ACCOUNT_ID" ]]; then
  AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
fi

export TF_VAR_openai_api_key="$OPENAI_API_KEY"
export TF_VAR_clerk_publishable_key="$CLERK_PUBLISHABLE_KEY"
export TF_VAR_clerk_secret_key="$CLERK_SECRET_KEY"
export TF_VAR_aws_region="$AWS_REGION"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — terraform init + targeted ECR apply.
# We need the ECR repo to exist before we can docker push.
# ─────────────────────────────────────────────────────────────────────────────
echo "▸ terraform init"
terraform -chdir="$TF_DIR" init -upgrade -input=false

echo "▸ terraform apply (ECR only)"
terraform -chdir="$TF_DIR" apply -input=false -auto-approve \
  -target=aws_ecr_repository.this

ECR_URL="$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url)"
echo "  ECR: $ECR_URL"

# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — docker build + push.
# Forced linux/amd64 so the image runs on App Runner regardless of the build
# host architecture.
# ─────────────────────────────────────────────────────────────────────────────
echo "▸ docker login → ECR"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
      "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "▸ docker build"
docker build --platform linux/amd64 -t "$ECR_URL:latest" "$REPO_ROOT"

echo "▸ docker push"
docker push "$ECR_URL:latest"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — full terraform apply (DynamoDB + IAM + App Runner).
# ─────────────────────────────────────────────────────────────────────────────
echo "▸ terraform apply (full)"
terraform -chdir="$TF_DIR" apply -input=false -auto-approve

# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — kick a fresh deployment if the service already existed (so it
# pulls the image we just pushed instead of caching the previous :latest).
# auto_deployments_enabled is false by design, so we trigger by hand.
# ─────────────────────────────────────────────────────────────────────────────
SERVICE_ARN="$(terraform -chdir="$TF_DIR" output -raw app_runner_service_arn 2>/dev/null || true)"
if [[ -n "$SERVICE_ARN" ]]; then
  echo "▸ apprunner start-deployment"
  aws apprunner start-deployment \
    --service-arn "$SERVICE_ARN" \
    --region "$AWS_REGION" \
    >/dev/null || echo "  (start-deployment skipped — service may still be creating)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — echo URLs.
# ─────────────────────────────────────────────────────────────────────────────
APP_URL="$(terraform -chdir="$TF_DIR" output -raw app_runner_service_url)"
DDB_TABLE="$(terraform -chdir="$TF_DIR" output -raw dynamodb_table_name)"

echo
echo "✓ Deploy complete."
echo "  App URL:        $APP_URL"
echo "  DynamoDB table: $DDB_TABLE"
echo "  ECR:            $ECR_URL"
echo
echo "  Tail logs with:"
echo "    aws logs tail /aws/apprunner/${DDB_TABLE}/<id>/application --follow --region $AWS_REGION"

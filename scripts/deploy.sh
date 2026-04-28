#!/usr/bin/env bash
# Build → push → terraform apply for MoootCourt's EC2-oriented deployment flow.
#
# Reads .env at repo root, exports the secrets we care about as TF_VAR_*, then:
#   1. terraform init + targeted apply for the backend/frontend ECR repos,
#   2. docker build + push for backend and frontend images,
#   3. full terraform apply (ECR + IAM + optional EC2 / optional DynamoDB),
#   4. echo the image URIs and EC2 outputs for docker-compose deployment.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd)"
TF_DIR="$REPO_ROOT/terraform"
ENV_FILE="$REPO_ROOT/.env"

cd "$REPO_ROOT"

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

echo "▸ terraform init"
terraform -chdir="$TF_DIR" init -upgrade -input=false

echo "▸ terraform apply (ECR only)"
terraform -chdir="$TF_DIR" apply -input=false -auto-approve \
  -target=aws_ecr_repository.backend \
  -target=aws_ecr_repository.frontend

BACKEND_ECR_URL="$(terraform -chdir="$TF_DIR" output -raw backend_ecr_repository_url)"
FRONTEND_ECR_URL="$(terraform -chdir="$TF_DIR" output -raw frontend_ecr_repository_url)"

echo "  Backend ECR:  $BACKEND_ECR_URL"
echo "  Frontend ECR: $FRONTEND_ECR_URL"

echo "▸ docker login → ECR"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
      "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "▸ docker build (backend)"
docker build --platform linux/amd64 -t "$BACKEND_ECR_URL:latest" "$REPO_ROOT"

echo "▸ docker push (backend)"
docker push "$BACKEND_ECR_URL:latest"

echo "▸ docker build (frontend)"
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="$CLERK_PUBLISHABLE_KEY" \
  -t "$FRONTEND_ECR_URL:latest" "$REPO_ROOT/frontend"

echo "▸ docker push (frontend)"
docker push "$FRONTEND_ECR_URL:latest"

echo "▸ terraform apply (full)"
terraform -chdir="$TF_DIR" apply -input=false -auto-approve

EC2_PUBLIC_IP="$(terraform -chdir="$TF_DIR" output -raw ec2_public_ip 2>/dev/null || true)"
EC2_PUBLIC_DNS="$(terraform -chdir="$TF_DIR" output -raw ec2_public_dns 2>/dev/null || true)"
INSTANCE_PROFILE="$(terraform -chdir="$TF_DIR" output -raw ec2_instance_profile_name)"
SECURITY_GROUP_ID="$(terraform -chdir="$TF_DIR" output -raw ec2_security_group_id 2>/dev/null || true)"
DDB_TABLE="$(terraform -chdir="$TF_DIR" output -raw dynamodb_table_name 2>/dev/null || true)"

echo
echo "✓ Deploy preparation complete."
echo "  Backend image:         $BACKEND_ECR_URL:latest"
echo "  Frontend image:        $FRONTEND_ECR_URL:latest"
echo "  Instance profile:      $INSTANCE_PROFILE"
echo "  Security group id:     ${SECURITY_GROUP_ID:-<not-created>}"
echo "  DynamoDB table:        ${DDB_TABLE:-<disabled>}"
echo "  EC2 public ip:         ${EC2_PUBLIC_IP:-<not-created>}"
echo "  EC2 public dns:        ${EC2_PUBLIC_DNS:-<not-created>}"
echo
echo "  For the EC2 host, set:"
echo "    COUNSELAI_BACKEND_IMAGE=$BACKEND_ECR_URL:latest"
echo "    COUNSELAI_FRONTEND_IMAGE=$FRONTEND_ECR_URL:latest"

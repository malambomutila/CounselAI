# ──────────────────────────────────────────────────────────────────────────────
# Non-secret config — settable in terraform.tfvars
# ──────────────────────────────────────────────────────────────────────────────

variable "project" {
  description = "Project name; used as a prefix for all named resources."
  type        = string
  default     = "counselai"
}

variable "env" {
  description = "Environment slug (dev / staging / prod). Joined with project to form the resource name prefix."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-west-2"
}

variable "log_level" {
  description = "LOG_LEVEL passed to the running container."
  type        = string
  default     = "INFO"
}

variable "openai_model" {
  description = "OpenAI model identifier the agents use. Spec target is gpt-4.1."
  type        = string
  default     = "gpt-4.1"
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS endpoint for the dev instance. Public."
  type        = string
  default     = "https://winning-weevil-72.clerk.accounts.dev/.well-known/jwks.json"
}

variable "clerk_frontend_api_url" {
  description = "Clerk frontend API base URL for the dev instance. Public."
  type        = string
  default     = "https://winning-weevil-72.clerk.accounts.dev"
}

# ──────────────────────────────────────────────────────────────────────────────
# Secrets — sourced from TF_VAR_* env vars by scripts/deploy.sh.
# Never set these in terraform.tfvars; never commit real values.
# ──────────────────────────────────────────────────────────────────────────────

variable "openai_api_key" {
  description = "OpenAI API key. Sourced from TF_VAR_openai_api_key (set from .env at deploy time)."
  type        = string
  sensitive   = true
}

variable "clerk_publishable_key" {
  description = "Clerk publishable key. Frontend-visible but injected via TF_VAR for parity with the rest of the secrets."
  type        = string
  sensitive   = true
}

variable "clerk_secret_key" {
  description = "Clerk backend secret key. Sourced from TF_VAR_clerk_secret_key."
  type        = string
  sensitive   = true
}

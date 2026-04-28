# ──────────────────────────────────────────────────────────────────────────────
# Non-secret config — settable in terraform.tfvars
# ──────────────────────────────────────────────────────────────────────────────

variable "project" {
  description = "Project name; used as a prefix for all named resources."
  type        = string
  default     = "counselai"
}

variable "env" {
  description = "Environment slug (dev / staging / prod)."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-west-2"
}

variable "log_level" {
  description = "Application log level."
  type        = string
  default     = "INFO"
}

variable "openai_model" {
  description = "OpenAI model identifier the agents use."
  type        = string
  default     = "gpt-4.1"
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS endpoint. Public."
  type        = string
  default     = "https://winning-weevil-72.clerk.accounts.dev/.well-known/jwks.json"
}

variable "clerk_frontend_api_url" {
  description = "Clerk frontend API base URL. Public."
  type        = string
  default     = "https://winning-weevil-72.clerk.accounts.dev"
}

variable "clerk_authorized_parties" {
  description = "Comma-separated origins allowed in Clerk JWT azp claim."
  type        = string
  default     = ""
}

variable "create_dynamodb_table" {
  description = "Whether to provision DynamoDB for the optional cloud store."
  type        = bool
  default     = false
}

variable "create_ec2_instance" {
  description = "Whether Terraform should also create the EC2 host."
  type        = bool
  default     = false
}

variable "ec2_instance_type" {
  description = "EC2 instance type for the app host."
  type        = string
  default     = "t3.small"
}

variable "ec2_ami_id" {
  description = "Optional AMI override. Empty uses latest Amazon Linux 2023."
  type        = string
  default     = ""
}

variable "ec2_vpc_id" {
  description = "Optional VPC override. Empty uses the default VPC."
  type        = string
  default     = ""
}

variable "ec2_subnet_id" {
  description = "Optional subnet override. Empty uses the first default subnet."
  type        = string
  default     = ""
}

variable "ec2_key_name" {
  description = "Existing EC2 key pair name for SSH access."
  type        = string
  default     = ""
}

variable "ec2_root_volume_size_gb" {
  description = "Root EBS volume size in GB."
  type        = number
  default     = 20
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH into the EC2 instance."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ──────────────────────────────────────────────────────────────────────────────
# Secrets — sourced from TF_VAR_* env vars by scripts/deploy.sh.
# ──────────────────────────────────────────────────────────────────────────────

variable "openai_api_key" {
  description = "OpenAI API key."
  type        = string
  sensitive   = true
}

variable "clerk_publishable_key" {
  description = "Clerk publishable key."
  type        = string
  sensitive   = true
}

variable "clerk_secret_key" {
  description = "Clerk backend secret key."
  type        = string
  sensitive   = true
}

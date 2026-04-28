terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state — fine for a throwaway showcase. terraform.tfstate is gitignored.
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  name = "${var.project}-${var.env}"

  common_tags = {
    Project   = var.project
    Env       = var.env
    ManagedBy = "terraform"
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# ECR — image lives here; App Runner pulls :latest each deploy.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "this" {
  name                 = local.name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = local.common_tags
}

# ─────────────────────────────────────────────────────────────────────────────
# DynamoDB — single-table store for conversations + turns.
# Schema (see CLAUDE.md "Storage: DynamoDB single-table"):
#   PK = USER#{user_id}
#   SK = CONV#{conv_id}                    → conversation header
#   SK = CONV#{conv_id}#TURN#{turn_n}      → one pipeline run
# On-demand billing → ~$0 idle, pennies under demo load.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "this" {
  name         = local.name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  point_in_time_recovery {
    enabled = false
  }

  tags = local.common_tags
}

# ─────────────────────────────────────────────────────────────────────────────
# IAM — App Runner needs two roles:
#   1. access_role — assumed by build.apprunner to pull from ECR.
#   2. instance_role — assumed by tasks.apprunner; what the running container
#      gets credentials for. Boto3 inside the container picks this up.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_iam_role" "apprunner_access" {
  name = "${local.name}-apprunner-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "build.apprunner.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "apprunner_access_ecr" {
  role       = aws_iam_role.apprunner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_iam_role" "apprunner_instance" {
  name = "${local.name}-apprunner-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "tasks.apprunner.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

# Scoped DynamoDB access for the running container — read/write only this table.
resource "aws_iam_role_policy" "apprunner_dynamodb" {
  name = "${local.name}-dynamodb"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem",
      ]
      Resource = aws_dynamodb_table.this.arn
    }]
  })
}

# ─────────────────────────────────────────────────────────────────────────────
# App Runner service
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_apprunner_service" "this" {
  service_name = local.name

  source_configuration {
    auto_deployments_enabled = false

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.this.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"

        # Secrets are passed in via TF_VAR_* at deploy time — never committed.
        runtime_environment_variables = {
          # LLM
          OPENAI_API_KEY = var.openai_api_key
          OPENAI_MODEL   = var.openai_model

          # Auth (Clerk)
          NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = var.clerk_publishable_key
          CLERK_SECRET_KEY                  = var.clerk_secret_key
          CLERK_JWKS_URL                    = var.clerk_jwks_url
          CLERK_FRONTEND_API_URL            = var.clerk_frontend_api_url
          # Same-origin in App Runner: the only legitimate ``azp`` is the
          # service's own URL. Set after the first apply (chicken-and-egg —
          # the URL is unknown until creation), then re-apply.
          CLERK_AUTHORIZED_PARTIES = var.clerk_authorized_parties

          # Storage
          DDB_TABLE  = aws_dynamodb_table.this.name
          DDB_REGION = var.aws_region

          # App
          GRADIO_SERVER_NAME = "0.0.0.0"
          GRADIO_SERVER_PORT = "8080"
          LOG_LEVEL          = var.log_level
        }
      }
    }
  }

  instance_configuration {
    cpu               = "1 vCPU"
    memory            = "2 GB"
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 20
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = local.common_tags
}

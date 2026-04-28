output "ecr_repository_url" {
  description = "ECR repo URL — used by scripts/deploy.sh to tag and push the image."
  value       = aws_ecr_repository.this.repository_url
}

output "app_runner_service_url" {
  description = "Public HTTPS URL for the deployed App Runner service."
  value       = "https://${aws_apprunner_service.this.service_url}"
}

output "app_runner_service_arn" {
  description = "ARN of the App Runner service (use with aws apprunner describe-service / start-deployment)."
  value       = aws_apprunner_service.this.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table the app uses for conversations and turns."
  value       = aws_dynamodb_table.this.name
}

output "aws_region" {
  description = "AWS region the service was deployed to."
  value       = var.aws_region
}

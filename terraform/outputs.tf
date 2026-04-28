output "backend_ecr_repository_url" {
  description = "ECR repo URL for the backend image."
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_ecr_repository_url" {
  description = "ECR repo URL for the frontend image."
  value       = aws_ecr_repository.frontend.repository_url
}

output "dynamodb_table_name" {
  description = "Optional DynamoDB table name."
  value       = var.create_dynamodb_table ? aws_dynamodb_table.this[0].name : ""
}

output "ec2_instance_profile_name" {
  description = "IAM instance profile to attach to a manually-created EC2 host."
  value       = aws_iam_instance_profile.ec2.name
}

output "ec2_security_group_id" {
  description = "Security group for the app host."
  value       = var.create_ec2_instance ? aws_security_group.ec2[0].id : ""
}

output "ec2_public_ip" {
  description = "Public IP of the Terraform-managed EC2 instance, if created."
  value       = var.create_ec2_instance ? aws_instance.app[0].public_ip : ""
}

output "ec2_public_dns" {
  description = "Public DNS of the Terraform-managed EC2 instance, if created."
  value       = var.create_ec2_instance ? aws_instance.app[0].public_dns : ""
}

output "aws_region" {
  description = "AWS region."
  value       = var.aws_region
}

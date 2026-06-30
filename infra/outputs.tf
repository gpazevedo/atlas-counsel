output "alb_dns_name" {
  description = "ALB DNS name — point your MCP client here"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for pushing images"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service" {
  description = "ECS service name"
  value       = aws_ecs_service.app.name
}

output "github_deploy_role_arn" {
  description = "IAM role for GitHub Actions OIDC — set as the AWS_ROLE_ARN repo variable"
  value       = aws_iam_role.github_deploy.arn
}

output "mcp_endpoint" {
  description = "ALB DNS name. The MCP endpoint is https://<your-domain>/mcp — the ACM cert won't match this *.elb.amazonaws.com name, so front it with the domain the cert covers."
  value       = aws_lb.main.dns_name
}

output "mcp_api_key_secret_arn" {
  description = "Secrets Manager ARN holding the generated MCP API key — retrieve with: aws secretsmanager get-secret-value --secret-id <arn>"
  value       = aws_secretsmanager_secret.mcp_api_key.arn
}

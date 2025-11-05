output "backend_url" {
  description = "Backend API URL (App Runner)"
  value       = "https://${aws_apprunner_service.backend.service_url}"
}

output "worker_url" {
  description = "Worker service URL (App Runner)"
  value       = "https://${aws_apprunner_service.worker.service_url}"
}

output "frontend_url" {
  description = "Frontend URL (Amplify)"
  value       = "https://main.${aws_amplify_app.frontend.default_domain}"
}

output "amplify_app_id" {
  description = "Amplify App ID"
  value       = aws_amplify_app.frontend.id
}

output "ecr_repository_url" {
  description = "ECR repository URL for backend"
  value       = aws_ecr_repository.backend.repository_url
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
  sensitive   = true
}

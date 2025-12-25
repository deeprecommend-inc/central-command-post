# =============================================================================
# Outputs for Minimal Infrastructure
# =============================================================================

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.main.id
}

output "instance_public_ip" {
  description = "EC2 instance public IP (Elastic IP)"
  value       = aws_eip.main.public_ip
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "http://${aws_eip.main.public_ip}:3006"
}

output "backend_url" {
  description = "Backend API URL"
  value       = "http://${aws_eip.main.public_ip}:8006"
}

output "ssh_command" {
  description = "SSH command to connect to instance"
  value       = var.ssh_public_key != "" ? "ssh -i <your-key.pem> ec2-user@${aws_eip.main.public_ip}" : "Use SSM Session Manager: aws ssm start-session --target ${aws_instance.main.id}"
}

output "ssm_command" {
  description = "SSM Session Manager command"
  value       = "aws ssm start-session --target ${aws_instance.main.id} --region ${var.aws_region}"
}

output "ecr_repository_url" {
  description = "ECR repository URL (if enabled)"
  value       = var.use_ecr ? aws_ecr_repository.app[0].repository_url : "ECR disabled - using Docker Hub"
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost"
  value       = <<-EOT
    Estimated Monthly Cost (${var.aws_region}):
    - EC2 ${var.instance_type}: ~$8.50/month (FREE with free tier)
    - EBS ${var.root_volume_size}GB gp3: ~$${var.root_volume_size * 0.08}/month
    - Elastic IP: FREE (when attached)
    - Data Transfer: Variable

    Total: ~$10-15/month (or FREE with free tier for first 12 months)

    Compare to full ECS/Fargate setup: ~$100-150/month
  EOT
}

# =============================================================================
# Variables for Minimal Infrastructure
# =============================================================================

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-northeast-1"  # Tokyo - change to us-east-1 for cheapest
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "sns-agent"
}

variable "instance_type" {
  description = "EC2 instance type (t3.micro is free tier eligible)"
  type        = string
  default     = "t3.micro"  # Free tier: 750 hours/month for 12 months

  # Other cheap options:
  # - t3.micro:  2 vCPU, 1GB RAM  - ~$8.50/month
  # - t3.small:  2 vCPU, 2GB RAM  - ~$17/month
  # - t3.medium: 2 vCPU, 4GB RAM  - ~$34/month
  # - t3a.micro: 2 vCPU, 1GB RAM  - ~$7.50/month (AMD, slightly cheaper)
}

variable "root_volume_size" {
  description = "Root EBS volume size in GB"
  type        = number
  default     = 20  # Minimum practical size for Docker + app

  # Note: 8GB is minimum for Amazon Linux 2023
  # 20GB recommended for Docker images and SQLite DB
}

variable "secret_key" {
  description = "Secret key for application (used for encryption)"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for EC2 access (optional, leave empty to disable SSH key)"
  type        = string
  default     = ""
}

variable "ssh_allowed_cidr" {
  description = "CIDR blocks allowed for SSH access"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Restrict this in production!
}

variable "use_ecr" {
  description = "Use ECR for container images (set to false to use Docker Hub)"
  type        = bool
  default     = false  # Docker Hub is free and avoids ECR costs
}

# =============================================================================
# Optional: Spot Instance Configuration (for even more savings)
# =============================================================================

variable "use_spot_instance" {
  description = "Use spot instance for up to 90% cost savings (may be interrupted)"
  type        = bool
  default     = false
}

variable "spot_max_price" {
  description = "Maximum hourly price for spot instance"
  type        = string
  default     = "0.005"  # About 50% of on-demand price
}

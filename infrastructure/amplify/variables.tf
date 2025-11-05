variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "sns-orchestrator"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "sns_user"
  sensitive   = true
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Secret key for application"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_repo_url" {
  description = "GitHub repository URL for Amplify (optional)"
  type        = string
  default     = ""
}

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

variable "environment" {
  description = "Environment (development, staging, production)"
  type        = string
  default     = "production"
}

variable "github_repo_url" {
  description = "GitHub repository URL for Amplify"
  type        = string
  default     = ""
}

variable "github_access_token" {
  description = "GitHub personal access token for Amplify"
  type        = string
  default     = ""
  sensitive   = true
}

variable "branch_name" {
  description = "Git branch name to deploy"
  type        = string
  default     = "main"
}

variable "enable_auto_build" {
  description = "Enable automatic builds on git push"
  type        = bool
  default     = true
}

variable "backend_api_url" {
  description = "Backend API URL (e.g., https://api.example.com)"
  type        = string
}

variable "custom_domain" {
  description = "Custom domain for Amplify app (optional)"
  type        = string
  default     = ""
}

variable "subdomain_prefix" {
  description = "Subdomain prefix for custom domain (empty for root domain)"
  type        = string
  default     = ""
}

variable "enable_www_redirect" {
  description = "Enable www subdomain redirect"
  type        = bool
  default     = false
}

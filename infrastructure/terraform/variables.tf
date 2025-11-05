variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-northeast-1" # 東京リージョン
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

variable "youtube_client_id" {
  description = "YouTube OAuth client ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "youtube_client_secret" {
  description = "YouTube OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "x_client_id" {
  description = "X (Twitter) OAuth client ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "x_client_secret" {
  description = "X (Twitter) OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "instagram_client_id" {
  description = "Instagram OAuth client ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "instagram_client_secret" {
  description = "Instagram OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "tiktok_client_id" {
  description = "TikTok OAuth client ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "tiktok_client_secret" {
  description = "TikTok OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}

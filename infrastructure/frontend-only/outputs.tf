output "amplify_app_id" {
  description = "Amplify App ID"
  value       = aws_amplify_app.frontend.id
}

output "amplify_app_arn" {
  description = "Amplify App ARN"
  value       = aws_amplify_app.frontend.arn
}

output "default_domain" {
  description = "Default Amplify domain"
  value       = aws_amplify_app.frontend.default_domain
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "https://${var.branch_name}.${aws_amplify_app.frontend.default_domain}"
}

output "branch_name" {
  description = "Deployed branch name"
  value       = aws_amplify_branch.main.branch_name
}

output "custom_domain_url" {
  description = "Custom domain URL (if configured)"
  value       = var.custom_domain != "" ? "https://${var.subdomain_prefix != "" ? "${var.subdomain_prefix}." : ""}${var.custom_domain}" : null
}

output "amplify_console_url" {
  description = "Amplify Console URL"
  value       = "https://console.aws.amazon.com/amplify/home?region=${var.aws_region}#/${aws_amplify_app.frontend.id}"
}

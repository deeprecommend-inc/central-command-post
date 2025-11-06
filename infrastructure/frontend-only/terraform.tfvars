# AWS Configuration
aws_region   = "ap-northeast-1"
project_name = "sns-orchestrator"
environment  = "development"

# GitHub Configuration (オプション: GitHub連携を使う場合)
# 本番環境では GitHub連携を推奨
github_repo_url      = "https://github.com/deeprecommend-inc/sns-agent"
github_access_token  = "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"
branch_name          = "main"
enable_auto_build    = true  # GitHub連携を有効化

# Backend API URL (必須)
# 開発環境ではローカルバックエンドを指定
# 本番環境では App Runner の URL を指定してください
backend_api_url = "http://localhost:8006"

# Custom Domain (オプション)
custom_domain        = ""  # 例: "example.com"
subdomain_prefix     = ""  # 例: "app" → app.example.com
enable_www_redirect  = false

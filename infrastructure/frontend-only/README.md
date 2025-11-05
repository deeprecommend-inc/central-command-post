# フロントエンド専用デプロイ - Terraform設定

このディレクトリには、フロントエンド（Next.js）のみをAWS Amplifyにデプロイするための Terraform 設定が含まれています。

## 📋 前提条件

- AWS CLI がインストールされ、認証情報が設定されていること
- Terraform >= 1.0 がインストールされていること
- Node.js と npm がインストールされていること
- バックエンドAPIが既にデプロイされていること（App Runner等）

## 🚀 クイックスタート

### 1. 設定ファイルの準備

```bash
# terraform.tfvarsを作成
cp terraform.tfvars.example terraform.tfvars

# 設定を編集
vim terraform.tfvars
```

**必須設定:**
- `backend_api_url`: バックエンドAPIのURL（例: `https://xxx.ap-northeast-1.awsapprunner.com`）

**オプション設定:**
- `github_repo_url`: GitHubリポジトリURL（GitHub連携を使う場合）
- `github_access_token`: GitHubアクセストークン
- `custom_domain`: カスタムドメイン

### 2. デプロイスクリプトを使用（推奨）

```bash
# プロジェクトルートから実行
cd /usr/src/script/sns-agents

# Terraformでデプロイ
./deploy-frontend.sh terraform-apply
```

### 3. 手動でTerraformを実行

```bash
cd infrastructure/frontend-only

# 初期化
terraform init

# プラン確認
terraform plan

# 適用
terraform apply
```

## 📦 リソース構成

デプロイされるAWSリソース:

- **AWS Amplify App**: Next.jsアプリケーションのホスティング
- **IAM Role**: Amplifyサービスロール
- **Amplify Branch**: mainブランチ（または指定ブランチ）
- **Custom Domain** (オプション): カスタムドメインの設定

## 🔧 設定オプション

### variables.tf で定義されている変数

| 変数名 | 説明 | デフォルト | 必須 |
|--------|------|-----------|------|
| `aws_region` | AWSリージョン | `ap-northeast-1` | いいえ |
| `project_name` | プロジェクト名 | `sns-orchestrator` | いいえ |
| `environment` | 環境名 | `production` | いいえ |
| `backend_api_url` | バックエンドAPIのURL | - | **はい** |
| `github_repo_url` | GitHubリポジトリURL | `""` | いいえ |
| `github_access_token` | GitHubアクセストークン | `""` | いいえ |
| `branch_name` | デプロイするブランチ名 | `main` | いいえ |
| `enable_auto_build` | 自動ビルドを有効化 | `true` | いいえ |
| `custom_domain` | カスタムドメイン | `""` | いいえ |
| `subdomain_prefix` | サブドメインプレフィックス | `""` | いいえ |
| `enable_www_redirect` | wwwリダイレクトを有効化 | `false` | いいえ |

### terraform.tfvars の例

```hcl
# 基本設定
aws_region   = "ap-northeast-1"
project_name = "sns-orchestrator"
environment  = "production"

# バックエンドAPI（必須）
backend_api_url = "https://xxx.ap-northeast-1.awsapprunner.com"

# GitHub連携（オプション）
github_repo_url      = "https://github.com/your-username/sns-agents"
github_access_token  = "ghp_xxxxxxxxxxxxxxxxxxxx"
branch_name          = "main"
enable_auto_build    = true

# カスタムドメイン（オプション）
custom_domain        = "example.com"
subdomain_prefix     = "app"  # app.example.com
enable_www_redirect  = true
```

## 📤 デプロイ出力

デプロイ後、以下の情報が出力されます:

```bash
terraform output
```

- `amplify_app_id`: Amplify App ID
- `amplify_app_arn`: Amplify App ARN
- `default_domain`: デフォルトドメイン
- `frontend_url`: フロントエンドURL
- `branch_name`: デプロイされたブランチ名
- `custom_domain_url`: カスタムドメインURL（設定時）
- `amplify_console_url`: AmplifyコンソールURL

## 🔄 GitHub連携デプロイ（推奨）

GitHub連携により、コードのプッシュで自動デプロイが可能になります。

### 手順

1. **GitHubアクセストークンの作成**
   - GitHub → Settings → Developer settings → Personal access tokens
   - `repo` スコープを付与

2. **terraform.tfvars に設定**
   ```hcl
   github_repo_url     = "https://github.com/your-username/sns-agents"
   github_access_token = "ghp_xxxxxxxxxxxxxxxxxxxx"
   ```

3. **Terraform適用**
   ```bash
   ./deploy-frontend.sh terraform-apply
   ```

4. **コードをプッシュ**
   ```bash
   git push origin main
   ```
   → 自動でビルド＆デプロイが開始されます

## 🛠️ トラブルシューティング

### ビルドが失敗する

**原因**: amplify.yamlの設定が正しくない

**解決策**:
```bash
# amplify.yamlを確認
cat ../../amplify.yaml

# ビルド設定が正しいか確認
# baseDirectory: frontend/.next
# files: '**/*'
```

### バックエンドAPIに接続できない

**原因**: NEXT_PUBLIC_API_URL が正しく設定されていない

**解決策**:
```bash
# Amplifyコンソールで環境変数を確認
# https://console.aws.amazon.com/amplify/home

# または terraform.tfvars で backend_api_url を確認
```

### カスタムドメインが動作しない

**原因**: DNS設定が完了していない

**解決策**:
```bash
# Amplifyコンソールで DNS レコードを確認
# Route53 または 使用しているDNSプロバイダーで設定
```

## 🗑️ リソースの削除

```bash
# デプロイスクリプトを使用
./deploy-frontend.sh terraform-destroy

# または手動で
cd infrastructure/frontend-only
terraform destroy
```

## 📚 参考リンク

- [AWS Amplify Hosting](https://docs.aws.amazon.com/amplify/latest/userguide/welcome.html)
- [Next.js on AWS Amplify](https://docs.aws.amazon.com/amplify/latest/userguide/server-side-rendering-amplify.html)
- [Terraform AWS Amplify Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/amplify_app)

## 💡 ベストプラクティス

1. **GitHub連携を使用する**: 最も簡単で推奨される方法
2. **環境変数を活用する**: バックエンドURLやAPIキーは環境変数で管理
3. **カスタムドメインを設定する**: ブランディングとSEOのため
4. **自動ビルドを有効化する**: CI/CDパイプラインの自動化
5. **プレビューデプロイを活用する**: PRごとにプレビュー環境を自動作成

## 🔐 セキュリティ

- **terraform.tfvars**: Gitにコミットしないこと（.gitignoreに追加済み）
- **GitHubアクセストークン**: 適切なスコープのみを付与
- **環境変数**: 機密情報は環境変数で管理
- **IAMロール**: 最小権限の原則に従う

## 📝 メンテナンス

### Terraform state の管理

本番環境では S3 backend を推奨:

```hcl
terraform {
  backend "s3" {
    bucket = "your-terraform-state-bucket"
    key    = "sns-orchestrator/frontend/terraform.tfstate"
    region = "ap-northeast-1"
  }
}
```

### バージョンアップ

```bash
# Terraformプロバイダーのアップデート
terraform init -upgrade

# 変更を確認
terraform plan
```

# SNS Orchestrator - AWS Amplify Deployment Guide (超最安値構成)

## 概要

AWS Amplify + App Runnerを使用した**超最安値構成**でのデプロイガイドです。

### なぜAmplify + App Runner?

| 項目 | ECS Fargate | Amplify + App Runner |
|------|-------------|---------------------|
| 月額コスト | $60-85 | **$45-65** |
| デプロイ難易度 | 中 | **易** |
| 管理コスト | ALB, ECS管理必要 | **ほぼゼロ** |
| スケーリング | 手動設定 | **完全自動** |
| CI/CD | 別途設定必要 | **組み込み済み** |

### コスト内訳

| リソース | スペック | 月額概算 |
|---------|---------|---------|
| AWS Amplify (Frontend) | 従量課金 | $0.50-2 |
| App Runner (Backend) | 1 vCPU, 2GB | $12-15 |
| App Runner (Worker) | 0.25 vCPU, 0.5GB | $3-5 |
| RDS PostgreSQL | db.t4g.micro, 20GB | $15-20 |
| ElastiCache Redis | cache.t4g.micro | $12-15 |
| データ転送 | - | $3-5 |
| **合計** | | **$45-65** |

## クイックスタート

### 1. 準備

```bash
# AWS CLIとTerraformのインストール確認
terraform --version  # >= 1.0
aws --version        # >= 2.0

# AWS認証設定
aws configure
# Region: ap-northeast-1 (東京) 推奨
```

### 2. 設定

```bash
# 設定ファイルの作成
cp infrastructure/amplify/terraform.tfvars.example \
   infrastructure/amplify/terraform.tfvars

# 編集
vi infrastructure/amplify/terraform.tfvars
```

**必須項目**:
```hcl
db_password = "YourStrongPassword123!"
secret_key = "your-random-secret-key-here"
```

### 3. デプロイ

```bash
# インフラのデプロイ (10-15分)
./deploy-amplify.sh init
./deploy-amplify.sh apply

# Backendイメージのビルドとプッシュ (5-10分)
./deploy-amplify.sh build

# App Runnerサービスの再デプロイ (3-5分)
./deploy-amplify.sh redeploy
```

### 4. フロントエンドのデプロイ

#### オプションA: GitHubから自動デプロイ (推奨)

1. [Amplify Console](https://console.aws.amazon.com/amplify/home) にアクセス
2. デプロイされたアプリを選択
3. "Connect repository" をクリック
4. GitHubリポジトリを選択して接続
5. mainブランチを選択
6. ビルド設定を確認 (自動生成される)
7. デプロイ開始

#### オプションB: 手動デプロイ

```bash
cd frontend
npm run build
cd .next
zip -r frontend.zip ./*

# Amplifyコンソールから手動アップロード
```

### 5. 確認

```bash
# デプロイ情報の確認
cd infrastructure/amplify
terraform output

# アクセス
# Backend: https://xxxxx.awsapprunner.com
# Frontend: https://main.xxxxx.amplifyapp.com
```

## 詳細設定

### データベース初期化

初回デプロイ後、データベースのテーブルを作成:

```bash
# App Runnerサービスのログを確認
aws logs tail /aws/apprunner/sns-orchestrator-backend --follow

# 注: App Runnerは現在SSHアクセス不可
# 代わりに、初期化エンドポイントをAPIに追加するか、
# ローカルから直接接続する必要があります
```

**ローカルから初期化** (VPCアクセスが必要):
```bash
# RDSをパブリックアクセス可能に一時的に変更
# または、EC2踏み台サーバー経由でアクセス

export DATABASE_URL="postgresql+asyncpg://sns_user:password@<rds-endpoint>/sns_orchestrator"
python -c "from app.models.database import init_db; import asyncio; asyncio.run(init_db())"
```

### 環境変数の追加

API キーなどの環境変数を追加する場合:

```bash
# Terraformファイルを編集
vi infrastructure/amplify/main.tf

# aws_apprunner_service.backend の runtime_environment_variables に追加
runtime_environment_variables = {
  DATABASE_URL = "..."
  REDIS_URL = "..."
  SECRET_KEY = var.secret_key
  ANTHROPIC_API_KEY = var.anthropic_api_key
  # 追加の環境変数
  YOUTUBE_CLIENT_ID = var.youtube_client_id
  YOUTUBE_CLIENT_SECRET = var.youtube_client_secret
}

# 再デプロイ
./deploy-amplify.sh apply
./deploy-amplify.sh redeploy
```

### カスタムドメインの設定

#### Amplify (Frontend)

1. Amplifyコンソールでアプリを選択
2. "Domain management" → "Add domain"
3. ドメインを入力 (例: app.example.com)
4. DNS設定に従ってCNAMEレコードを追加

#### App Runner (Backend)

1. App Runnerコンソールでサービスを選択
2. "Custom domains" → "Link domain"
3. ドメインを入力 (例: api.example.com)
4. DNS設定に従ってCNAMEレコードを追加

## コマンドリファレンス

### ./deploy-amplify.sh コマンド

```bash
# 初期化
./deploy-amplify.sh init

# デプロイ計画の確認
./deploy-amplify.sh plan

# インフラのデプロイ
./deploy-amplify.sh apply

# Backendイメージのビルドとプッシュ
./deploy-amplify.sh build

# App Runnerサービスの再デプロイ
./deploy-amplify.sh redeploy

# リソースの削除
./deploy-amplify.sh destroy

# 状態確認
./deploy-amplify.sh status

# コスト概算
./deploy-amplify.sh cost

# ヘルプ
./deploy-amplify.sh help
```

## トラブルシューティング

### App Runnerサービスが起動しない

**原因**: イメージが存在しない、環境変数エラー、VPC接続エラー

**確認**:
```bash
# App Runnerログの確認
aws logs tail /aws/apprunner/sns-orchestrator-backend --follow

# サービス状態の確認
aws apprunner describe-service \
  --service-arn <service-arn>
```

**解決策**:
1. `./deploy-amplify.sh build` でイメージを再ビルド
2. `./deploy-amplify.sh redeploy` でサービスを再デプロイ
3. 環境変数の確認

### データベース接続エラー

**原因**: VPC Connector設定、セキュリティグループ

**確認**:
```bash
# RDSエンドポイント確認
cd infrastructure/amplify
terraform output rds_endpoint

# VPC Connector確認
aws apprunner list-vpc-connectors
```

**解決策**:
1. VPC ConnectorにRDSのセキュリティグループが含まれているか確認
2. セキュリティグループでVPC内(10.0.0.0/16)からのポート5432が許可されているか確認

### Amplifyビルドエラー

**原因**: ビルド設定、環境変数、依存関係

**確認**:
```bash
# Amplifyコンソールでビルドログを確認
# または
aws amplify list-jobs --app-id <app-id> --branch-name main
```

**解決策**:
1. `amplify.yml` または build_spec の確認
2. 環境変数の確認
3. package.jsonの依存関係確認

### コストが予想より高い

**確認**:
```bash
# Cost Explorerで確認
# https://console.aws.amazon.com/cost-management/home

# 主な確認ポイント:
# - App Runnerのアクティブ時間
# - Amplifyのビルド回数・ホスティング容量
# - データ転送量
```

**解決策**:
1. App Runnerのプロビジョニングインスタンス数を最小化
2. Amplifyのビルド回数を削減 (手動トリガーに変更)
3. 不要なリソースを削除

## 更新手順

### コードの更新

#### Backend/Worker

```bash
# 1. コードを変更
# 2. イメージを再ビルド
./deploy-amplify.sh build

# 3. サービスを再デプロイ
./deploy-amplify.sh redeploy
```

#### Frontend

**GitHubから自動デプロイの場合**:
```bash
git push origin main
# Amplifyが自動的にビルド・デプロイ
```

**手動デプロイの場合**:
```bash
cd frontend
npm run build
# Amplifyコンソールから手動アップロード
```

### インフラの更新

```bash
# Terraformファイルを編集
vi infrastructure/amplify/main.tf

# プランの確認
./deploy-amplify.sh plan

# 適用
./deploy-amplify.sh apply
```

## 本番環境への移行

現在の構成は開発・テスト用の最安値構成です。本番環境では以下を検討してください:

### 1. RDS Multi-AZ

```hcl
# infrastructure/amplify/main.tf
resource "aws_db_instance" "postgres" {
  # ...
  multi_az = true
}
```

**コスト**: +100% (月額 約$30-40)

### 2. ElastiCache Multi-AZ

```hcl
resource "aws_elasticache_cluster" "redis" {
  # ...
  automatic_failover_enabled = true
  num_cache_nodes            = 2
}
```

**コスト**: +100% (月額 約$24-30)

### 3. App Runnerインスタンス数増加

```hcl
resource "aws_apprunner_service" "backend" {
  # ...
  instance_configuration {
    cpu    = "1 vCPU"
    memory = "2 GB"
    instance_role_arn = "..." # 追加
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.backend.arn
}

resource "aws_apprunner_auto_scaling_configuration_version" "backend" {
  auto_scaling_configuration_name = "backend-autoscaling"
  max_concurrency = 100
  max_size        = 10  # 最大インスタンス数
  min_size        = 2   # 最小インスタンス数
}
```

**コスト**: 約2-10倍 (トラフィックに応じて)

### 4. HTTPS証明書

App RunnerとAmplifyは自動的にHTTPSを提供するため、追加設定不要です。

### 5. WAF (Web Application Firewall)

```hcl
# AWS WAFをApp RunnerとAmplifyに適用
resource "aws_wafv2_web_acl" "main" {
  name  = "${var.project_name}-waf"
  scope = "REGIONAL"
  # ...
}
```

**コスト**: 月額 約$5-20

## コスト最適化のヒント

1. **プロビジョニングインスタンスの最小化**
   - App Runnerのプロビジョニングインスタンスは常時稼働
   - 低トラフィック時はインスタンス数を1に設定

2. **Amplifyビルドの最適化**
   - 頻繁なpushを避ける
   - 手動トリガーに変更
   - ビルドキャッシュを活用

3. **データ転送の削減**
   - CloudFront統合で転送コスト削減
   - 画像最適化

4. **不要なログの削減**
   - CloudWatch Logsの保持期間を短縮
   - 必要なログのみ出力

## 比較: Amplify vs ECS Fargate

| 項目 | Amplify + App Runner | ECS Fargate Spot |
|------|---------------------|-----------------|
| **月額コスト** | $45-65 | $60-85 |
| **初期構築** | 簡単 | やや複雑 |
| **運用管理** | ほぼ不要 | 中程度 |
| **スケーリング** | 完全自動 | 手動設定必要 |
| **可用性** | 高 (自動復旧) | 中 (スポット中断あり) |
| **CI/CD** | 組み込み | 別途設定 |
| **推奨用途** | 開発・テスト、低〜中トラフィック | 高トラフィック、本番環境 |

## サポート

問題が解決しない場合:
1. CloudWatch Logsを確認
2. App Runnerサービスの状態を確認
3. Amplifyビルドログを確認
4. プロジェクト管理者に連絡

## 参考リンク

- [AWS Amplify](https://aws.amazon.com/amplify/)
- [AWS App Runner](https://aws.amazon.com/apprunner/)
- [App Runner Pricing](https://aws.amazon.com/apprunner/pricing/)
- [Amplify Pricing](https://aws.amazon.com/amplify/pricing/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

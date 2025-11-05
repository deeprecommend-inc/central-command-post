# SNS Orchestrator - AWS Deployment Guide (最安値構成)

## 概要

このガイドでは、SNS Orchestratorを**AWS最安値構成**でデプロイする方法を説明します。

### デプロイ構成

| リソース | スペック | 月額コスト概算 |
|---------|---------|---------------|
| ECS Fargate Spot (Backend) | 0.25 vCPU, 0.5GB | $3-5/月 |
| ECS Fargate Spot (Frontend) | 0.25 vCPU, 0.5GB | $3-5/月 |
| ECS Fargate Spot (Worker) | 0.25 vCPU, 0.5GB | $3-5/月 |
| RDS PostgreSQL | db.t4g.micro, 20GB | $15-20/月 |
| ElastiCache Redis | cache.t4g.micro | $12-15/月 |
| Application Load Balancer | - | $20-25/月 |
| データ転送・その他 | - | $5-10/月 |
| **合計** | | **約 $60-85/月** |

### コスト最適化のポイント

1. **Fargate Spot**: 通常のFargateより最大70%安価
2. **t4g (Graviton2)**: x86より20%安価で高性能
3. **最小インスタンス**: 必要最小限のスペック
4. **Container Insights無効**: 追加課金なし
5. **短期ログ保持**: 7日間のみ
6. **最小バックアップ**: 1日分のみ

## 前提条件

### 必要なツール

```bash
# Terraform
brew install terraform  # macOS
# または https://www.terraform.io/downloads からダウンロード

# AWS CLI
brew install awscli  # macOS
# または https://aws.amazon.com/cli/ からダウンロード

# Docker
# https://docs.docker.com/get-docker/ からインストール

# バージョン確認
terraform --version  # >= 1.0
aws --version        # >= 2.0
docker --version     # >= 20.0
```

### AWS アカウント

- AWSアカウント (無料枠可)
- IAM ユーザーまたはロール (必要な権限):
  - EC2 (VPC, Subnet, Security Group)
  - ECS (Cluster, Service, Task)
  - RDS (Database Instance)
  - ElastiCache (Redis Cluster)
  - ECR (Repository)
  - IAM (Role, Policy)
  - CloudWatch (Logs)
  - Application Load Balancer

## クイックスタート

### 1. AWS認証情報の設定

```bash
aws configure
```

以下を入力:
- **AWS Access Key ID**: IAMユーザーのアクセスキー
- **AWS Secret Access Key**: IAMユーザーのシークレットキー
- **Default region name**: `ap-northeast-1` (東京) を推奨
- **Default output format**: `json`

### 2. Terraform設定

```bash
# terraform.tfvarsの作成
cp infrastructure/terraform/terraform.tfvars.example \
   infrastructure/terraform/terraform.tfvars

# 編集
vi infrastructure/terraform/terraform.tfvars
```

**必須項目**:
```hcl
# データベースパスワード (強力なパスワードを設定)
db_password = "YourStrongPasswordHere123!"

# アプリケーションシークレットキー (ランダムな文字列)
secret_key = "your-secret-key-change-this-to-random-string"
```

**オプション項目** (後でECSタスク定義で追加可能):
```hcl
anthropic_api_key = "sk-ant-..."
youtube_client_id = "..."
youtube_client_secret = "..."
```

### 3. デプロイ実行

```bash
# 初期化
./deploy.sh init

# プランの確認 (何が作成されるか確認)
./deploy.sh plan

# デプロイ実行 (10-15分)
./deploy.sh apply
```

### 4. Dockerイメージのビルドとデプロイ

```bash
# イメージをビルドしてECRにプッシュ
./deploy.sh build

# ECSサービスに新しいイメージを適用
aws ecs update-service --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-backend --force-new-deployment

aws ecs update-service --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-frontend --force-new-deployment

aws ecs update-service --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-worker --force-new-deployment
```

### 5. アクセス確認

```bash
# デプロイ情報の確認
cd infrastructure/terraform
terraform output

# Frontend URL
echo "http://$(terraform output -raw alb_dns_name)"

# Backend API URL
echo "http://$(terraform output -raw alb_dns_name)/api"
```

ブラウザでFrontend URLにアクセスしてダッシュボードを確認してください。

## 詳細手順

### データベース初期化

初回デプロイ後、データベースのテーブルを作成する必要があります。

```bash
# ECSタスクIDの取得
aws ecs list-tasks --cluster sns-orchestrator-cluster \
  --service-name sns-orchestrator-backend

# ECS Execでコンテナに接続
aws ecs execute-command \
  --cluster sns-orchestrator-cluster \
  --task <backend-task-id> \
  --container backend \
  --interactive \
  --command "/bin/bash"

# コンテナ内で実行
python -c "from app.models.database import init_db; import asyncio; asyncio.run(init_db())"
exit
```

**注意**: ECS Execを使用するには、事前にECS Execの有効化が必要です。

### 環境変数の追加設定

API キーなどの環境変数をECSタスク定義に追加する場合:

```bash
# 現在のタスク定義を取得
aws ecs describe-task-definition \
  --task-definition sns-orchestrator-backend \
  --query taskDefinition > task-def.json

# task-def.jsonを編集して環境変数を追加
vi task-def.json

# 新しいタスク定義を登録
aws ecs register-task-definition --cli-input-json file://task-def.json

# サービスを更新
aws ecs update-service \
  --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-backend \
  --force-new-deployment
```

または、Terraformファイルを直接編集:

```hcl
# infrastructure/terraform/main.tf の aws_ecs_task_definition.backend を編集
environment = [
  # 既存の環境変数
  {
    name  = "ANTHROPIC_API_KEY"
    value = var.anthropic_api_key
  },
  # 追加の環境変数
]
```

その後、`./deploy.sh apply`を再実行。

## deploy.shコマンドリファレンス

### init - 初期化
```bash
./deploy.sh init
```
Terraformの初期化を実行します。初回のみ実行が必要です。

### plan - プランの確認
```bash
./deploy.sh plan
```
デプロイで作成・変更・削除されるリソースを確認します。

### apply - デプロイ実行
```bash
./deploy.sh apply
```
AWSリソースをデプロイします。確認後に`yes`を入力してください。

### build - イメージビルド
```bash
./deploy.sh build
```
DockerイメージをビルドしてECRにプッシュします。

### destroy - リソース削除
```bash
./deploy.sh destroy
```
すべてのAWSリソースを削除します。**注意**: データも削除されます。

### status - 状態確認
```bash
./deploy.sh status
```
現在のデプロイ状態を確認します。

### cost - コスト概算
```bash
./deploy.sh cost
```
月額コストの概算を表示します。

### help - ヘルプ
```bash
./deploy.sh help
```
すべてのコマンドの使用方法を表示します。

## トラブルシューティング

### ECSタスクが起動しない

**原因**: イメージが存在しない、メモリ不足、環境変数エラーなど

**確認**:
```bash
# タスクの状態確認
aws ecs describe-tasks \
  --cluster sns-orchestrator-cluster \
  --tasks <task-id>

# ログ確認
aws logs tail /ecs/sns-orchestrator --follow
```

**解決策**:
1. `./deploy.sh build`でイメージをビルド
2. タスク定義の環境変数を確認
3. メモリ・CPUの割り当てを確認

### データベース接続エラー

**原因**: セキュリティグループ、エンドポイント設定

**確認**:
```bash
# RDSエンドポイント確認
cd infrastructure/terraform
terraform output rds_endpoint

# セキュリティグループ確認
aws ec2 describe-security-groups \
  --group-ids <sg-id>
```

**解決策**:
1. ECSタスクとRDSが同じVPC内にあることを確認
2. セキュリティグループでポート5432が許可されていることを確認

### Fargate Spotの中断

**原因**: AWS側の容量不足でスポットインスタンスが中断

**解決策**:
1. 自動的に再起動されるまで待つ
2. 本番環境では通常のFargateに変更を検討:
   ```hcl
   # main.tf の capacity_provider_strategy を変更
   launch_type = "FARGATE"
   # capacity_provider_strategy をコメントアウト
   ```

### Terraformエラー

**ロック解除**:
```bash
cd infrastructure/terraform
terraform force-unlock <lock-id>
```

**状態の修復**:
```bash
terraform refresh
```

**完全リセット**:
```bash
./deploy.sh destroy
rm -rf infrastructure/terraform/.terraform
rm infrastructure/terraform/.terraform.lock.hcl
./deploy.sh init
./deploy.sh apply
```

## 更新手順

### コードの更新をデプロイ

```bash
# 1. コードを更新 (git pull など)

# 2. イメージを再ビルド
./deploy.sh build

# 3. ECSサービスを更新
aws ecs update-service --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-backend --force-new-deployment
```

### インフラの更新

```bash
# 1. Terraformファイルを編集
vi infrastructure/terraform/main.tf

# 2. プランの確認
./deploy.sh plan

# 3. 適用
./deploy.sh apply
```

## 本番環境への移行

現在の構成は開発・テスト用です。本番環境では以下を検討してください:

### 1. Fargate通常インスタンスまたは予約

```hcl
# main.tf
launch_type = "FARGATE"
# capacity_provider_strategy をコメントアウト
```

### 2. RDS Multi-AZ

```hcl
# main.tf
multi_az = true
```

### 3. ElastiCache Multi-AZ

```hcl
# main.tf
automatic_failover_enabled = true
num_cache_nodes            = 2
```

### 4. Container Insights有効化

```hcl
# main.tf
setting {
  name  = "containerInsights"
  value = "enabled"
}
```

### 5. バックアップ期間延長

```hcl
# main.tf
backup_retention_period = 7  # 7日間
```

### 6. HTTPS対応

```hcl
# ACM証明書を取得してALBに設定
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = "arn:aws:acm:..."

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}
```

### 7. カスタムドメイン

Route 53でドメインを設定し、ALBをエイリアスレコードとして登録。

## セキュリティベストプラクティス

1. **パスワード管理**: AWS Secrets Managerを使用
2. **IAMロール**: 最小権限の原則を適用
3. **ネットワーク**: Private Subnetにデータベース配置
4. **暗号化**: RDS暗号化、S3暗号化を有効化
5. **監査ログ**: CloudTrailを有効化
6. **WAF**: AWS WAFでDDoS対策

## サポート

問題が解決しない場合:
1. CloudWatch Logsを確認
2. ECSタスクの状態を確認
3. Terraformの出力を確認
4. プロジェクト管理者に連絡

## 参考リンク

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS](https://docs.aws.amazon.com/ecs/)
- [AWS RDS](https://docs.aws.amazon.com/rds/)
- [AWS ElastiCache](https://docs.aws.amazon.com/elasticache/)
- [Fargate Spot](https://aws.amazon.com/fargate/spot/)

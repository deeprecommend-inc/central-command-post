# SNS Agent - Minimal Infrastructure

最小・最安構成でSNS Agentをデプロイするための設定です。

## コスト比較

| 構成 | 月額コスト (概算) |
|------|------------------|
| **Minimal (この構成)** | **~$10-15/month** (Free Tier: $0) |
| Full ECS/Fargate | ~$100-150/month |

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│                    EC2 Instance                     │
│                    (t3.micro)                       │
│  ┌─────────────────────────────────────────────┐   │
│  │              Docker Compose                  │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │ Frontend│ │ Backend │ │  Redis  │       │   │
│  │  │  :3006  │ │  :8006  │ │  :6379  │       │   │
│  │  └─────────┘ └─────────┘ └─────────┘       │   │
│  │                   │                         │   │
│  │              ┌────┴────┐                   │   │
│  │              │ SQLite  │                   │   │
│  │              │   DB    │                   │   │
│  │              └─────────┘                   │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## 使い方

### 1. 設定ファイルの作成

```bash
cd infrastructure/minimal
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvarsを編集して値を設定
```

### 2. Terraformの実行

```bash
terraform init
terraform plan
terraform apply
```

### 3. アプリケーションのデプロイ

```bash
# EC2インスタンスにSSH接続
ssh -i your-key.pem ec2-user@<public-ip>

# または SSM Session Manager
aws ssm start-session --target <instance-id>

# アプリケーションディレクトリに移動
cd /opt/sns-agent

# Dockerイメージをビルド (ソースコードをコピー後)
docker-compose -f docker-compose.minimal.yml build

# 起動
docker-compose -f docker-compose.minimal.yml up -d
```

### 4. アクセス

- Frontend: `http://<public-ip>:3006`
- Backend API: `http://<public-ip>:8006`
- API Docs: `http://<public-ip>:8006/docs`

## コスト削減のポイント

1. **EC2 t3.micro** - Free Tier対象 (12ヶ月間無料)
2. **SQLite** - PostgreSQL RDS不要 (~$15/month削減)
3. **ローカルRedis** - ElastiCache不要 (~$15/month削減)
4. **ALB不要** - 直接EC2にアクセス (~$20/month削減)
5. **NAT Gateway不要** - パブリックサブネットのみ (~$35/month削減)
6. **Container Insights無効** - CloudWatchコスト削減
7. **最小ログ保持** - 3日間のみ

## 注意事項

- この構成は開発/テスト用です
- 本番環境では以下を検討してください:
  - t3.small以上のインスタンス (2GB RAM)
  - RDSへの移行
  - ALBの追加
  - HTTPS対応
  - バックアップ設定

## トラブルシューティング

### ログの確認

```bash
# User-dataスクリプトのログ
cat /var/log/user-data.log

# Dockerログ
docker-compose logs -f

# 個別サービスのログ
docker-compose logs -f backend
```

### サービスの再起動

```bash
# すべてのサービスを再起動
docker-compose restart

# 個別サービスを再起動
docker-compose restart backend
```

### ディスク容量の確認

```bash
df -h
docker system df
```

## 削除

```bash
terraform destroy
```

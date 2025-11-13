# 釈迦AI (Shaka AI) v2.0

**自然言語でSNSを操作する次世代AIエージェント**

YouTube、X (Twitter)、Instagram、TikTokを**プロンプトベース**で自動操作するシステムです。

## ✨ 主な特徴

### 🎯 プロンプトベース操作

```bash
"YouTubeでAIに関する動画を検索して、上位5件にいいねして"
"Xで最新のテック系ニュースをリツイートして"
"Instagramで#旅行のハッシュタグを検索して、良い写真10件にいいねして"
```

**自然言語のタスク指示だけで、LLMが自動的にブラウザを操作します。**

### 🤖 Browser-Use アーキテクチャ

- **OAuth不要**: ユーザー名/パスワードで直接ログイン
- **LLM判断**: 状況に応じて柔軟に操作
- **統一API**: 全プラットフォームで同じインターフェース
- **ステルス対応**: Browser Use Cloudでbot検出回避

## 主要機能

### 1. マルチプラットフォーム対応（ブラウザ自動化）

#### YouTube
- ✅ Gmail生成（電話番号認証回避）
- ✅ ログイン
- ✅ 動画アップロード
- ✅ いいね / コメント / チャンネル登録
- ✅ 検索 / チャンネル情報取得

#### X (Twitter)
- ✅ ログイン
- ✅ ツイート投稿
- ✅ いいね / リツイート / 返信
- ✅ フォロー
- ✅ 検索 / ユーザー情報取得

#### Instagram
- ✅ ログイン
- ✅ 写真投稿
- ✅ いいね / コメント / フォロー
- ✅ ハッシュタグ検索
- ✅ DM送信

#### TikTok
- ✅ アカウント登録

### 2. 実行エンジン
- **Browser Automation**: Playwright完全ブラウザ操作（推奨）
- **Mulogin連携**: ブラウザ指紋管理（検知回避）
- **BrightData連携**: レジデンシャル/モバイルプロキシ（IPローテーション）

### 3. 大規模アカウント生成
- **対応規模**: 10,000 〜 1,000,000 アカウント
- **Gmail生成**: 電話番号認証回避戦略実装済み
- **ペルソナベース**: 各アカウントに異なる人格・行動パターン
- **プロキシローテーション**: 1アカウント1IP（固定セッション）
- **同時生成数**: 最大50並列

### 3. AI生成機能
- Claude API統合
- 返信候補生成 (人手承認必須)
- 投稿案、ハッシュタグ案生成
- 安全フィルタ、重複チェック

### 4. 16分類監視システム
Bot検知回避のための詳細な観測:
1. IP構造
2. 通信リズム
3. 暗号/プロトコル
4. User Agent
5. 指紋
6. Cookie/保存
7. JavaScript
8. マウス/ポインタ
9. テンポ
10. ナビゲーション
11. ヘッダ
12. データ送信
13. CAPTCHA後挙動
14. 一貫性
15. 分散
16. 自動学習対応

### 5. セキュリティ
- OAuth トークン暗号化
- WORM監査ログ (不可逆)
- レート制限遵守
- Kill Switch機能

## アーキテクチャ

```
[React/Next.js] ─REST→ [FastAPI] ─→ [Redis(Queue+Rate)]
                           │
                      [Workers(Python)]
                           │
              [SNS API / Internal QA Domain]
                           │
         [PostgreSQL] + [WORM Audit Storage]
```

## セットアップ

### 前提条件
- Docker & Docker Compose
- Node.js 18+ (ローカル開発の場合)
- Python 3.11+ (ローカル開発の場合)

### 1. 環境変数設定

```bash
cp .env.example .env
# .envファイルを編集して各APIキーを設定
```

### 2. 起動 (自動化スクリプト使用)

```bash
./start.sh
```

このスクリプトは以下を自動的に実行します:
- 依存関係チェック (Docker, Docker Compose)
- 環境変数ファイルの確認・作成
- 既存コンテナの停止
- サービスの起動
- データベースの初期化
- 起動確認

サービスが起動します:
- Backend API: http://localhost:8006
- Frontend: http://localhost:3006
- PostgreSQL: localhost:5432
- Redis: localhost:6379

#### オプション
```bash
./start.sh -f           # ログを自動的に表示
./start.sh --skip-checks # 依存関係チェックをスキップ
./start.sh -h           # ヘルプ表示
```

### 3. 手動起動 (従来の方法)

```bash
# Docker起動
docker-compose up -d

# データベース初期化
docker-compose exec backend python -c "from app.models.database import init_db; import asyncio; asyncio.run(init_db())"
```

## 使用方法

### ダッシュボード
http://localhost:3006 にアクセス

- KPIカード表示
- 当日のキュー状況
- 承認待ちアイテム
- システムステータス

### OAuth接続設定

1. 各プラットフォームの開発者コンソールでアプリ作成
2. リダイレクトURIを設定: `http://localhost:8006/oauth/{platform}/callback`
3. クライアントIDとシークレットを`.env`に設定
4. UIから接続: OAuth接続 → プラットフォーム選択 → 認可

### 実行作成

1. **実行作成**ページへ
2. プラットフォーム選択
3. 実行エンジン選択 (API Fast推奨)
4. スケジュール設定
5. レート・ペース設定
6. 16分類監視しきい値設定
7. Custom Prompt入力
8. 実行

### 承認フロー

1. **承認キュー**ページへ
2. AI生成案を確認
3. 承認/編集/差戻し

## API エンドポイント

### OAuth
- `GET /oauth/{platform}/connect` - OAuth接続開始
- `GET /oauth/{platform}/callback` - OAuth コールバック
- `GET /oauth/{platform}/status` - 接続状態確認
- `POST /oauth/{platform}/disconnect/{account_id}` - 接続解除

### Runs (実行)
- `POST /runs/` - Run作成
- `GET /runs/{run_id}` - Run詳細取得
- `GET /runs/` - Run一覧取得
- `PATCH /runs/{run_id}` - Run更新
- `POST /runs/{run_id}/kill` - Kill Switch発動
- `POST /runs/{run_id}/enqueue` - ジョブをキューに追加

### AI Drafts
- `POST /drafts/generate` - AI生成
- `GET /drafts/{draft_id}` - Draft詳細取得
- `GET /drafts/` - Draft一覧取得
- `POST /drafts/{draft_id}/approve` - Draft承認
- `POST /drafts/{draft_id}/reject` - Draft拒否

### Metrics
- `GET /metrics/kpi` - KPIメトリクス取得
- `GET /metrics/execution-stats` - 実行統計取得
- `GET /metrics/observability` - 監視メトリクス取得
- `GET /metrics/dashboard` - ダッシュボードサマリ取得

### Campaigns
- `POST /schedules/campaigns` - キャンペーン作成
- `GET /schedules/campaigns/{campaign_id}` - キャンペーン詳細取得
- `GET /schedules/campaigns` - キャンペーン一覧取得
- `PATCH /schedules/campaigns/{campaign_id}` - キャンペーン更新
- `DELETE /schedules/campaigns/{campaign_id}` - キャンペーン削除

## データモデル

### 主要テーブル
- `accounts` - SNSアカウント情報
- `runs` - 実行設定
- `run_events` - 実行イベント履歴
- `ai_drafts` - AI生成案
- `kpi_snapshots` - KPIスナップショット
- `audit_worm` - WORM監査ログ
- `observability_metrics` - 監視メトリクス
- `campaigns` - キャンペーン
- `kill_switches` - Kill Switch

## 監視しきい値設定

16分類の監視項目は`observability_json`に設定:

```json
{
  "ip_structure": {
    "ip_ua_inconsistency_sigma": 2.5,
    "geo_mismatch_pct": 5.0,
    "asn_bias_pct": 60.0,
    "residential_ratio_min": 30.0
  },
  "rhythm": {
    "interval_periodicity_score": 75.0,
    "persistent_conn_ratio_min": 40.0,
    "simul_conn_per_ip_max": 4
  },
  ...
}
```

詳細は仕様書の「付録A: 16分類→観測キー完全対応表」を参照。




### 推奨事項
- アカウント自動生成
- 成りすまし
- 検知回避目的の悪用
- CAPTCHA回避
- クリック水増し
- 規約違反行為
- OAuth接続済みの自社・同意済みアカウントのみ使用
- 承認フローを必ず有効化
- レート制限を遵守
- 監査ログを定期的に確認
- Kill Switchを適切に活用

## 管理スクリプト

プロジェクトには以下の管理スクリプトが用意されています:

### start.sh - 起動スクリプト
システムを起動し、自動的にセットアップします。

```bash
./start.sh              # 通常起動
./start.sh -f           # ログを表示しながら起動
./start.sh --skip-checks # 依存関係チェックをスキップ
```

### stop.sh - 停止スクリプト
システムを停止します。

```bash
./stop.sh               # サービス停止 (データは保持)
./stop.sh --volumes     # サービス停止 + データ削除
./stop.sh --clean       # 完全クリーンアップ
./stop.sh --status      # 現在の状態確認
```

### logs.sh - ログ表示スクリプト
各サービスのログを表示します。

```bash
./logs.sh               # 全サービスのログ表示
./logs.sh backend       # バックエンドのみ
./logs.sh frontend      # フロントエンドのみ
./logs.sh worker        # ワーカーのみ
./logs.sh -f            # ログをフォロー
./logs.sh backend -n 50 # 最後の50行を表示
```

### reset.sh - リセットスクリプト
システムを完全にリセットします（全データ削除）。

```bash
./reset.sh              # 完全リセット（確認あり）
```

### cleanup-ports.sh - ポートクリーンアップスクリプト
ポート競合を解決します（クイックフィックス）。

```bash
./cleanup-ports.sh      # ポートを使用中のプロセス/コンテナを停止
```

## トラブルシューティング

### データベース接続エラー
```bash
docker-compose restart postgres
./logs.sh postgres
```

### Redis接続エラー
```bash
docker-compose restart redis
./logs.sh redis
```

### ワーカーが動作しない
```bash
./logs.sh worker
docker-compose restart worker
```

### OAuth接続失敗
- クライアントID/シークレットを確認
- リダイレクトURIが正しいか確認: `http://localhost:8006/oauth/{platform}/callback`
- プラットフォームのAPI制限を確認

### ポート競合エラー
```bash
# クイックフィックス
./cleanup-ports.sh
./start.sh

# または完全リセット
./reset.sh
./start.sh
```

### サービスが起動しない
```bash
# 完全リセットして再起動
./reset.sh
./start.sh
```

### ログの確認
```bash
# 全サービスのログ
./logs.sh -f

# 特定サービスのログ
./logs.sh backend -f
```

## AWS本番デプロイ

本プロジェクトはTerraformを使用してAWS上に2種類の構成でデプロイできます。

### デプロイオプション比較

| 構成 | 月額コスト | 特徴 | 推奨用途 |
|------|-----------|------|---------|
| **Amplify + App Runner** | $45-65 | サーバーレス、自動スケーリング、デプロイ簡単 | 開発・テスト、低〜中トラフィック |
| **ECS Fargate Spot** | $60-85 | コンテナベース、スポット価格、ALB付き | 高トラフィック、本番環境 |

### オプション1: Amplify + App Runner (超最安値・推奨)

**月額 約 $45-65**

#### 構成
- **AWS Amplify** (Frontend): 従量課金、自動CI/CD
- **AWS App Runner** (Backend/Worker): 従量課金、自動スケーリング
- **RDS PostgreSQL**: db.t4g.micro (最小インスタンス)
- **ElastiCache Redis**: cache.t4g.micro (最小インスタンス)

#### 利点
- ECS Fargateより20-30%安価
- サーバーレス (管理不要)
- デプロイが非常に簡単
- ALB不要 (コスト削減)
- 自動スケーリング

#### デプロイ手順

```bash
# 1. AWS認証設定
aws configure

# 2. 設定ファイル作成
cp infrastructure/amplify/terraform.tfvars.example infrastructure/amplify/terraform.tfvars
vi infrastructure/amplify/terraform.tfvars

# 3. デプロイ
./deploy-amplify.sh init
./deploy-amplify.sh apply
./deploy-amplify.sh build
./deploy-amplify.sh redeploy

# 4. フロントエンド: Amplifyコンソールでリポジトリ接続
```

詳細は `./deploy-amplify.sh help` を参照。

---

### オプション2: ECS Fargate Spot (高トラフィック向け)

**月額 約 $60-85**

#### 構成
- **ECS Fargate Spot**: スポットインスタンスで最大70%コスト削減
- **RDS PostgreSQL**: db.t4g.micro (最小インスタンス)
- **ElastiCache Redis**: cache.t4g.micro (最小インスタンス)
- **Application Load Balancer**: HTTPアクセス対応

#### デプロイ手順

```bash
# 1. AWS認証設定
aws configure

# 2. 設定ファイル作成
cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
vi infrastructure/terraform/terraform.tfvars

# 3. デプロイ
./deploy.sh init
./deploy.sh apply
./deploy.sh build
```

詳細は `./deploy.sh help` または `DEPLOY.md` を参照。

---

## デプロイ詳細情報

### 前提条件

```bash
# 必要なツール
- Terraform >= 1.0
- AWS CLI
- Docker

# インストール確認
terraform --version
aws --version
docker --version
```

### ECS Fargate詳細手順

#### 1. AWS認証情報の設定

```bash
aws configure
# AWS Access Key ID を入力
# AWS Secret Access Key を入力
# リージョンを入力 (例: ap-northeast-1)
```

#### 2. Terraform設定ファイルの準備

```bash
# terraform.tfvarsの作成
cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars

# terraform.tfvarsを編集
vi infrastructure/terraform/terraform.tfvars
```

必須設定項目:
- `db_password`: データベースパスワード
- `secret_key`: アプリケーションシークレットキー

#### 3. Terraformの初期化

```bash
./deploy.sh init
```

#### 4. デプロイプランの確認

```bash
./deploy.sh plan
```

#### 5. インフラのデプロイ

```bash
./deploy.sh apply
```

デプロイには10-15分程度かかります。完了すると以下の情報が表示されます:
- Frontend URL
- Backend API URL
- ECS Cluster名

#### 6. Dockerイメージのビルドとプッシュ

```bash
./deploy.sh build
```

このコマンドは以下を実行します:
- BackendとFrontendのDockerイメージをビルド
- AWS ECRにイメージをプッシュ

#### 7. ECSサービスの再起動

```bash
# 新しいイメージを適用するためサービスを再起動
aws ecs update-service --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-backend --force-new-deployment

aws ecs update-service --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-frontend --force-new-deployment

aws ecs update-service --cluster sns-orchestrator-cluster \
  --service sns-orchestrator-worker --force-new-deployment
```

#### 8. データベースの初期化

```bash
# ECSタスクに接続してデータベースを初期化
# (まず、ECS Execを有効にする必要があります)
aws ecs execute-command --cluster sns-orchestrator-cluster \
  --task <backend-task-id> --container backend --interactive \
  --command "/bin/bash"

# コンテナ内で実行
python -c "from app.models.database import init_db; import asyncio; asyncio.run(init_db())"
```

### deploy.shコマンド一覧

```bash
./deploy.sh init      # Terraformの初期化 (初回のみ)
./deploy.sh plan      # デプロイ計画の確認
./deploy.sh apply     # インフラのデプロイ
./deploy.sh build     # Dockerイメージのビルドとプッシュ
./deploy.sh destroy   # 全リソースの削除
./deploy.sh status    # 現在のデプロイ状態の確認
./deploy.sh cost      # 月額コスト概算の表示
./deploy.sh help      # ヘルプ表示
```

### リソースの削除

```bash
./deploy.sh destroy
```

すべてのAWSリソースが削除されます。確認メッセージで`yes`を入力してください。

### コスト最適化のポイント

1. **Fargate Spot使用**: 通常の70%のコストで実行
2. **最小インスタンスサイズ**: db.t4g.micro, cache.t4g.micro
3. **Container Insights無効**: CloudWatch追加課金なし
4. **バックアップ最小化**: 1日分のみ保持
5. **ログ保持期間短縮**: 7日間のみ

### 注意事項

- **スポットインスタンスの中断**: Fargate Spotは需要が高い時に中断される可能性があります
- **本番環境での推奨事項**:
  - 予約インスタンスの検討
  - マルチAZ構成
  - バックアップ期間の延長
  - CloudWatch Container Insightsの有効化
  - AWS WAFの追加
  - Route 53でのカスタムドメイン設定

### トラブルシューティング

#### Terraformエラー

```bash
# 状態ファイルのロック解除
cd infrastructure/terraform
terraform force-unlock <lock-id>

# 状態の確認
terraform show
```

#### ECSタスクが起動しない

```bash
# ログの確認
aws logs tail /ecs/sns-orchestrator --follow

# タスクの詳細確認
aws ecs describe-tasks --cluster sns-orchestrator-cluster --tasks <task-id>
```

#### データベース接続エラー

```bash
# セキュリティグループの確認
aws ec2 describe-security-groups --group-ids <sg-id>

# RDSエンドポイントの確認
cd infrastructure/terraform
terraform output rds_endpoint
```

## 開発

### ローカル開発 (Docker不使用)

#### バックエンド
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### フロントエンド
```bash
cd frontend
npm install
npm run dev
```

### テスト実行

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## ライセンス

Private - 内部使用のみ

## サポート

問題や質問がある場合は、プロジェクト管理者に連絡してください。

## バージョン履歴

- v1.3.0 (2025-01-05)
  - 初期リリース
  - 4プラットフォーム対応
  - 16分類監視システム実装
  - WORM監査ログ実装
  - AI生成機能統合

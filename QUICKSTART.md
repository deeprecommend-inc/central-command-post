# SNS運用オーケストレーター - クイックスタートガイド

5分でSNS Orchestratorを起動・体験できるガイドです。

## 前提条件

- Docker & Docker Compose がインストール済み
- 8006, 3006, 5432, 6379 ポートが利用可能

## ステップ1: プロジェクトの準備 (1分)

```bash
cd /path/to/sns-agents

# 環境変数ファイルを作成 (開発用デフォルト設定)
cp .env.example .env
```

> **注意**: 本番利用する場合は、`.env`を編集して各SNSプラットフォームのOAuthクライアントID/シークレット、AI APIキーを設定してください。

## ステップ2: システム起動 (2-3分)

```bash
# 自動起動スクリプトを実行
./start.sh
```

スクリプトが自動的に以下を実行します:
- ✓ 依存関係チェック
- ✓ Dockerコンテナのビルド・起動
- ✓ データベース初期化
- ✓ サービス起動確認

起動完了後、以下のURLが表示されます:
- **Frontend**: http://localhost:3006
- **Backend API**: http://localhost:8006
- **API Docs**: http://localhost:8006/docs

## ステップ3: ダッシュボードにアクセス (30秒)

ブラウザで以下を開きます:
```
http://localhost:3006
```

ダッシュボードには以下が表示されます:
- 📊 KPIカード (実行数、成功率、承認待ち、違反数)
- 🎯 クイックアクション
- 💚 システムステータス

## ステップ4: APIドキュメント確認 (30秒)

```
http://localhost:8006/docs
```

Swagger UIで全APIエンドポイントを確認・テスト可能:
- OAuth管理
- Run作成・管理
- AI生成・承認
- メトリクス取得
- キャンペーン管理

## 次のステップ

### OAuth接続設定

各SNSプラットフォームと連携するには:

1. **開発者コンソールでアプリ作成**
   - YouTube: https://console.cloud.google.com/
   - X: https://developer.twitter.com/
   - Instagram: https://developers.facebook.com/
   - TikTok: https://developers.tiktok.com/

2. **リダイレクトURI設定**
   ```
   http://localhost:8006/oauth/{platform}/callback
   ```

3. **.envファイルに認証情報追加**
   ```bash
   YOUTUBE_CLIENT_ID=your-client-id
   YOUTUBE_CLIENT_SECRET=your-client-secret
   # ... 他のプラットフォームも同様
   ```

4. **サービス再起動**
   ```bash
   ./stop.sh
   ./start.sh
   ```

5. **UI経由で接続**
   - ダッシュボード → "Manage OAuth Connections"
   - プラットフォーム選択 → 認可

### AI機能を有効化

AIによる投稿・返信生成を使用するには:

1. **APIキー取得**
   - Anthropic Claude: https://console.anthropic.com/
   - または OpenAI: https://platform.openai.com/

2. **.envに追加**
   ```bash
   ANTHROPIC_API_KEY=your-anthropic-api-key
   # または
   OPENAI_API_KEY=your-openai-api-key
   ```

3. **サービス再起動**
   ```bash
   docker-compose restart backend worker
   ```

### 最初のRunを作成

1. **ダッシュボード → "Create New Run"**

2. **基本設定**
   - プラットフォーム選択
   - 実行エンジン: API Fast (推奨)
   - 接続済みアカウント選択

3. **スケジュール設定**
   ```json
   {
     "start": "2025-01-06T09:00:00+09:00",
     "end": "2025-01-06T18:00:00+09:00",
     "timezone": "Asia/Tokyo"
   }
   ```

4. **レート設定**
   ```json
   {
     "hourly_limit": 10,
     "daily_limit": 100,
     "wait_min_seconds": 60,
     "wait_max_seconds": 300,
     "distribution": "normal"
   }
   ```

5. **カスタムプロンプト入力**
   ```
   フォロワーとエンゲージメントを高める
   フレンドリーで専門的なトーン
   適切なハッシュタグを含める
   ```

6. **実行**

## 便利なコマンド

### ログ確認
```bash
# 全ログを表示
./logs.sh -f

# バックエンドのみ
./logs.sh backend -f

# 最後の50行のみ
./logs.sh backend -n 50
```

### サービス管理
```bash
# 停止 (データ保持)
./stop.sh

# 停止 + データ削除
./stop.sh --volumes

# 完全リセット
./reset.sh

# 再起動
./stop.sh && ./start.sh
```

### ステータス確認
```bash
# コンテナ状態確認
docker-compose ps

# リソース使用状況
docker stats
```

## トラブルシューティング

### ポートが使用中

**クイックフィックス (推奨):**
```bash
# 自動クリーンアップスクリプト実行
./cleanup-ports.sh

# その後、再起動
./start.sh
```

**手動確認:**
```bash
# ポート使用確認
lsof -i :8006  # Backend
lsof -i :3006  # Frontend
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis

# 使用中のプロセスを停止
kill -9 <PID>

# または全Dockerコンテナ停止
docker stop $(docker ps -q)
```

### データベース接続エラー
```bash
# PostgreSQL再起動
docker-compose restart postgres

# ログ確認
./logs.sh postgres
```

### コンテナが起動しない
```bash
# 完全クリーンアップ
./reset.sh

# 再起動
./start.sh
```

### キャッシュクリア
```bash
# Dockerイメージ再ビルド
docker-compose build --no-cache

# 起動
docker-compose up -d
```

## セキュリティチェックリスト

起動後、必ず確認してください:

- [ ] `.env`ファイルのシークレットキーを変更
- [ ] OAuth クライアントシークレットを設定
- [ ] 本番環境では`DEBUG=false`に設定
- [ ] ファイアウォール設定 (必要なポートのみ開放)
- [ ] 監査ログの定期確認体制を確立
- [ ] Kill Switchの使用方法を理解

## よくある質問

**Q: デモ用途で使えますか？**
A: はい。`.env.example`のデフォルト設定で即座に起動できます。ただしOAuth連携とAI機能は実際のAPIキーが必要です。

**Q: 本番環境で使用できますか？**
A: 可能ですが、以下を実施してください:
- トークン暗号化の実装 (KMS)
- ユーザー認証の実装
- セキュリティ監査
- バックアップ体制の確立

**Q: どのSNSから始めるべきですか？**
A: X (Twitter)が最も簡単です。API v2は個人開発者でもアクセスしやすく、テストに最適です。

**Q: レート制限を超えるとどうなりますか？**
A: システムが自動的に検知し、実行を遅延またはキューに待機させます。監視メトリクスで確認できます。

**Q: AI生成は必須ですか？**
A: いいえ。手動で投稿内容を指定することも可能です。AI生成は補助機能です。

## サポート

- **ドキュメント**: README.md
- **実装詳細**: IMPLEMENTATION.md
- **仕様書**: 仕様書.md
- **API仕様**: http://localhost:8006/docs

---

**起動時間**: 約3-5分
**推奨メモリ**: 4GB以上
**推奨CPU**: 2コア以上

**準備完了です！SNS運用を始めましょう🚀**

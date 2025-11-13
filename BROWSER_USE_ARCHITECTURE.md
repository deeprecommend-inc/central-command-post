# 釈迦AI - Browser-Use Based Architecture

## Overview

**釈迦AI (Shaka AI)** は**OAuth不要**の**プロンプトベース**SNS自動化システムです。

browser-useライブラリを使用して、自然言語のタスク指示からブラウザ操作を実行します。

### 名前の由来

「釈迦」は悟りを開いた仏陀として、あらゆる苦しみから人々を解放しました。
**釈迦AI**は、煩雑なSNS運用作業から人々を解放し、自然言語だけでSNSを自在に操る「悟り」の境地を提供します。

## アーキテクチャ変更

### Before (OAuth方式)
```
ユーザー → OAuth認証 → APIトークン → SNS API呼び出し
```

**問題点**:
- OAuth認証フローが複雑
- プラットフォームごとにAPIの制限・仕様が異なる
- API経由では実行できない操作がある
- トークン管理が煩雑

### After (Browser-Use方式)
```
ユーザー → 自然言語タスク → Browser-Use Agent → ブラウザ操作 → SNS
```

**利点**:
- 自然言語で操作を記述
- OAuth不要（ユーザー名/パスワードでログイン）
- 人間と同じ操作が可能
- プラットフォーム間で統一されたAPI
- LLMが状況判断して柔軟に操作

## 主要コンポーネント

### 1. Browser Agent Service
**ファイル**: `backend/app/services/browser_agent.py`

browser-useラッパーサービス。自然言語タスクをブラウザ操作に変換。

```python
from app.services.browser_agent import browser_agent

# 自然言語でタスク実行
result = await browser_agent.execute_task(
    task="Like the top 5 videos in my YouTube feed",
    platform="youtube",
    account_credentials={
        "username": "demo_user_1",
        "email": "demo_user_1@gmail.com",
        "password": "password123"
    }
)
```

### 2. Browser Actions API
**ファイル**: `backend/app/api/browser_actions.py`

プロンプトベースのアクション実行API。

**エンドポイント**:

#### `POST /browser-actions/execute`
自然言語タスクを実行

**リクエスト例**:
```json
{
  "task": "Post a video with title 'My Test Video' and description 'This is a test'",
  "platform": "youtube",
  "account_id": 1,
  "use_generated_account": true,
  "browser_config": {
    "headless": true
  }
}
```

**レスポンス例**:
```json
{
  "success": true,
  "result": "Video posted successfully",
  "actions_taken": [
    "Logged in to YouTube",
    "Navigated to upload page",
    "Uploaded video file",
    "Filled in title and description",
    "Published video"
  ],
  "screenshots": [
    "screenshot_1.png",
    "screenshot_2.png"
  ],
  "execution_time": 45.2,
  "error": null
}
```

#### `POST /browser-actions/login`
プラットフォームにログインしてセッション確立

#### `GET /browser-actions/examples`
プラットフォーム別のタスク例を取得

### 3. アカウントモデル（変更点）

**Before**:
```python
class Account(Base):
    oauth_token_ref = Column(String(255))  # OAuthトークン
```

**After**:
```python
class Account(Base):
    username = Column(String(255))  # SNSユーザー名
    email = Column(String(255))  # ログインメール
    password_encrypted = Column(String(255))  # 暗号化パスワード
```

OAuth不要。ブラウザログインに使用する認証情報を保存。

## 使用例

### 例1: YouTube動画投稿
```bash
curl -X POST "http://localhost:8006/browser-actions/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Upload a video with title \"Test Video\" and description \"This is a test\"",
    "platform": "youtube",
    "account_id": 1,
    "use_generated_account": true
  }'
```

### 例2: X (Twitter) ツイート
```bash
curl -X POST "http://localhost:8006/browser-actions/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Post a tweet: Hello World from browser automation!",
    "platform": "x",
    "account_id": 2,
    "use_generated_account": true
  }'
```

### 例3: Instagram いいね
```bash
curl -X POST "http://localhost:8006/browser-actions/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Like the top 10 posts in my feed",
    "platform": "instagram",
    "account_id": 3,
    "use_generated_account": true
  }'
```

### 例4: 複雑なタスク
```bash
curl -X POST "http://localhost:8006/browser-actions/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Search for videos about AI, watch the top 3, like them if they are good quality, and leave a thoughtful comment",
    "platform": "youtube",
    "account_id": 1,
    "use_generated_account": true
  }'
```

## タスク記述のベストプラクティス

### ✅ Good Examples

```
"Post a video with title 'My Tutorial' and description 'Learn Python'"
"Like the top 10 videos in my feed"
"Follow users who posted videos about AI in the last week"
"Search for 'cooking recipes' and save the top 5 videos to Watch Later"
"Reply 'Great content!' to comments on my latest video"
```

### ❌ Bad Examples

```
"Do something"  # 曖昧すぎる
"Post video"  # 詳細が不足
"Like all videos"  # 無限ループの可能性
```

### タスク記述のコツ

1. **具体的に**: 何をするかを明確に
2. **数量を指定**: "top 5", "10 posts" など
3. **条件を明記**: "if they are high quality", "from last week" など
4. **ステップを分ける**: 複雑な場合は複数のタスクに分割

## Browser-Use Cloud

### ローカル実行 (デフォルト)
```python
result = await browser_agent.execute_task(
    task="...",
    use_cloud=False  # ローカルのChromiumを使用
)
```

### Cloud実行 (ステルス・スケール)
```python
result = await browser_agent.execute_task(
    task="...",
    use_cloud=True  # Browser Use Cloudを使用
)
```

**Cloud の利点**:
- ステルスブラウザ（検出されにくい）
- 並列実行のスケール
- セッション管理
- プロキシ管理

**環境変数設定**:
```bash
BROWSER_USE_API_KEY=your-api-key
```

## セットアップ

### 1. 依存関係インストール
```bash
cd backend
pip install -r requirements.txt
```

### 2. Chromiumインストール
```bash
playwright install chromium
```

### 3. 環境変数設定
```bash
# .env
DATABASE_URL=postgresql+asyncpg://...
ANTHROPIC_API_KEY=your-anthropic-key  # ChatBrowserUse用
OPENAI_API_KEY=your-openai-key  # オプション
BROWSER_USE_API_KEY=your-browser-use-key  # Cloud使用時
```

### 4. サーバー起動
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload
```

## API ドキュメント

起動後、以下のURLでインタラクティブAPIドキュメントを確認：

- **Swagger UI**: http://localhost:8006/docs
- **ReDoc**: http://localhost:8006/redoc

"Browser Actions" タグのエンドポイントを参照。

## 移行ガイド

### OAuth APIから Browser-Use APIへ

**Before**:
```python
# OAuthトークンで投稿
POST /youtube/post
Headers: Authorization: Bearer <token>
Body: {"title": "...", "description": "..."}
```

**After**:
```python
# 自然言語タスクで投稿
POST /browser-actions/execute
Body: {
  "task": "Post a video with title '...' and description '...'",
  "platform": "youtube",
  "account_id": 1
}
```

### 既存アカウントの移行

1. Accountテーブルに `username`, `email`, `password_encrypted` を追加
2. 既存OAuthアカウントは `oauth.router` (Legacy) で継続利用可能
3. 新規アカウントは `generated_accounts` で管理

## トラブルシューティング

### Chromiumが起動しない
```bash
playwright install chromium
playwright install-deps chromium
```

### タスクがタイムアウト
- `browser_config.timeout` を増やす
- タスクを複数に分割

### ログインに失敗
- 認証情報を確認
- 2段階認証が有効な場合は無効化または専用パスワード使用
- Cloudモード (`use_cloud=True`) でステルスブラウザを試す

## 今後の拡張

- [ ] タスク履歴管理
- [ ] スケジュール実行
- [ ] バッチ処理
- [ ] カスタムツール追加
- [ ] マルチアカウント並列実行
- [ ] Webhook通知
- [ ] タスクテンプレート

## 参考リンク

- [browser-use GitHub](https://github.com/browser-use/browser-use)
- [Browser Use Cloud](https://browseruse.com)
- [Playwright](https://playwright.dev/)

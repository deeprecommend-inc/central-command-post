# CCP - Central Command Platform

産業現場の「判断」と「指示」を担うAI中央指揮所

## コンセプト

CCPは、点在するデータ、分断された判断、属人化した運用を統合し、
「状況把握 → 判断 → 指示 → 実行監視」をAIで自動化・高速化する。

```
[Sense] → [Think] → [Command] → [Control] → [Learn]
   ↓         ↓          ↓           ↓          ↓
 状況認識   判断      指示生成    実行監視    学習・知識化
```

## CCPの本質的価値

- AIは分析係ではなく「指揮官」
- データを見るAIではなく、動かすAI
- 単体AIではなく、全体を統べるOS
- 現場・経営・システムを貫く意思決定中枢

---

# Web操作エージェント（Command層の実装）

プロンプトからWeb操作エージェントを実行するPythonフレームワーク。

## 機能

- **プロキシローテーション** - BrightData連携による自動IPローテーション
- **IPタイプ選択** - 住宅IP / モバイルIP / データセンターIP / ISP IP
- **ヘルスチェック** - プロキシの自動健全性確認
- **ユーザーエージェント管理** - LRUキャッシュ付きUA/フィンガープリント
- **並列処理** - 最大50並列のブラウザセッション
- **自動リトライ** - 指数バックオフによる再試行
- **レート制限** - トークンバケット方式のリクエスト制限
- **セッション永続化** - Cookie/LocalStorage の保存・復元
- **構造化ログ** - JSON形式対応

## インストール

```bash
# 1. リポジトリをクローン
git clone <repository-url>
cd sns-agent

# 2. 仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 3. 依存関係をインストール
pip install -r requirements.txt

# 4. Playwrightブラウザをインストール
playwright install chromium
playwright install-deps chromium

# 5. 環境変数を設定（オプション）
cp .env.example .env
```

## CLI

### 基本コマンド

```bash
# URL操作
python run.py url https://example.com

# 複数URL並列
python run.py url https://example.com https://google.com https://github.com

# プロキシヘルスチェック
python run.py health

# デモ
python run.py demo

# ヘルプ
python run.py --help
```

### プロキシタイプ選択

```bash
# 住宅IP（デフォルト）
python run.py url -r https://example.com

# モバイルIP
python run.py url -m https://example.com

# データセンターIP
python run.py url -d https://example.com

# ISP IP
python run.py url -i https://example.com

# プロキシなし（直接接続）
python run.py url --no-proxy https://example.com
```

### ロギングオプション

```bash
# JSON形式でログ出力
python run.py url --json https://example.com

# 詳細ログ（DEBUG）
python run.py url -v https://example.com
```

### CLIオプション一覧

| オプション | 短縮 | 説明 |
|-----------|------|------|
| `--residential` | `-r` | 住宅IP（デフォルト） |
| `--mobile` | `-m` | モバイルIP |
| `--datacenter` | `-d` | データセンターIP |
| `--isp` | `-i` | ISP IP |
| `--no-proxy` | - | 直接接続 |
| `--json` | - | JSON形式ログ |
| `--verbose` | `-v` | 詳細ログ |

## 環境変数

| 変数 | 必須 | 説明 |
|------|------|------|
| BRIGHTDATA_USERNAME | No | BrightDataユーザー名 |
| BRIGHTDATA_PASSWORD | No | BrightDataパスワード |
| BRIGHTDATA_PROXY_TYPE | No | residential/datacenter/mobile/isp |
| PARALLEL_SESSIONS | No | 並列数（デフォルト: 5、最大: 50） |
| HEADLESS | No | ヘッドレス実行（デフォルト: true） |
| LOG_FORMAT | No | ログ形式: json/text（デフォルト: text） |
| LOG_LEVEL | No | ログレベル: DEBUG/INFO/WARNING/ERROR |

## Pythonコード

### 基本使用

```python
import asyncio
from src import WebAgent, AgentConfig

async def main():
    config = AgentConfig(
        parallel_sessions=5,
        headless=True,
    )

    # コンテキストマネージャーで自動クリーンアップ
    async with WebAgent(config) as agent:
        result = await agent.navigate("https://httpbin.org/ip")
        if result.success:
            print(f"Title: {result.data.get('title')}")

        # 複数URLに並列アクセス
        results = await agent.parallel_navigate([
            "https://httpbin.org/ip",
            "https://httpbin.org/user-agent",
        ])

asyncio.run(main())
```

### プロキシ使用

```python
async def main():
    config = AgentConfig(
        brightdata_username="your_username",
        brightdata_password="your_password",
        proxy_type="mobile",
    )

    async with WebAgent(config) as agent:
        # プロキシヘルスチェック
        health = await agent.health_check()
        print(f"Proxy health: {health}")

        result = await agent.navigate("https://httpbin.org/ip")
        print(f"IP: {result.data}")
```

### レート制限

```python
from src import TokenBucketRateLimiter, DomainRateLimiter

# 単一ドメイン用
limiter = TokenBucketRateLimiter(
    requests_per_second=2.0,
    burst_size=5,
)

async with limiter:
    await make_request()

# ドメイン別レート制限
domain_limiter = DomainRateLimiter(default_rps=1.0)
domain_limiter.set_domain_limit("api.example.com", 5.0)

async with domain_limiter.for_url("https://api.example.com/data"):
    await fetch_data()
```

### セッション永続化

```python
from src import SessionManager

manager = SessionManager(storage_dir="./sessions")

# ログイン後にセッション保存
await manager.save_session(browser_context, "user_session")

# 次回起動時にセッション復元
await manager.load_session(browser_context, "user_session")

# セッション一覧
sessions = manager.list_sessions()

# セッション削除
manager.delete_session("user_session")
```

### 構造化ログ

```python
from src import configure_logging

# JSON形式でログ出力
configure_logging(level="INFO", json_format=True)

# ファイル出力
configure_logging(
    level="DEBUG",
    json_format=True,
    log_file="./logs/agent.log"
)
```

## API リファレンス

### WebAgent

| メソッド | 説明 |
|---------|------|
| `navigate(url)` | 単一URLにアクセス |
| `parallel_navigate(urls)` | 複数URLに並列アクセス |
| `run_custom_task(task_id, task_fn)` | カスタムタスクを実行 |
| `get_proxy_stats()` | プロキシ統計を取得 |
| `get_proxy_health()` | プロキシ健全性サマリを取得 |
| `health_check()` | ライブヘルスチェック実行 |
| `cleanup()` | リソースを解放 |
| `is_closed` | クローズ状態を取得 |

### BrowserWorker

| メソッド | 説明 |
|---------|------|
| `navigate(url)` | URLにアクセス |
| `get_content()` | ページコンテンツを取得 |
| `click(selector)` | 要素をクリック |
| `fill(selector, value)` | 入力フィールドに値を設定 |
| `type(selector, text, delay)` | テキストを1文字ずつ入力 |
| `screenshot(path)` | スクリーンショットを保存 |
| `evaluate(script)` | JavaScriptを実行 |
| `scroll(direction, amount)` | ページをスクロール |
| `hover(selector)` | 要素にホバー |
| `select(selector, value)` | ドロップダウンから選択 |
| `get_text(selector)` | 要素のテキストを取得 |
| `wait_for_selector(selector)` | 要素の出現を待機 |
| `wait_for_navigation()` | ナビゲーション完了を待機 |
| `press(key)` | キーボードキーを押下 |

### TokenBucketRateLimiter

| メソッド | 説明 |
|---------|------|
| `acquire()` | トークンを取得（待機あり） |
| `get_stats()` | 統計情報を取得 |
| `reset()` | リセット |

### SessionManager

| メソッド | 説明 |
|---------|------|
| `save_session(context, id)` | セッションを保存 |
| `load_session(context, id)` | セッションを読込 |
| `get_session(id)` | セッションデータを取得 |
| `delete_session(id)` | セッションを削除 |
| `list_sessions()` | セッション一覧 |
| `clear_all()` | 全セッション削除 |

### ParallelController

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `max_workers` | 5 | 最大並列数 |
| `max_retries` | 3 | 最大リトライ回数 |
| `BASE_DELAY` | 1.0s | リトライ基本待機時間 |
| `MAX_DELAY` | 30.0s | リトライ最大待機時間 |

## エラーハンドリング

### ErrorType

| タイプ | リトライ | 説明 |
|--------|---------|------|
| `TIMEOUT` | Yes | タイムアウト |
| `CONNECTION` | Yes | 接続エラー |
| `PROXY` | Yes | プロキシエラー |
| `ELEMENT_NOT_FOUND` | No | 要素が見つからない |
| `VALIDATION` | No | バリデーションエラー |
| `BROWSER_CLOSED` | No | ブラウザが閉じた |

### 自動リトライ

- 指数バックオフ: 1s → 2s → 4s → ... (最大30s)
- 新しいプロキシで再試行
- 最大3回リトライ（設定可能）

## 設定バリデーション

AgentConfigは以下のバリデーションを実行:

| フィールド | 制約 |
|-----------|------|
| `brightdata_port` | 1-65535 |
| `parallel_sessions` | 1-50 |
| `max_retries` | 0-10 |
| `proxy_type` | residential/datacenter/mobile/isp |

## テスト

```bash
# 全テスト実行
pytest tests/ -v

# カバレッジ付き
pytest tests/ --cov=src
```

## 依存関係

- Python 3.10+
- playwright
- fake-useragent
- aiohttp
- python-dotenv
- loguru
- pydantic

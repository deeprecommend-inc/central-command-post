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

---

## Web操作エージェント（Command層の実装）

プロンプトからWeb操作エージェントを実行するPythonフレームワーク。

### 機能

- **プロキシローテーション** - BrightData連携（オプション）
- **ユーザーエージェント管理** - セッションごとに一貫したUA
- **並列処理** - 最大5並列のブラウザセッション
- **AI駆動** - browser-useによる自然言語Web操作

## プロジェクト構造

```
sns-agent/
├── .env.example              # 環境変数テンプレート
├── requirements.txt          # 依存関係
├── run.py                    # CLIエントリーポイント
├── main.py                   # Pythonエントリーポイント
├── config/
│   └── settings.py           # 設定管理
└── src/
    ├── proxy_manager.py      # プロキシローテーション
    ├── ua_manager.py         # ユーザーエージェント管理
    ├── browser_worker.py     # ブラウザワーカー
    ├── parallel_controller.py # 並列処理コントローラー
    ├── web_agent.py          # メインエージェント
    └── browser_use_agent.py  # AI駆動エージェント
```

## インストール

```bash
# 1. リポジトリをクローン
git clone <repository-url>
cd sns-agent

# 2. 仮想環境を作成
python3 -m venv venv
source venv/bin/activate  # Linux/Mac

# 3. 依存関係をインストール
pip install -r requirements.txt

# 4. Playwrightブラウザをインストール
playwright install chromium
playwright install-deps chromium  # Linux: システム依存関係

# 5. 環境変数を設定（オプション）
cp .env.example .env
```

## 環境変数

| 変数 | 必須 | 説明 |
|------|------|------|
| BRIGHTDATA_USERNAME | No | BrightDataユーザー名（未設定時は直接接続） |
| BRIGHTDATA_PASSWORD | No | BrightDataパスワード |
| BRIGHTDATA_PROXY_TYPE | No | residential/datacenter/mobile/isp |
| OPENAI_API_KEY | AIモードのみ | OpenAI APIキー |
| PARALLEL_SESSIONS | No | 並列数（デフォルト: 5） |
| HEADLESS | No | ヘッドレス実行（デフォルト: true） |

## 使用方法

### CLI

```bash
# URL操作（プロキシなしでも動作）
python run.py url https://httpbin.org/ip
python run.py url https://example.com https://google.com

# AI駆動タスク（OPENAI_API_KEY必須）
python run.py ai "Go to google.com and search for python"

# デモ
python run.py demo

# ヘルプ
python run.py --help
```

### Pythonコード

```python
import asyncio
from src import WebAgent
from src.web_agent import AgentConfig

async def main():
    # プロキシなしで動作
    config = AgentConfig(
        parallel_sessions=5,
        headless=True,
    )

    # プロキシありの場合
    # config = AgentConfig(
    #     brightdata_username="your_username",
    #     brightdata_password="your_password",
    #     proxy_type="residential",
    # )

    agent = WebAgent(config)

    try:
        # 単一URLにアクセス
        result = await agent.navigate("https://httpbin.org/ip")
        if result.success:
            print(f"Title: {result.data.get('title')}")

        # 複数URLに並列アクセス
        urls = [
            "https://httpbin.org/ip",
            "https://httpbin.org/user-agent",
        ]
        results = await agent.parallel_navigate(urls)

    finally:
        await agent.cleanup()

asyncio.run(main())
```

### カスタムタスク

```python
from src.browser_worker import BrowserWorker, WorkerResult

async def custom_task(worker: BrowserWorker) -> WorkerResult:
    await worker.navigate("https://example.com")
    await worker.click("button#submit")
    await worker.fill("input#search", "検索ワード")
    await worker.screenshot("/tmp/screenshot.png")
    result = await worker.evaluate("document.title")
    return WorkerResult(success=True, data={"title": result.data})

result = await agent.run_custom_task("my_task", custom_task)
```

## API リファレンス

### WebAgent

| メソッド | 説明 |
|---------|------|
| `navigate(url)` | 単一URLにアクセス |
| `parallel_navigate(urls)` | 複数URLに並列アクセス |
| `run_custom_task(task_id, task_fn)` | カスタムタスクを実行 |
| `get_proxy_stats()` | プロキシ統計を取得 |
| `cleanup()` | リソースを解放 |

### BrowserWorker

| メソッド | 説明 |
|---------|------|
| `navigate(url)` | URLにアクセス |
| `get_content()` | ページコンテンツを取得 |
| `click(selector)` | 要素をクリック |
| `fill(selector, value)` | 入力フィールドに値を設定 |
| `screenshot(path)` | スクリーンショットを保存 |
| `evaluate(script)` | JavaScriptを実行 |

## 依存関係

- Python 3.10+
- playwright
- browser-use
- fake-useragent
- python-dotenv
- loguru
- pydantic

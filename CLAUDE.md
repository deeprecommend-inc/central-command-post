あなたは天才ハッカーであり、クラウド・インフラ・セキュリティ・ネットワークに精通したプログラマです。

## 絶対に達成すること
・Googleでアカウント生成が可能
・5件YouTubeチャンネル回っていいねができる（browser-use）
・プロキシローテーションが確立されている（brightdata）
・ユーザーエージェントが確立されている（Mulogin）
・10000件以上の異なるプロキシ、ユーザーエージェント、Googleアカウントで並列5件YouTubeチャンネル回っていいねができる（browser-use）

## 1. 全体システムアーキテクチャ


```text
[ 管理コンソール ] → [ コアコントローラー ] → [ ワークマネージャー ]
        ↓                     ↓                      ↓
[ データベース ]      [ リソースマネージャー ]   [ ブラウザワーカー群 ]
```

## 2. コアコンポーネント設計

### 2.1 リソース管理モジュール

```python
class ResourceManager:
    # プロキシ管理（BrightData）
    - プロキシプールの初期化（10,000件以上）
    - プロキシヘルスチェック
    - ローテーションロジック（使用回数、応答時間、成功率に基づく）
    - IPジャック防止のための制御（同一IPの連続使用禁止）
    
    # ユーザーエージェント管理（Mulogin連携）
    - UAプールの管理（OS、ブラウザバージョン、デバイスタイプの多様化）
    - フィンガープリント生成
    - セッションごとのUA固定
    
    # Googleアカウント管理
    - アカウント生成キュー
    - アカウント認証状態の確認
    - アカウント使用履歴の追跡
    - CAPTCHA対策モジュール
```

### 2.2 ブラウザ自動化モジュール（browser-use）

```python
class BrowserWorker:
    # セッション設定
    - プロキシ設定適用
    - ユーザーエージェント設定
    - キャッシュ・Cookie管理
    - フィンガープリントマスキング
    
    # Googleアカウント生成フロー
    - アカウント作成ページへのナビゲーション
    - フォーム自動入力（一意の情報生成）
    - 電話番号検証対策（仮想番号サービス連携）
    - CAPTCHA解決（2Captcha/AntiCaptcha連携）
    - バックアップメール設定
    - アカウント設定のカスタマイズ
    
    # YouTube操作フロー
    - Googleアカウントでのログイン
    - ターゲットチャンネルの特定
    - 動画リストの取得
    - いいね操作の実行（人間らしい遅延・動作パターン）
    - 行動パターンのランダム化（スクロール、閲覧時間）
```

### 2.3 分散処理コントローラー

```python
class DistributedController:
    # 並列処理管理
    - 5並列のブラウザセッション制御
    - リソース割り当て最適化
    - 負荷分散アルゴリズム
    
    # タスクスケジューリング
    - 操作間隔のランダム化
    - ピーク時間帯の回避
    - 24時間稼働スケジュール
    
    # エラーハンドリング
    - プロキシ切断時の自動切り替え
    - アカウントブロック時の対応
    - 再試行メカニズム（指数バックオフ）
```

## 3. 実装ロジックの詳細


### 3.1 プロキシローテーション確立（BrightData）

```text
1. プロキシリスト取得
   ↓
2. プロキシ分類（国、速度、タイプ）
   ↓
3. 使用スケジュール作成
   ↓
4. セッションごとのプロキシ割り当て
   ↓
5. パフォーマンス監視＆最適化
```

### 3.2 ユーザーエージェント確立（Mulogin）

```text
1. UAテンプレートのロード
   ↓
2. 環境変数生成（解像度、言語、タイムゾーン）
   ↓
3. フィンガープリント生成
   ↓
4. セッションへの適用
   ↓
5. 一貫性の維持（同一セッション内）
```

### 3.3 Googleアカウント生成

```text
1. メールアドレス生成（カスタムドメイン/ Gmail）
   ↓
2. 個人情報生成（一意の名前、生年月日）
   ↓
3. プロキシ経由での登録ページアクセス
   ↓
4. CAPTCHA解決
   ↓
5. 電話認証突破（SMS受信サービス）
   ↓
6. セキュリティ設定の最適化
   ↓
7. 認証情報の安全な保存
```

### 3.4 YouTubeいいね実行

```text
1. ターゲットチャンネルURLの読み込み
   ↓
2. 動画リストの取得（最新10動画）
   ↓
3. 各動画へのアクセス（自然な経路）
   ↓
4. 視聴時間のランダム化（30秒〜5分）
   ↓
5. いいねボタンのクリック（確率的に実施）
   ↓
6. 行動ログの記録
   ↓
7. セッション終了（クッキー保存）
```

## 4. セキュリティ＆隠蔽対策

### 4.1 検出回避技術

- タイミングランダム化: 操作間隔を指数分布で変動
- 行動パターン模倣: マウスムーブ、スクロールパターンの人間化
- Cookie管理: セッション維持と定期的なクリア
- ヘッダー完全性: 完全なHTTPヘッダーセットの模倣

### 4.2 レート制限対策

- 1アカウントあたりの日次操作制限の遵守
- IPごとのリクエスト頻度制御
- 行動パターンの多様化

## 5. モニタリング＆メンテナンス

### 5.1 監視システム

- 成功/失敗率のリアルタイム監視
- プロキシ速度・稼働率の追跡
- アカウント生存状況の確認
- リソース使用量の最適化

### 5.2 メンテナンスタスク

- 定期的なプロキシリストの更新
- 古いアカウントのフィルタリング
- ブラウザ設定の更新
- ログのローテーションと分析

## 6. スケーラビリティ設計

```text
初期: 5並列 → モニタリング → 最適化 → 拡張
   ↓
中規模: 50並列（プロキシ10,000、アカウント1,000）
   ↓
大規模: 分散サーバー構成による水平拡張
```

## 7. リスク管理

### 7.1 フォールバック戦略

- プロキシ障害時: 代替プロバイダーへの切り替え
- CAPTCHAサービス障害: 複数サービスの併用
- アカウント大量ブロック: 新規生成パイプラインの強化

## 8. 技術スタック推奨

## 自動化フレームワーク: browser-use / Playwright / Puppeteer

- プロキシサービス: BrightData + 複数バックアップ
- CAPTCHA解決: 2Captcha, AntiCaptcha
- インフラ: Dockerコンテナ + Kubernetes
- データベース: PostgreSQL + Redis（セッション管理）
- 監視: Prometheus + Grafana

## 9 必要な技術スタックと外部リソース一覧

### 9.1 コア自動化フレームワーク

#### browser-use（主要フレームワーク）

- **GitHub**: https://github.com/browser-use/browser-use
- **インストール**: `pip install browser-use`
- **特徴**: Playwrightベース、宣言的AI自動化
- **代替/補完**: 
  - Playwright: https://github.com/microsoft/playwright-python (`pip install playwright`)
  - Puppeteer: https://github.com/puppeteer/puppeteer

#### ブラウザ自動化関連
```bash
pip install:
- playwright-stealth  # 検出回避 https://github.com/Atubo951/playwright_stealth
- undetected-playwright  # 検出回避強化 https://github.com/ultrafunkamsterdam/undetected-playwright
- fake-useragent  # ユーザーエージェント生成 https://github.com/hellysmile/fake-useragent
- pyvirtualdisplay  # ヘッドレス表示（Linux用） https://github.com/ponty/pyvirtualdisplay
```

### 9.2 プロキシ管理（BrightData）

#### BrightData公式
- **公式サイト**: https://brightdata.com/
- **APIドキュメント**: https://brightdata.com/products/rotating-proxies
- **SDK/ライブラリ**:
  ```bash
  # BrightDataのPython SDK（公式）
  pip install brightdata-sdk  # または直接API使用
  
  # プロキシ管理ユーティリティ
  pip install proxy-tools
  pip install requests[socks]
  ```

#### プロキシ管理ライブラリ
```bash
pip install:
- aiohttp  # 非同期HTTPクライアント https://github.com/aio-libs/aiohttp
- aiosocks  # SOCKS5サポート https://github.com/nibrag/aiosocks
- proxy-checker  # プロキシチェッカー https://github.com/Anorov/PyProxyChecker
- python-socks  # SOCKSプロキシサポート https://github.com/romis2012/python-socks
```

### 9.3 アカウント生成＆管理

#### Googleアカウント自動化
```bash
pip install:
- gmail-account-generator  # 参考実装 https://github.com/hexatester/gmail-account-generator
- python-anticaptcha  # CAPTCHA解決 https://github.com/AdminAnticaptcha/anticaptcha-python
- twocaptcha  # 2Captcha API https://github.com/2captcha/2captcha-python
- phonenumbers  # 電話番号検証 https://github.com/daviddrysdale/python-phonenumbers
```

#### メール管理
```bash
pip install:
- yagmail  # Gmail APIラッパー https://github.com/kootenpv/yagmail
- imbox  # IMAPクライアント https://github.com/martinrusev/imbox
- tempmail-python  # 仮想メール https://github.com/tempmail-lol/tempmail-python
```

### 9.4 フィンガープリント＆ユーザーエージェント

#### Mulogin代替/補完
- **公式サイト**: https://mulogin.com/（商用サービス）
- **オープンソース代替**:
  ```bash
  # ブラウザフィンガープリント生成
  pip install browser-fingerprint  # https://github.com/ben-sb/browser-fingerprint
  
  # ユーザーエージェント生成
  pip install fake-useragent  # 前述
  pip install user_agent  # https://github.com/lorien/user_agent
  
  # キャンバスフィンガープリント
  pip install canvas-fingerprint  # https://github.com/antoinevastel/fpscanner
  ```

#### WebRTC/IP漏洩防止
```bash
pip install:
- webrtc-ip-leak-prevent  # https://github.com/aghorler/webrtc-ip-leak-prevent
```

### 9.5 並列処理・分散処理

#### 非同期/並列処理
```bash
pip install:
- asyncio  # 標準ライブラリ（Python 3.7+）
- aiohttp  # 前述
- aiofiles  # 非同期ファイル操作 https://github.com/Tinche/aiofiles
- asyncio-pool  # コネクションプール https://github.com/achimnol/aiotools
```

#### 分散処理フレームワーク
```bash
pip install:
- celery  # 分散タスクキュー https://github.com/celery/celery
  - redis  # ブローカー用 https://github.com/redis/redis-py
  - flower  # 監視用 https://github.com/mher/flower
  
# または
- dramatiq  # 軽量代替 https://github.com/Bogdanp/dramatiq
- rq  # Redis Queue https://github.com/rq/rq
```

#### プロセス管理
```bash
pip install:
- supervisor  # プロセス管理 https://github.com/Supervisor/supervisor
- circus  # 代替プロセス管理 https://github.com/circus-tent/circus
```

### 9.6 データベース＆ストレージ

#### メインDB
```bash
# PostgreSQL
pip install:
- psycopg2-binary  # PostgreSQLアダプタ https://github.com/psycopg/psycopg2
- asyncpg  # 非同期PostgreSQL https://github.com/MagicStack/asyncpg
- sqlalchemy  # ORM https://github.com/sqlalchemy/sqlalchemy
- alembic  # マイグレーション https://github.com/sqlalchemy/alembic
```

#### キャッシュ/キュー
```bash
# Redis
pip install:
- redis  # Redisクライアント https://github.com/redis/redis-py
- aioredis  # 非同期Redis https://github.com/aio-libs/aioredis
- redis-py-cluster  # Redisクラスター https://github.com/Grokzen/redis-py-cluster
```

### 9.7 監視・ロギング・分析

#### ロギング
```bash
pip install:
- structlog  # 構造化ログ https://github.com/hynek/structlog
- loguru  # シンプルロギング https://github.com/Delgan/loguru
- sentry-sdk  # エラー追跡 https://github.com/getsentry/sentry-python
```

#### 監視・メトリクス
```bash
pip install:
- prometheus-client  # メトリクス収集 https://github.com/prometheus/client_python
- grafana-api  # Grafana連携 https://github.com/panodata/grafana-client
- psutil  # システム監視 https://github.com/giampaolo/psutil
```

### 9.8 設定管理

#### 環境変数・設定
```bash
pip install:
- python-dotenv  # 環境変数管理 https://github.com/theskumar/python-dotenv
- dynaconf  # 動的設定管理 https://github.com/dynaconf/dynaconf
- hydra  # 設定管理フレームワーク https://github.com/facebookresearch/hydra
```

### 9.9 セキュリティ・暗号化

```bash
pip install:
- cryptography  # 暗号化 https://github.com/pyca/cryptography
- bcrypt  # パスワードハッシュ https://github.com/pyca/bcrypt
- fernet  # 対称暗号化 https://github.com/fernet/spec
```

### 9.10 ユーティリティ

```bash
pip install:
- faker  # ダミーデータ生成 https://github.com/joke2k/faker
- pydantic  # データバリデーション https://github.com/pydantic/pydantic
- tenacity  # リトライ処理 https://github.com/jd/tenacity
- tqdm  # プログレスバー https://github.com/tqdm/tqdm
- colorama  # カラー出力 https://github.com/tartley/colorama
```

### 9.11 参考GitHubリポジトリ

#### 関連プロジェクト（参考用）
1. **YouTube自動化サンプル**:
   - https://github.com/egbertbouman/youtube-comment-api
   - https://github.com/topics/youtube-automation

2. **ブラウザ自動化テンプレート**:
   - https://github.com/xtekky/google-login-bypass
   - https://github.com/ultrafunkamsterdam/playwright-stealth-proxy

3. **プロキシ管理システム**:
   - https://github.com/constverum/ProxyBroker
   - https://github.com/jundymek/free-proxy

4. **分散スクレイピングフレームワーク**:
   - https://github.com/scrapy/scrapy
   - https://github.com/Miserlou/Zappa

### 9.12 外部サービス（有料/無料）

#### CAPTCHA解決サービス
1. **2Captcha**: https://2captcha.com/ - APIキーが必要
2. **Anti-Captcha**: https://anti-captcha.com/ - APIキーが必要
3. **CapSolver**: https://www.capsolver.com/ - APIキーが必要

#### 仮想電話番号（SMS受信）
1. **SMSPVA**: https://smspva.com/ - APIサービス
2. **5Sim**: https://5sim.net/ - 仮想番号
3. **OnlineSim**: https://onlinesim.ru/ - ロシア番号

#### メールサービス
1. **Temp-Mail**: https://temp-mail
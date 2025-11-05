#!/bin/bash

###############################################################################
# SNS Orchestrator - Frontend Only Deployment Script for AWS Amplify
###############################################################################
# このスクリプトはフロントエンドのみをAWS Amplifyにデプロイします。
#
# 前提条件:
# - インフラ(RDS, ElastiCache, App Runner)が既にデプロイされていること
# - Amplifyアプリが作成されていること
#
# デプロイ方法:
# 1. GitHubリポジトリ経由 (推奨)
# 2. 手動ビルド + Zipアップロード
#
# 使用方法:
#   ./deploy-frontend.sh setup      # Amplify接続情報の確認
#   ./deploy-frontend.sh build      # フロントエンドをビルド
#   ./deploy-frontend.sh package    # デプロイパッケージの作成
#   ./deploy-frontend.sh github     # GitHub連携の手順を表示
#   ./deploy-frontend.sh manual     # 手動デプロイの手順を表示
#   ./deploy-frontend.sh status     # デプロイ状態の確認
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Project configuration
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
BUILD_DIR="${FRONTEND_DIR}/.next"
TERRAFORM_DIR="${PROJECT_ROOT}/infrastructure/frontend-only"
TERRAFORM_AMPLIFY_DIR="${PROJECT_ROOT}/infrastructure/amplify"
DEPLOY_DIR="${PROJECT_ROOT}/.deploy"
DEPLOY_PACKAGE="${DEPLOY_DIR}/frontend-deploy.zip"

# Functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    print_info "依存関係をチェック中..."

    local missing_deps=()

    if ! command -v node &> /dev/null; then
        missing_deps+=("node")
    fi

    if ! command -v npm &> /dev/null; then
        missing_deps+=("npm")
    fi

    if ! command -v aws &> /dev/null; then
        missing_deps+=("aws-cli")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "以下の依存関係が不足しています: ${missing_deps[*]}"
        print_info "インストール方法:"
        for dep in "${missing_deps[@]}"; do
            case $dep in
                node|npm)
                    echo "  - Node.js/npm: https://nodejs.org/"
                    ;;
                aws-cli)
                    echo "  - AWS CLI: https://aws.amazon.com/cli/"
                    ;;
            esac
        done
        exit 1
    fi

    print_success "すべての依存関係が確認されました"
}

check_aws_credentials() {
    print_info "AWS認証情報をチェック中..."

    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS認証情報が設定されていません"
        print_info "以下のコマンドで設定してください:"
        echo "  aws configure"
        exit 1
    fi

    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local region=$(aws configure get region)

    print_success "AWS認証情報を確認しました"
    print_info "  Account ID: ${account_id}"
    print_info "  Region: ${region}"
}

get_amplify_info() {
    print_info "Amplify情報を取得中..."

    # Try frontend-only first, then fallback to full amplify
    local tf_dir="$TERRAFORM_DIR"
    if [ ! -d "$tf_dir" ] || [ ! -f "$tf_dir/terraform.tfstate" ]; then
        tf_dir="$TERRAFORM_AMPLIFY_DIR"
    fi

    if [ ! -d "$tf_dir" ]; then
        print_warning "Terraformディレクトリが見つかりません"
        print_info "先にTerraformでAmplifyをデプロイしてください: ./deploy-frontend.sh terraform-apply"
        return 1
    fi

    cd "$tf_dir"

    if [ ! -f "terraform.tfstate" ]; then
        print_warning "terraform.tfstateが見つかりません"
        print_info "先にTerraformでAmplifyをデプロイしてください: ./deploy-frontend.sh terraform-apply"
        return 1
    fi

    local amplify_app_id=$(terraform output -raw amplify_app_id 2>/dev/null || echo "")
    local backend_url=$(terraform output -raw backend_url 2>/dev/null || terraform output -raw frontend_url 2>/dev/null | sed 's/\/frontend$//' || echo "")

    if [ -z "$amplify_app_id" ]; then
        print_error "Amplifyアプリケーションが見つかりません"
        return 1
    fi

    print_success "Amplify情報を取得しました"
    echo "  App ID: ${amplify_app_id}"
    echo "  Backend URL: ${backend_url}"

    export AMPLIFY_APP_ID="$amplify_app_id"
    export NEXT_PUBLIC_API_URL="$backend_url"

    cd "$PROJECT_ROOT"
}

build_frontend() {
    print_info "フロントエンドをビルド中..."

    # 環境変数の設定
    if ! get_amplify_info; then
        print_error "Amplify情報の取得に失敗しました"
        exit 1
    fi

    cd "$FRONTEND_DIR"

    # 依存関係のインストール
    print_info "依存関係をインストール中..."
    npm ci

    # .envファイルの作成
    print_info "環境変数を設定中..."
    cat > .env.local << EOF
NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
NEXT_PUBLIC_APP_NAME=SNS Orchestrator
EOF

    # ビルド実行
    print_info "Next.jsビルドを実行中..."
    npm run build

    print_success "フロントエンドのビルドが完了しました"
}

create_deployment_package() {
    print_info "デプロイパッケージを作成中..."

    cd "$FRONTEND_DIR"

    # ビルドされているか確認
    if [ ! -d "$BUILD_DIR" ]; then
        print_error "ビルドディレクトリが見つかりません"
        print_info "先にビルドを実行してください: ./deploy-frontend.sh build"
        exit 1
    fi

    # デプロイディレクトリの作成
    mkdir -p "$DEPLOY_DIR"
    rm -f "$DEPLOY_PACKAGE"

    # 必要なファイルをZipに圧縮
    print_info "ファイルを圧縮中..."
    zip -r "$DEPLOY_PACKAGE" \
        .next \
        public \
        package.json \
        package-lock.json \
        next.config.js \
        -x "*.git*" \
        -x "*node_modules*" \
        -x "*.env*"

    local package_size=$(du -h "$DEPLOY_PACKAGE" | cut -f1)
    print_success "デプロイパッケージを作成しました"
    print_info "  場所: ${DEPLOY_PACKAGE}"
    print_info "  サイズ: ${package_size}"
}

show_github_deploy_instructions() {
    get_amplify_info || return 1

    cat << EOF

========================================
  GitHub連携デプロイ (推奨)
========================================

AWS AmplifyはGitHubリポジトリと直接連携できます。
これにより、mainブランチへのプッシュで自動デプロイが可能になります。

手順:

1. GitHubリポジトリの準備
   - コードをGitHubリポジトリにプッシュ
   - リポジトリがprivateの場合、AWS Amplifyへのアクセス権限を付与

2. Amplifyコンソールでリポジトリを接続
   https://console.aws.amazon.com/amplify/home

   a. アプリ「${AMPLIFY_APP_ID}」を選択
   b. 「Connect repository」をクリック
   c. GitHubを選択
   d. リポジトリとブランチ(main)を選択
   e. ビルド設定を確認 (自動検出されます)

3. ビルド設定の確認 (amplify.ymlは自動生成されます)

   version: 1
   frontend:
     phases:
       preBuild:
         commands:
           - cd frontend
           - npm ci
       build:
         commands:
           - npm run build
     artifacts:
       baseDirectory: frontend/.next
       files:
         - '**/*'
     cache:
       paths:
         - frontend/node_modules/**/*

4. 環境変数の設定
   Amplifyコンソールで以下の環境変数を設定:

   NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
   NEXT_PUBLIC_APP_NAME=SNS Orchestrator

5. デプロイ開始
   - 「Save and deploy」をクリック
   - 初回デプロイには5-10分かかります

6. 自動デプロイの確認
   - mainブランチへプッシュすると自動でデプロイされます
   - プルリクエストのプレビューも自動で作成されます

========================================

EOF

    print_success "GitHub連携が最も簡単で推奨されるデプロイ方法です"
}

show_manual_deploy_instructions() {
    if [ ! -f "$DEPLOY_PACKAGE" ]; then
        print_warning "デプロイパッケージが見つかりません"
        print_info "先にパッケージを作成してください: ./deploy-frontend.sh package"
        return 1
    fi

    get_amplify_info || return 1

    cat << EOF

========================================
  手動デプロイ
========================================

GitHubを使用しない場合、AWS CLIで手動デプロイできます。

注意: Amplifyは主にGit連携を前提としているため、
      手動デプロイは限定的なサポートです。

手順:

1. デプロイパッケージの確認
   場所: ${DEPLOY_PACKAGE}

2. AWS CLIでデプロイ (オプション1: AWS CLI v2)

   # Amplify App Runner経由でデプロイする場合
   # App RunnerにNext.jsアプリをデプロイ

   a. ECRにイメージをプッシュ
      cd ${FRONTEND_DIR}
      docker build -t frontend:latest .
      # ECRへのプッシュ手順は deploy-amplify.sh build を参照

3. 代替オプション: S3 + CloudFront

   Amplifyを使わず、静的ホスティングする場合:

   a. Next.jsを静的エクスポート
      # next.config.js に以下を追加
      output: 'export'

   b. ビルド
      cd ${FRONTEND_DIR}
      npm run build

   c. S3にアップロード
      aws s3 sync out/ s3://your-bucket-name/ \\
        --delete \\
        --cache-control "public, max-age=31536000, immutable"

4. Amplify Hosting でのデプロイ (推奨)

   Amplifyコンソールから手動でデプロイ:

   a. https://console.aws.amazon.com/amplify/home にアクセス
   b. アプリ「${AMPLIFY_APP_ID}」を選択
   c. 「Deploy without Git」を選択
   d. Zipファイル「${DEPLOY_PACKAGE}」をアップロード
   e. デプロイを実行

========================================

推奨: GitHub連携を使用してください
      ./deploy-frontend.sh github

========================================

EOF
}

show_deployment_status() {
    print_info "デプロイ状態を確認中..."

    get_amplify_info || return 1

    local region=$(aws configure get region || echo "ap-northeast-1")

    print_info "Amplifyアプリの状態:"
    aws amplify get-app \
        --app-id "$AMPLIFY_APP_ID" \
        --region "$region" \
        --query 'app.[name,defaultDomain,platform,repository]' \
        --output table

    print_info ""
    print_info "最新のデプロイ状況:"
    aws amplify list-branches \
        --app-id "$AMPLIFY_APP_ID" \
        --region "$region" \
        --query 'branches[].[branchName,displayName,enableNotification]' \
        --output table
}

setup_amplify_yaml() {
    print_info "amplify.yamlをチェック中..."

    local amplify_yaml="${PROJECT_ROOT}/amplify.yaml"

    if [ -f "$amplify_yaml" ]; then
        print_success "amplify.yamlは既に存在します: ${amplify_yaml}"
    else
        print_warning "amplify.yamlが見つかりません"
        print_info "amplify.yamlはAmplifyでのビルド設定に必要です"
        print_info "amplify.yaml.exampleを参照して作成してください"
    fi
}

terraform_init() {
    print_info "Terraformを初期化中..."

    if [ ! -d "$TERRAFORM_DIR" ]; then
        print_error "Terraformディレクトリが見つかりません: $TERRAFORM_DIR"
        exit 1
    fi

    cd "$TERRAFORM_DIR"

    if ! command -v terraform &> /dev/null; then
        print_error "Terraformがインストールされていません"
        print_info "インストール: https://www.terraform.io/downloads"
        exit 1
    fi

    terraform init

    print_success "Terraformの初期化が完了しました"
    cd "$PROJECT_ROOT"
}

terraform_plan() {
    print_info "Terraformプランを作成中..."

    if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
        print_warning "terraform.tfvarsが見つかりません"
        print_info "terraform.tfvars.exampleをコピーして編集してください:"
        print_info "  cp $TERRAFORM_DIR/terraform.tfvars.example $TERRAFORM_DIR/terraform.tfvars"
        print_info "  vim $TERRAFORM_DIR/terraform.tfvars"

        read -p "バックエンドAPIのURLを入力してください: " backend_url
        if [ -z "$backend_url" ]; then
            print_error "バックエンドAPIのURLは必須です"
            exit 1
        fi

        cd "$TERRAFORM_DIR"
        terraform plan -var="backend_api_url=$backend_url" -out=tfplan
    else
        cd "$TERRAFORM_DIR"
        terraform plan -out=tfplan
    fi

    print_success "Terraformプランが作成されました"
    cd "$PROJECT_ROOT"
}

terraform_apply() {
    print_info "Terraformを適用中..."

    terraform_init
    terraform_plan

    cd "$TERRAFORM_DIR"

    print_warning "上記のプランを確認してください"
    read -p "Terraformを適用しますか? (y/n): " confirm

    if [ "$confirm" != "y" ]; then
        print_info "キャンセルしました"
        return 0
    fi

    terraform apply tfplan

    print_success "Terraformの適用が完了しました"

    # 出力を表示
    print_info ""
    print_info "========================================="
    print_info " デプロイ情報"
    print_info "========================================="
    terraform output

    cd "$PROJECT_ROOT"
}

terraform_destroy() {
    print_warning "Amplifyアプリを削除しようとしています"
    print_warning "この操作は元に戻せません"

    read -p "本当に削除しますか? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        print_info "キャンセルしました"
        return 0
    fi

    cd "$TERRAFORM_DIR"
    terraform destroy

    print_success "Amplifyアプリを削除しました"
    cd "$PROJECT_ROOT"
}

show_help() {
    cat << EOF
SNS Orchestrator - Frontend Only Deployment Script

使用方法:
  ./deploy-frontend.sh <command>

コマンド:
  terraform-init     Terraformを初期化
  terraform-plan     Terraformプランを作成
  terraform-apply    TerraformでAmplifyアプリをデプロイ (推奨)
  terraform-destroy  Amplifyアプリを削除
  setup              Amplify接続情報の確認
  build              フロントエンドをビルド
  package            デプロイパッケージの作成 (Zip)
  github             GitHub連携デプロイの手順を表示
  manual             手動デプロイの手順を表示
  status             現在のデプロイ状態を確認
  help               このヘルプを表示

推奨デプロイ手順 (Terraform + GitHub):

  1. Terraformでインフラをセットアップ
     $ ./deploy-frontend.sh terraform-apply

     ※ バックエンドAPIのURLを求められます

  2. GitHub連携の設定
     $ ./deploy-frontend.sh github

     表示された手順に従ってAmplifyコンソールで設定

  3. コードをプッシュして自動デプロイ
     $ git push origin main

手動ビルドデプロイ (非推奨):

  1. ビルド
     $ ./deploy-frontend.sh build

  2. パッケージ作成
     $ ./deploy-frontend.sh package

  3. 手動デプロイ
     $ ./deploy-frontend.sh manual

設定ファイル:
  - amplify.yaml                          Amplifyビルド設定
  - infrastructure/frontend-only/         Terraform設定
    ├── main.tf                           メイン設定
    ├── variables.tf                      変数定義
    ├── outputs.tf                        出力定義
    └── terraform.tfvars                  変数値 (作成必要)

注意事項:
  - フロントエンドのみをデプロイします
  - GitHub連携が最も簡単で推奨されます
  - Terraformでインフラを管理します
  - バックエンドAPIのURLは必須です

EOF
}

# Main
main() {
    case "${1:-}" in
        terraform-init)
            check_dependencies
            check_aws_credentials
            terraform_init
            ;;
        terraform-plan)
            check_dependencies
            check_aws_credentials
            terraform_plan
            ;;
        terraform-apply)
            check_dependencies
            check_aws_credentials
            setup_amplify_yaml
            terraform_apply
            ;;
        terraform-destroy)
            check_dependencies
            check_aws_credentials
            terraform_destroy
            ;;
        setup)
            check_dependencies
            check_aws_credentials
            get_amplify_info
            setup_amplify_yaml
            ;;
        build)
            check_dependencies
            check_aws_credentials
            build_frontend
            ;;
        package)
            check_dependencies
            create_deployment_package
            ;;
        github)
            check_dependencies
            check_aws_credentials
            show_github_deploy_instructions
            ;;
        manual)
            check_dependencies
            check_aws_credentials
            show_manual_deploy_instructions
            ;;
        status)
            check_dependencies
            check_aws_credentials
            show_deployment_status
            ;;
        help|--help|-h|"")
            show_help
            ;;
        *)
            print_error "無効なコマンド: ${1:-}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"

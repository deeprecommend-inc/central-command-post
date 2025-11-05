#!/bin/bash

###############################################################################
# SNS Orchestrator - AWS Amplify Deployment Script (超最安値構成)
###############################################################################
# このスクリプトはTerraformを使用してAWS Amplify + App Runnerでデプロイします。
#
# 構成:
# - AWS Amplify (Frontend) - 従量課金
# - AWS App Runner (Backend/Worker) - 従量課金
# - RDS PostgreSQL db.t4g.micro
# - ElastiCache Redis cache.t4g.micro
#
# 月額コスト概算: 約 $40-60/月
#
# 使用方法:
#   ./deploy-amplify.sh init    # 初期化 (初回のみ)
#   ./deploy-amplify.sh plan    # デプロイ計画の確認
#   ./deploy-amplify.sh apply   # デプロイ実行
#   ./deploy-amplify.sh destroy # リソース削除
#   ./deploy-amplify.sh status  # デプロイ状態確認
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
TERRAFORM_DIR="${PROJECT_ROOT}/infrastructure/amplify"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"

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

    if ! command -v terraform &> /dev/null; then
        missing_deps+=("terraform")
    fi

    if ! command -v aws &> /dev/null; then
        missing_deps+=("aws-cli")
    fi

    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "以下の依存関係が不足しています: ${missing_deps[*]}"
        print_info "インストール方法:"
        for dep in "${missing_deps[@]}"; do
            case $dep in
                terraform)
                    echo "  - Terraform: https://www.terraform.io/downloads"
                    ;;
                aws-cli)
                    echo "  - AWS CLI: https://aws.amazon.com/cli/"
                    ;;
                docker)
                    echo "  - Docker: https://docs.docker.com/get-docker/"
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

terraform_init() {
    print_info "Terraformを初期化中..."

    cd "$TERRAFORM_DIR"

    if [ ! -f "terraform.tfvars" ]; then
        print_warning "terraform.tfvarsが見つかりません"
        print_info "terraform.tfvars.exampleからコピーして設定してください:"
        echo "  cp ${TERRAFORM_DIR}/terraform.tfvars.example ${TERRAFORM_DIR}/terraform.tfvars"
        echo "  # terraform.tfvarsを編集して必要な値を設定"
        exit 1
    fi

    terraform init

    print_success "Terraform初期化完了"
}

build_and_push_backend() {
    print_info "Backendイメージをビルド中..."

    # AWS ECRログイン
    local region=$(aws configure get region || echo "ap-northeast-1")
    local account_id=$(aws sts get-caller-identity --query Account --output text)

    print_info "ECRにログイン中..."
    aws ecr get-login-password --region "$region" | \
        docker login --username AWS --password-stdin "${account_id}.dkr.ecr.${region}.amazonaws.com"

    # ECRリポジトリの取得
    cd "$TERRAFORM_DIR"
    local backend_repo=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "")

    if [ -z "$backend_repo" ]; then
        print_warning "ECRリポジトリが作成されていません"
        print_info "先にTerraform applyを実行してECRリポジトリを作成してください"
        exit 1
    fi

    # Backendイメージのビルドとプッシュ
    print_info "Backendイメージをビルド中..."
    cd "$BACKEND_DIR"
    docker build -t "${backend_repo}:latest" .
    docker push "${backend_repo}:latest"
    print_success "Backendイメージをプッシュしました"
}

deploy_frontend_to_amplify() {
    print_info "Amplifyへのフロントエンドデプロイ..."

    cd "$TERRAFORM_DIR"
    local amplify_app_id=$(terraform output -raw amplify_app_id 2>/dev/null || echo "")

    if [ -z "$amplify_app_id" ]; then
        print_warning "AmplifyアプリケーションIDが見つかりません"
        print_info "Terraformでインフラを先にデプロイしてください"
        exit 1
    fi

    print_info "Amplify App ID: ${amplify_app_id}"
    print_info "GitHubリポジトリを接続してください:"
    echo "  1. https://console.aws.amazon.com/amplify/home にアクセス"
    echo "  2. アプリ「${amplify_app_id}」を選択"
    echo "  3. GitHubリポジトリを接続"
    echo "  4. mainブランチをデプロイ"
}

terraform_plan() {
    print_info "Terraformプランを実行中..."

    cd "$TERRAFORM_DIR"
    terraform plan

    print_success "Terraformプラン完了"
}

terraform_apply() {
    print_info "Terraformを適用中..."

    cd "$TERRAFORM_DIR"
    terraform apply

    if [ $? -eq 0 ]; then
        print_success "デプロイ完了!"
        show_deployment_info
    else
        print_error "デプロイに失敗しました"
        exit 1
    fi
}

terraform_destroy() {
    print_warning "すべてのリソースを削除します"
    read -p "本当に削除しますか? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        print_info "削除をキャンセルしました"
        exit 0
    fi

    cd "$TERRAFORM_DIR"
    terraform destroy

    print_success "リソースの削除が完了しました"
}

show_deployment_info() {
    print_info "デプロイ情報:"

    cd "$TERRAFORM_DIR"

    echo ""
    echo "=========================================="
    echo "   デプロイ完了 (Amplify構成)"
    echo "=========================================="
    echo ""

    if terraform output backend_url &> /dev/null; then
        local backend_url=$(terraform output -raw backend_url)
        local frontend_url=$(terraform output -raw frontend_url)
        local worker_url=$(terraform output -raw worker_url)

        echo "  Backend API URL (App Runner): ${backend_url}"
        echo "  Worker URL (App Runner): ${worker_url}"
        echo "  Frontend URL (Amplify): ${frontend_url}"
        echo ""
    fi

    echo "=========================================="
    echo ""

    print_info "次のステップ:"
    echo "  1. Backendイメージのビルドとプッシュ:"
    echo "     ./deploy-amplify.sh build"
    echo ""
    echo "  2. App Runnerサービスの再デプロイ:"
    echo "     ./deploy-amplify.sh redeploy"
    echo ""
    echo "  3. Amplifyでフロントエンドをデプロイ:"
    echo "     - GitHubリポジトリを接続"
    echo "     - または手動でzip/tarをアップロード"
    echo ""
    echo "  4. データベースの初期化 (初回のみ):"
    echo "     App Runnerコンソールでコマンドを実行"
    echo ""
}

redeploy_apprunner() {
    print_info "App Runnerサービスを再デプロイ中..."

    local region=$(aws configure get region || echo "ap-northeast-1")

    # Backend再デプロイ
    print_info "Backendを再デプロイ中..."
    aws apprunner start-deployment \
        --service-arn $(aws apprunner list-services --region "$region" \
        --query "ServiceSummaryList[?ServiceName=='sns-orchestrator-backend'].ServiceArn" \
        --output text) \
        --region "$region"

    # Worker再デプロイ
    print_info "Workerを再デプロイ中..."
    aws apprunner start-deployment \
        --service-arn $(aws apprunner list-services --region "$region" \
        --query "ServiceSummaryList[?ServiceName=='sns-orchestrator-worker'].ServiceArn" \
        --output text) \
        --region "$region"

    print_success "App Runnerサービスの再デプロイを開始しました"
    print_info "デプロイ完了まで3-5分お待ちください"
}

show_status() {
    print_info "デプロイ状態を確認中..."

    cd "$TERRAFORM_DIR"

    if [ ! -f "terraform.tfstate" ]; then
        print_warning "まだデプロイされていません"
        exit 0
    fi

    terraform show
}

estimate_cost() {
    print_info "月額コスト概算 (東京リージョン):"
    echo ""
    echo "  AWS Amplify (Frontend):"
    echo "    ビルド時間: 約 $0.01/分 × 30ビルド = $0.30/月"
    echo "    ホスティング: 約 $0.15/GB × 1GB = $0.15/月"
    echo "    リクエスト: 最初の15GB無料"
    echo "    小計: 約 $0.50-2/月"
    echo ""
    echo "  App Runner (Backend, 1 vCPU, 2GB):"
    echo "    プロビジョニング: 約 $6/月"
    echo "    アクティブ: 約 $0.064/時 × 100時間 = $6.40/月"
    echo "    小計: 約 $12-15/月"
    echo ""
    echo "  App Runner (Worker, 0.25 vCPU, 0.5GB):"
    echo "    プロビジョニング: 約 $2/月"
    echo "    アクティブ: 約 $0.016/時 × 100時間 = $1.60/月"
    echo "    小計: 約 $3-5/月"
    echo ""
    echo "  RDS PostgreSQL (db.t4g.micro, 20GB):"
    echo "    約 $15-20/月"
    echo ""
    echo "  ElastiCache Redis (cache.t4g.micro):"
    echo "    約 $12-15/月"
    echo ""
    echo "  データ転送・その他:"
    echo "    約 $3-5/月"
    echo ""
    echo "  合計: 約 $45-65/月"
    echo ""
    print_success "ECS Fargateより約20-30%安価!"
}

show_help() {
    cat << EOF
SNS Orchestrator - AWS Amplify Deployment Script

使用方法:
  ./deploy-amplify.sh <command> [options]

コマンド:
  init        Terraformの初期化 (初回のみ実行)
  plan        デプロイ計画の確認
  apply       インフラのデプロイ
  build       Backendイメージのビルドとプッシュ
  redeploy    App Runnerサービスの再デプロイ
  destroy     全リソースの削除
  status      現在のデプロイ状態の確認
  cost        月額コスト概算の表示
  help        このヘルプを表示

デプロイ手順:
  1. AWS認証情報の設定
     $ aws configure

  2. terraform.tfvarsの設定
     $ cp infrastructure/amplify/terraform.tfvars.example infrastructure/amplify/terraform.tfvars
     $ vi infrastructure/amplify/terraform.tfvars

  3. Terraformの初期化
     $ ./deploy-amplify.sh init

  4. インフラのデプロイ
     $ ./deploy-amplify.sh apply

  5. Backendイメージのビルドとプッシュ
     $ ./deploy-amplify.sh build

  6. App Runnerサービスの再デプロイ
     $ ./deploy-amplify.sh redeploy

  7. Amplifyでフロントエンドをデプロイ
     - AmplifyコンソールでGitHubリポジトリを接続

超最安値構成:
  - AWS Amplify (従量課金)
  - App Runner (従量課金 + プロビジョニング最小)
  - RDS db.t4g.micro
  - ElastiCache cache.t4g.micro
  - 月額約 $45-65

利点:
  - ECS Fargateより20-30%安価
  - サーバーレス (自動スケーリング)
  - デプロイが簡単
  - ALB不要 (コスト削減)

注意事項:
  - App Runnerはプロビジョニングインスタンスで常時稼働
  - 低トラフィックなら非常にコスト効率的
  - 高トラフィックの場合はFargateを推奨

EOF
}

# Main
main() {
    case "${1:-}" in
        init)
            check_dependencies
            check_aws_credentials
            terraform_init
            ;;
        plan)
            check_dependencies
            check_aws_credentials
            terraform_plan
            ;;
        apply)
            check_dependencies
            check_aws_credentials
            terraform_apply
            ;;
        build)
            check_dependencies
            check_aws_credentials
            build_and_push_backend
            ;;
        redeploy)
            check_dependencies
            check_aws_credentials
            redeploy_apprunner
            ;;
        destroy)
            check_dependencies
            check_aws_credentials
            terraform_destroy
            ;;
        status)
            check_dependencies
            show_status
            ;;
        cost)
            estimate_cost
            ;;
        help|--help|-h)
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

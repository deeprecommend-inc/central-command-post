#!/bin/bash

###############################################################################
# SNS Orchestrator - AWS Deployment Script (最安値構成)
###############################################################################
# このスクリプトはTerraformを使用してAWS上に最安値構成でデプロイします。
#
# 構成:
# - ECS Fargate Spot (最安値)
# - RDS PostgreSQL db.t4g.micro
# - ElastiCache Redis cache.t4g.micro
# - Application Load Balancer
#
# 使用方法:
#   ./deploy.sh init    # 初期化 (初回のみ)
#   ./deploy.sh plan    # デプロイ計画の確認
#   ./deploy.sh apply   # デプロイ実行
#   ./deploy.sh destroy # リソース削除
#   ./deploy.sh status  # デプロイ状態確認
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project configuration
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/infrastructure/terraform"
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

build_and_push_images() {
    print_info "Dockerイメージをビルド中..."

    # AWS ECRログイン
    local region=$(aws configure get region || echo "ap-northeast-1")
    local account_id=$(aws sts get-caller-identity --query Account --output text)

    print_info "ECRにログイン中..."
    aws ecr get-login-password --region "$region" | \
        docker login --username AWS --password-stdin "${account_id}.dkr.ecr.${region}.amazonaws.com"

    # ECRリポジトリの取得または作成
    cd "$TERRAFORM_DIR"
    local backend_repo=$(terraform output -raw ecr_backend_repository_url 2>/dev/null || echo "")
    local frontend_repo=$(terraform output -raw ecr_frontend_repository_url 2>/dev/null || echo "")

    if [ -z "$backend_repo" ] || [ -z "$frontend_repo" ]; then
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

    # Frontendイメージのビルドとプッシュ
    print_info "Frontendイメージをビルド中..."
    cd "$FRONTEND_DIR"
    docker build -t "${frontend_repo}:latest" .
    docker push "${frontend_repo}:latest"
    print_success "Frontendイメージをプッシュしました"
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
    echo "   デプロイ完了"
    echo "=========================================="
    echo ""

    if terraform output frontend_url &> /dev/null; then
        local frontend_url=$(terraform output -raw frontend_url)
        local backend_url=$(terraform output -raw backend_api_url)

        echo "  Frontend URL: ${frontend_url}"
        echo "  Backend API URL: ${backend_url}"
        echo "  API Docs: ${backend_url}/docs"
        echo ""
    fi

    echo "  ECS Cluster: $(terraform output -raw ecs_cluster_name)"
    echo ""
    echo "=========================================="
    echo ""

    print_info "デプロイ後の手順:"
    echo "  1. データベースの初期化:"
    echo "     aws ecs execute-command --cluster <cluster-name> --task <task-id> --container backend --interactive --command \"/bin/bash\""
    echo "     python -c \"from app.models.database import init_db; import asyncio; asyncio.run(init_db())\""
    echo ""
    echo "  2. 環境変数の設定 (必要に応じて):"
    echo "     ECSタスク定義の環境変数にAPIキーを追加してください"
    echo ""
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
    echo "  ECS Fargate Spot (0.25 vCPU, 0.5GB x 3タスク):"
    echo "    約 $10-15/月 (スポット価格)"
    echo ""
    echo "  RDS PostgreSQL (db.t4g.micro, 20GB):"
    echo "    約 $15-20/月"
    echo ""
    echo "  ElastiCache Redis (cache.t4g.micro):"
    echo "    約 $12-15/月"
    echo ""
    echo "  Application Load Balancer:"
    echo "    約 $20-25/月"
    echo ""
    echo "  データ転送・その他:"
    echo "    約 $5-10/月"
    echo ""
    echo "  合計: 約 $60-85/月"
    echo ""
    print_warning "実際のコストは使用量によって変動します"
}

show_help() {
    cat << EOF
SNS Orchestrator - AWS Deployment Script

使用方法:
  ./deploy.sh <command> [options]

コマンド:
  init        Terraformの初期化 (初回のみ実行)
  plan        デプロイ計画の確認
  apply       インフラのデプロイ
  build       Dockerイメージのビルドとプッシュ
  destroy     全リソースの削除
  status      現在のデプロイ状態の確認
  cost        月額コスト概算の表示
  help        このヘルプを表示

デプロイ手順:
  1. AWS認証情報の設定
     $ aws configure

  2. terraform.tfvarsの設定
     $ cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
     $ vi infrastructure/terraform/terraform.tfvars

  3. Terraformの初期化
     $ ./deploy.sh init

  4. インフラのデプロイ
     $ ./deploy.sh apply

  5. Dockerイメージのビルドとプッシュ
     $ ./deploy.sh build

  6. ECSサービスの再起動 (新しいイメージを適用)
     $ aws ecs update-service --cluster <cluster-name> --service <service-name> --force-new-deployment

最安値構成:
  - ECS Fargate Spot (スポットインスタンス)
  - RDS db.t4g.micro
  - ElastiCache cache.t4g.micro
  - 月額約 $60-85

注意事項:
  - スポットインスタンスは中断される可能性があります
  - 本番環境では予約インスタンスの検討を推奨
  - バックアップは1日分のみ保持されます

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
            build_and_push_images
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

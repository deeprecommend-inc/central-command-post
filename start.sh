#!/bin/bash

# SNS Orchestrator Startup Script
# Version: 1.3.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}=================================================${NC}"
    echo -e "${BLUE}  SNS Orchestrator - Startup Script v1.3.0${NC}"
    echo -e "${BLUE}=================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_dependencies() {
    print_info "Checking dependencies..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_success "Docker found"

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_success "Docker Compose found"

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    print_success "Docker daemon is running"

    echo ""
}

check_ports() {
    print_info "Checking port availability..."

    PORTS_IN_USE=()
    REQUIRED_PORTS=(3006 8006 5432 6379)

    for port in "${REQUIRED_PORTS[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -tuln 2>/dev/null | grep -q ":$port "; then
            PORTS_IN_USE+=($port)
        fi
    done

    if [ ${#PORTS_IN_USE[@]} -gt 0 ]; then
        print_warning "The following ports are already in use: ${PORTS_IN_USE[*]}"
        echo ""
        print_info "Port usage details:"
        for port in "${PORTS_IN_USE[@]}"; do
            case $port in
                3006)
                    echo "  Port 3006: Frontend (Next.js)"
                    ;;
                8006)
                    echo "  Port 8006: Backend API (FastAPI)"
                    ;;
                5432)
                    echo "  Port 5432: PostgreSQL Database"
                    ;;
                6379)
                    echo "  Port 6379: Redis"
                    ;;
            esac
        done
        echo ""

        print_warning "Options:"
        echo "  1. Stop the processes using these ports"
        echo "  2. Stop existing Docker containers"
        echo "  3. Exit and manually resolve"
        echo ""
        read -p "Enter choice (1/2/3): " -n 1 -r
        echo

        case $REPLY in
            1)
                print_info "Attempting to stop processes on ports..."
                for port in "${PORTS_IN_USE[@]}"; do
                    PID=$(lsof -ti:$port 2>/dev/null)
                    if [ ! -z "$PID" ]; then
                        print_info "Killing process $PID on port $port..."
                        kill -9 $PID 2>/dev/null || true
                    fi
                done
                sleep 2
                print_success "Processes stopped"
                ;;
            2)
                print_info "Stopping Docker containers..."
                docker ps -q | xargs -r docker stop 2>/dev/null || true
                sleep 2
                print_success "Docker containers stopped"
                ;;
            3)
                print_info "Exiting. Please manually resolve port conflicts."
                echo ""
                print_info "To check port usage:"
                echo "  lsof -i :3006"
                echo "  lsof -i :8006"
                echo "  lsof -i :5432"
                echo "  lsof -i :6379"
                exit 1
                ;;
            *)
                print_error "Invalid choice. Exiting."
                exit 1
                ;;
        esac
    else
        print_success "All required ports are available"
    fi

    echo ""
}

check_env_file() {
    print_info "Checking environment configuration..."

    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from template..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success "Created .env file from template"
            print_warning "Please edit .env file and configure your API keys before starting."
            echo ""
            print_info "Required configurations:"
            echo "  - Database credentials (default values work for development)"
            echo "  - OAuth credentials (YouTube, X, Instagram, TikTok)"
            echo "  - AI API keys (Anthropic/OpenAI)"
            echo "  - Proxy API keys (optional: BrightData, MuLogin)"
            echo ""
            read -p "Press Enter to continue after configuring .env, or Ctrl+C to exit..."
        else
            print_error ".env.example not found. Cannot create .env file."
            exit 1
        fi
    else
        print_success ".env file found"
    fi

    echo ""
}

stop_existing_containers() {
    print_info "Checking for existing containers..."

    # Check for this project's containers
    if docker-compose ps -q 2>/dev/null | grep -q .; then
        print_warning "Stopping existing SNS Orchestrator containers..."
        docker-compose down --remove-orphans
        print_success "Stopped existing containers"
    fi

    # Also check for containers that might be using our ports
    CONFLICTING_CONTAINERS=$(docker ps --filter "publish=3006" --filter "publish=8006" --filter "publish=5432" --filter "publish=6379" -q 2>/dev/null)

    if [ ! -z "$CONFLICTING_CONTAINERS" ]; then
        print_warning "Found containers using required ports"
        print_info "Stopping conflicting containers..."
        echo "$CONFLICTING_CONTAINERS" | xargs docker stop 2>/dev/null || true
        print_success "Stopped conflicting containers"
    else
        print_success "No conflicting containers found"
    fi

    # Wait a moment for ports to be released
    sleep 2

    echo ""
}

start_services() {
    print_info "Starting services with Docker Compose..."

    # Build and start services
    if docker-compose up -d --build 2>&1 | tee /tmp/docker-compose-start.log; then
        print_success "Services started successfully"
    else
        print_error "Failed to start services"
        echo ""
        print_info "Error details:"
        cat /tmp/docker-compose-start.log | grep -i "error\|failed" || cat /tmp/docker-compose-start.log | tail -20
        echo ""
        print_warning "Common issues:"
        echo "  1. Ports still in use - Try: ./stop.sh --clean && ./start.sh"
        echo "  2. Docker daemon not running - Start Docker Desktop/Engine"
        echo "  3. Insufficient resources - Check Docker resource limits"
        echo ""
        print_info "To debug further:"
        echo "  docker-compose logs"
        echo "  docker ps -a"
        exit 1
    fi

    echo ""
}

wait_for_services() {
    print_info "Waiting for services to be ready..."

    # Wait for PostgreSQL
    print_info "Waiting for PostgreSQL..."
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U sns_user &> /dev/null; then
            print_success "PostgreSQL is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "PostgreSQL failed to start in time"
            exit 1
        fi
        sleep 1
    done

    # Wait for Redis
    print_info "Waiting for Redis..."
    for i in {1..30}; do
        if docker-compose exec -T redis redis-cli ping &> /dev/null; then
            print_success "Redis is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            print_error "Redis failed to start in time"
            exit 1
        fi
        sleep 1
    done

    # Wait for Backend API
    print_info "Waiting for Backend API..."
    for i in {1..60}; do
        if curl -s http://localhost:8006/health &> /dev/null; then
            print_success "Backend API is ready"
            break
        fi
        if [ $i -eq 60 ]; then
            print_error "Backend API failed to start in time"
            print_info "Check logs with: docker-compose logs backend"
            exit 1
        fi
        sleep 1
    done

    echo ""
}

initialize_database() {
    print_info "Initializing database..."

    # Check if database is already initialized
    DB_INITIALIZED=$(docker-compose exec -T postgres psql -U sns_user -d sns_orchestrator -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")

    if [ "$DB_INITIALIZED" -gt "0" ]; then
        print_warning "Database already initialized (found $DB_INITIALIZED tables)"
        read -p "Reinitialize database? This will drop all tables. (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Skipping database initialization"
            echo ""
            return
        fi
    fi

    docker-compose exec -T backend python -c "
from app.models.database import init_db
import asyncio
asyncio.run(init_db())
print('Database initialized successfully')
" 2>/dev/null

    if [ $? -eq 0 ]; then
        print_success "Database initialized"
    else
        print_warning "Database initialization may have issues. Check logs with: docker-compose logs backend"
    fi

    echo ""
}

display_status() {
    print_header
    print_success "SNS Orchestrator is now running!"
    echo ""

    echo -e "${GREEN}Service URLs:${NC}"
    echo "  Frontend:     http://localhost:3006"
    echo "  Backend API:  http://localhost:8006"
    echo "  API Docs:     http://localhost:8006/docs"
    echo "  PostgreSQL:   localhost:5432"
    echo "  Redis:        localhost:6379"
    echo ""

    echo -e "${BLUE}Container Status:${NC}"
    docker-compose ps
    echo ""

    echo -e "${YELLOW}Useful Commands:${NC}"
    echo "  View logs:           docker-compose logs -f"
    echo "  View backend logs:   docker-compose logs -f backend"
    echo "  View frontend logs:  docker-compose logs -f frontend"
    echo "  Stop services:       docker-compose down"
    echo "  Restart services:    docker-compose restart"
    echo ""

    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Open http://localhost:3006 in your browser"
    echo "  2. Configure OAuth connections for SNS platforms"
    echo "  3. Create your first run"
    echo ""
}

show_logs() {
    print_info "Showing logs (Ctrl+C to exit)..."
    echo ""
    docker-compose logs -f
}

# Main execution
main() {
    print_header

    # Parse command line arguments
    FOLLOW_LOGS=false
    SKIP_CHECKS=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--follow-logs)
                FOLLOW_LOGS=true
                shift
                ;;
            --skip-checks)
                SKIP_CHECKS=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  -f, --follow-logs    Follow logs after startup"
                echo "  --skip-checks        Skip dependency checks"
                echo "  -h, --help          Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done

    # Run startup sequence
    if [ "$SKIP_CHECKS" = false ]; then
        check_dependencies
        check_ports
    fi

    check_env_file
    stop_existing_containers
    start_services
    wait_for_services
    initialize_database
    display_status

    # Follow logs if requested
    if [ "$FOLLOW_LOGS" = true ]; then
        show_logs
    else
        print_info "Run 'docker-compose logs -f' to follow logs"
    fi
}

# Run main function
main "$@"

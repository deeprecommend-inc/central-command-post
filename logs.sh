#!/bin/bash

# SNS Orchestrator Logs Viewer
# Version: 1.3.0

set -e

# Colors for output
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=================================================${NC}"
    echo -e "${BLUE}  SNS Orchestrator - Logs Viewer v1.3.0${NC}"
    echo -e "${BLUE}=================================================${NC}"
    echo ""
}

show_usage() {
    echo "Usage: $0 [SERVICE] [OPTIONS]"
    echo ""
    echo "Services:"
    echo "  all        Show logs from all services (default)"
    echo "  backend    Show backend API logs"
    echo "  frontend   Show frontend logs"
    echo "  worker     Show worker logs"
    echo "  postgres   Show PostgreSQL logs"
    echo "  redis      Show Redis logs"
    echo ""
    echo "Options:"
    echo "  -f, --follow     Follow log output"
    echo "  -n, --tail NUM   Show last NUM lines (default: 100)"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    Show last 100 lines from all services"
    echo "  $0 backend -f         Follow backend logs"
    echo "  $0 frontend -n 50     Show last 50 lines from frontend"
}

# Detect Docker Compose command
detect_docker_compose() {
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        echo "Docker Compose is not installed."
        exit 1
    fi
}

main() {
    SERVICE="all"
    FOLLOW=""
    TAIL="100"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            backend|frontend|worker|postgres|redis|all)
                SERVICE=$1
                shift
                ;;
            -f|--follow)
                FOLLOW="-f"
                shift
                ;;
            -n|--tail)
                TAIL="$2"
                shift 2
                ;;
            -h|--help)
                print_header
                show_usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    print_header

    # Detect Docker Compose
    detect_docker_compose

    # Build docker-compose logs command
    if [ "$SERVICE" = "all" ]; then
        $DOCKER_COMPOSE logs --tail="$TAIL" $FOLLOW
    else
        $DOCKER_COMPOSE logs --tail="$TAIL" $FOLLOW "$SERVICE"
    fi
}

main "$@"

#!/bin/bash

# SNS Orchestrator Stop Script
# Version: 1.3.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=================================================${NC}"
    echo -e "${BLUE}  SNS Orchestrator - Stop Script v1.3.0${NC}"
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

# Detect Docker Compose command
detect_docker_compose() {
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        print_error "Docker Compose is not installed."
        exit 1
    fi
}

stop_services() {
    print_info "Stopping services..."

    if $DOCKER_COMPOSE ps -q 2>/dev/null | grep -q .; then
        $DOCKER_COMPOSE down

        if [ $? -eq 0 ]; then
            print_success "Services stopped successfully"
        else
            print_error "Failed to stop services"
            exit 1
        fi
    else
        print_warning "No running services found"
    fi

    echo ""
}

remove_volumes() {
    print_warning "This will remove all data volumes (database, redis, audit logs)"
    read -p "Are you sure you want to remove volumes? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Removing volumes..."
        $DOCKER_COMPOSE down -v

        if [ $? -eq 0 ]; then
            print_success "Volumes removed"
        else
            print_error "Failed to remove volumes"
            exit 1
        fi
    else
        print_info "Keeping volumes"
    fi

    echo ""
}

clean_all() {
    print_warning "This will remove all containers, volumes, and networks"
    read -p "Are you sure you want to clean everything? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning all resources..."
        $DOCKER_COMPOSE down -v --remove-orphans

        if [ $? -eq 0 ]; then
            print_success "All resources cleaned"
        else
            print_error "Failed to clean resources"
            exit 1
        fi
    else
        print_info "Cancelled"
    fi

    echo ""
}

show_status() {
    print_info "Current status:"
    echo ""
    $DOCKER_COMPOSE ps
    echo ""
}

main() {
    print_header

    # Detect Docker Compose
    detect_docker_compose

    # Parse command line arguments
    REMOVE_VOLUMES=false
    CLEAN_ALL=false
    SHOW_STATUS=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--volumes)
                REMOVE_VOLUMES=true
                shift
                ;;
            --clean)
                CLEAN_ALL=true
                shift
                ;;
            -s|--status)
                SHOW_STATUS=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  -v, --volumes    Stop services and remove volumes"
                echo "  --clean          Stop services and remove all resources"
                echo "  -s, --status     Show current status"
                echo "  -h, --help       Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                Stop services (keep data)"
                echo "  $0 --volumes      Stop services and remove data"
                echo "  $0 --clean        Stop and clean everything"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done

    if [ "$SHOW_STATUS" = true ]; then
        show_status
        exit 0
    fi

    if [ "$CLEAN_ALL" = true ]; then
        clean_all
    elif [ "$REMOVE_VOLUMES" = true ]; then
        remove_volumes
    else
        stop_services
    fi

    print_success "Done!"
}

main "$@"

#!/bin/bash

# SNS Orchestrator Reset Script
# Version: 1.3.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=================================================${NC}"
    echo -e "${BLUE}  SNS Orchestrator - Reset Script v1.3.0${NC}"
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

confirm_reset() {
    echo -e "${RED}WARNING: This will:${NC}"
    echo "  - Stop all services"
    echo "  - Remove all containers"
    echo "  - Delete all data (database, redis, audit logs)"
    echo "  - Remove all volumes"
    echo ""
    read -p "Are you absolutely sure? Type 'RESET' to confirm: " -r
    echo

    if [[ $REPLY != "RESET" ]]; then
        print_info "Reset cancelled"
        exit 0
    fi
}

reset_system() {
    print_header

    # Detect Docker Compose
    detect_docker_compose

    confirm_reset

    print_info "Starting reset process..."
    echo ""

    # Stop all services
    print_info "Stopping services..."
    $DOCKER_COMPOSE down -v --remove-orphans
    print_success "Services stopped and volumes removed"

    # Clean up audit logs
    print_info "Cleaning audit logs..."
    if [ -d "./audit_logs" ]; then
        rm -rf ./audit_logs/*.log 2>/dev/null || true
        print_success "Audit logs cleaned"
    fi

    # Remove .next build
    print_info "Cleaning frontend build..."
    if [ -d "./frontend/.next" ]; then
        rm -rf ./frontend/.next
        print_success "Frontend build cleaned"
    fi

    # Remove Python cache
    print_info "Cleaning Python cache..."
    find ./backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find ./backend -type f -name "*.pyc" -delete 2>/dev/null || true
    print_success "Python cache cleaned"

    echo ""
    print_success "Reset complete!"
    echo ""
    print_info "To start fresh, run: ./start.sh"
}

main() {
    reset_system
}

main "$@"

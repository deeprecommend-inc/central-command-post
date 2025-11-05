#!/bin/bash

# Port Cleanup Script
# Quick fix for port conflicts

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}  Port Cleanup Script${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

print_info "Checking ports 3006, 8006, 5432, 6379..."
echo ""

PORTS=(3006 8006 5432 6379)
FREED=0

for port in "${PORTS[@]}"; do
    PID=$(lsof -ti:$port 2>/dev/null || true)

    if [ ! -z "$PID" ]; then
        print_warning "Port $port is in use by PID $PID"

        # Get process info
        PROCESS_INFO=$(ps -p $PID -o comm= 2>/dev/null || echo "unknown")
        echo "  Process: $PROCESS_INFO"

        # Kill the process
        if kill -9 $PID 2>/dev/null; then
            print_success "Killed process on port $port"
            FREED=$((FREED + 1))
        else
            print_error "Failed to kill process on port $port (might need sudo)"
        fi
    else
        print_success "Port $port is available"
    fi
done

echo ""

# Stop all Docker containers using these ports
print_info "Checking Docker containers..."

ALL_CONTAINERS=$(docker ps -q 2>/dev/null || true)

if [ ! -z "$ALL_CONTAINERS" ]; then
    print_warning "Stopping all running Docker containers..."
    docker stop $(docker ps -q) 2>/dev/null || true
    print_success "Docker containers stopped"
    FREED=$((FREED + 1))
else
    print_success "No Docker containers running"
fi

# Clean up docker-compose for this project
if [ -f "docker-compose.yml" ]; then
    print_info "Cleaning up docker-compose..."
    docker-compose down --remove-orphans 2>/dev/null || true
    print_success "Docker-compose cleaned"
fi

echo ""

if [ $FREED -gt 0 ]; then
    print_success "Cleanup complete! Freed $FREED port(s)/container(s)"
    echo ""
    print_info "You can now run: ./start.sh"
else
    print_success "All ports were already available"
fi

echo ""

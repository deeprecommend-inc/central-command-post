#!/usr/bin/env bash
set -euo pipefail

# CCP - Central Command Platform Setup
# Supports: macOS, Ubuntu/Debian (including WSL2)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin) OS="macos" ;;
        Linux)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                OS="wsl2"
            else
                OS="linux"
            fi
            ;;
        *) error "Unsupported OS: $(uname -s)" ;;
    esac
    info "Detected OS: $OS"
}

# Install system dependencies
install_deps() {
    info "Installing system dependencies..."
    case "$OS" in
        macos)
            if ! command -v brew &>/dev/null; then
                error "Homebrew is required. Install from https://brew.sh"
            fi
            brew install python@3.12 zstd || true
            ;;
        linux|wsl2)
            apt-get update
            apt-get install -y python3 python3-pip python3-venv zstd curl
            ;;
    esac
}

# Install Ollama
install_ollama() {
    if command -v ollama &>/dev/null; then
        info "Ollama already installed: $(ollama --version)"
        return
    fi

    info "Installing Ollama..."
    case "$OS" in
        macos)
            brew install ollama
            ;;
        linux|wsl2)
            curl -fsSL https://ollama.ai/install.sh | sh
            ;;
    esac
    info "Ollama installed"
}

# Start Ollama service
start_ollama() {
    info "Starting Ollama..."
    case "$OS" in
        macos)
            if ! pgrep -x ollama &>/dev/null; then
                ollama serve &>/dev/null &
                sleep 2
            fi
            ;;
        linux|wsl2)
            if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
                systemctl start ollama 2>/dev/null || true
            else
                # WSL2 or environments without systemd
                if ! pgrep -x ollama &>/dev/null; then
                    ollama serve &>/dev/null &
                    sleep 2
                fi
            fi
            ;;
    esac

    # Wait for Ollama API
    for i in $(seq 1 10); do
        if curl -s http://localhost:11434/api/tags &>/dev/null; then
            info "Ollama API is ready"
            return
        fi
        sleep 1
    done
    warn "Ollama API not responding. You may need to start it manually: ollama serve"
}

# Pull default LLM model
pull_model() {
    local model="${1:-dolphin3}"
    info "Pulling model: $model"
    ollama pull "$model"
    info "Model $model ready"
}

# Setup Python virtual environment
setup_venv() {
    info "Setting up Python virtual environment..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    info "Python dependencies installed"
}

# Install Playwright browsers
install_playwright() {
    info "Installing Playwright browsers..."
    source venv/bin/activate
    playwright install chromium
    case "$OS" in
        linux|wsl2)
            playwright install-deps chromium 2>/dev/null || true
            ;;
    esac
    info "Playwright ready"
}

# Setup .env file
setup_env() {
    if [ ! -f ".env" ]; then
        info "Creating .env from .env.example..."
        cp .env.example .env
        info ".env created. Edit it to configure API keys and settings."
    else
        info ".env already exists"
    fi
}

# Verify installation
verify() {
    info "Verifying installation..."
    local ok=true

    if command -v ollama &>/dev/null; then
        info "  ollama: OK"
    else
        warn "  ollama: NOT FOUND"
        ok=false
    fi

    if [ -d "venv" ]; then
        info "  venv: OK"
    else
        warn "  venv: NOT FOUND"
        ok=false
    fi

    source venv/bin/activate 2>/dev/null
    if python3 -c "import playwright" 2>/dev/null; then
        info "  playwright: OK"
    else
        warn "  playwright: NOT FOUND"
        ok=false
    fi

    if python3 -c "import browser_use" 2>/dev/null; then
        info "  browser-use: OK"
    else
        warn "  browser-use: NOT FOUND"
        ok=false
    fi

    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        info "  ollama API: OK"
    else
        warn "  ollama API: NOT RUNNING"
    fi

    if $ok; then
        info "Setup complete"
    else
        warn "Some components missing. Check warnings above."
    fi
}

# Main
main() {
    local model="dolphin3"
    local skip_model=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --model)
                model="$2"
                shift 2
                ;;
            --skip-model)
                skip_model=true
                shift
                ;;
            --help|-h)
                echo "Usage: ./setup.sh [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --model NAME     LLM model to pull (default: dolphin3)"
                echo "  --skip-model     Skip model download"
                echo "  -h, --help       Show this help"
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done

    detect_os
    install_deps
    install_ollama
    start_ollama
    if ! $skip_model; then
        pull_model "$model"
    fi
    setup_venv
    install_playwright
    setup_env
    verify

    echo ""
    info "Quick start:"
    info "  source venv/bin/activate"
    info "  python run.py ai --local \"Go to example.com and get the title\" --no-proxy"
}

main "$@"

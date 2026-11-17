#!/usr/bin/env bash
# ==============================================================================
# Buda Secret Santa - Startup Script
# Starts the bot inside the virtual environment with pre-flight checks.
# ==============================================================================

set -euo pipefail

# Text formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python3"

# 1. Check virtual environment
if [ ! -f "${VENV_PYTHON}" ]; then
    log_error "Virtual environment not found at .venv/"
    log_error "Please run the setup script first:"
    log_error "  ./setup.sh"
    exit 1
fi

# 2. Check configuration file
if [ ! -f .env ]; then
    log_error "Configuration file .env not found!"
    if [ -f .env.example ]; then
        log_info "Creating default .env from template..."
        cp .env.example .env
    fi
    log_error "Please edit .env and configure your DISCORD_TOKEN before starting:"
    log_error "  nano .env"
    exit 1
fi

# 3. Check DISCORD_TOKEN value in .env
TOKEN_VAL="$(grep -E "^DISCORD_TOKEN=" .env | cut -d '=' -f2- | tr -d ' "\r\n' || true)"
if [ -z "${TOKEN_VAL}" ] || [ "${TOKEN_VAL}" = "your_bot_token_here" ]; then
    echo -e "${RED}${BOLD}"
    echo "=========================================================="
    echo "  ❌ ERROR: DISCORD_TOKEN is not configured in .env!      "
    echo "=========================================================="
    echo -e "${NC}"
    echo "Please open .env and insert your Discord Bot Token:"
    echo "  nano .env"
    echo ""
    echo "Need a token? Generate one at:"
    echo "  https://discord.com/developers/applications"
    echo ""
    exit 1
fi

# 4. Ensure required data directories exist
mkdir -p data/backups assets

# 5. Launch the bot
echo -e "${CYAN}${BOLD}🎅 Starting Buda Secret Santa Bot...${NC}"
log_info "Python environment: ${VENV_PYTHON}"
log_info "Working directory:  ${SCRIPT_DIR}"
echo ""

# Execute run.py passing through any arguments
exec "${VENV_PYTHON}" run.py "$@"

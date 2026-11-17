#!/usr/bin/env bash
# ==============================================================================
# Buda Secret Santa - Debian & Debian-based Systems Setup Script
# Supports: Debian 11/12+, Ubuntu 20.04/22.04/24.04+, Linux Mint, Pop!_OS, etc.
# ==============================================================================

set -euo pipefail

# Text formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo -e "${CYAN}${BOLD}"
echo "=========================================================="
echo "   🎅 Buda Secret Santa — Debian Setup & Installation     "
echo "=========================================================="
echo -e "${NC}"

# 1. Check OS distribution
log_info "Verifying operating system compatibility..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_LIKE="${ID_LIKE:-}"
    OS_NAME="${PRETTY_NAME:-$OS_ID}"
    log_ok "Detected OS: ${OS_NAME}"

    if ! echo "${OS_ID} ${OS_LIKE}" | grep -qEi "debian|ubuntu|mint|pop|raspbian"; then
        log_warn "This script is optimized for Debian/Ubuntu derivatives."
        log_warn "Proceeding anyway, but package manager steps may differ."
    fi
else
    log_warn "Could not read /etc/os-release. Assuming Debian-compatible system."
fi

# 2. Determine root / sudo privilege
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        log_error "'sudo' is not installed and you are not running as root."
        log_error "Please run as root or install sudo: apt-get install -y sudo"
        exit 1
    fi
fi

# 3. Install required system packages
log_info "Updating apt package index and installing dependencies..."
export DEBIAN_FRONTEND=noninteractive
${SUDO} apt-get update -qq

PACKAGES=(
    python3
    python3-venv
    python3-pip
    python3-dev
    build-essential
    libsqlite3-dev
    ca-certificates
    curl
    git
)

log_info "Installing system packages: ${PACKAGES[*]}"
${SUDO} apt-get install -y "${PACKAGES[@]}"
log_ok "System packages installed successfully."

# 4. Check Python version (requires >= 3.10)
PYTHON_BIN="python3"
PY_VERSION="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
log_info "Found Python version: ${PY_VERSION}"

PY_MAJOR="$(${PYTHON_BIN} -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$(${PYTHON_BIN} -c 'import sys; print(sys.version_info.minor)')"

if [ "${PY_MAJOR}" -lt 3 ] || { [ "${PY_MAJOR}" -eq 3 ] && [ "${PY_MINOR}" -lt 10 ]; }; then
    log_error "Python 3.10 or newer is required (found ${PY_VERSION})."
    log_error "Please install a newer Python version (e.g. from deadsnakes PPA on Ubuntu or pyenv)."
    exit 1
fi
log_ok "Python version ${PY_VERSION} is supported."

# 5. Create project directories
log_info "Ensuring project storage directories exist..."
mkdir -p data/backups
mkdir -p assets
log_ok "Directories verified: data/, data/backups/, assets/"

# 6. Setup Python virtual environment
VENV_DIR="${SCRIPT_DIR}/.venv"
if [ ! -d "${VENV_DIR}" ]; then
    log_info "Creating virtual environment in .venv..."
    ${PYTHON_BIN} -m venv "${VENV_DIR}"
    log_ok "Virtual environment created."
else
    log_ok "Existing virtual environment found in .venv."
fi

# 7. Install / upgrade Python packages
log_info "Upgrading pip and installing project dependencies..."
"${VENV_DIR}/bin/python3" -m pip install --upgrade pip --quiet
"${VENV_DIR}/bin/python3" -m pip install -r requirements.txt --quiet
log_ok "Python dependencies installed successfully."

# 8. Check and prepare .env file
if [ ! -f .env ]; then
    log_info "Creating .env configuration from .env.example..."
    cp .env.example .env
    log_warn "A fresh .env file has been created."
    log_warn "👉 Please edit .env and configure your DISCORD_TOKEN before starting!"
else
    log_ok "Configuration file .env exists."
fi

# 9. Set executable permissions
chmod +x run.py start.sh setup.sh 2>/dev/null || true

# 10. Summary & Next Steps
echo ""
echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo -e "${GREEN}${BOLD}   🎉 Setup Completed Successfully!                      ${NC}"
echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo -e "  1. Configure your Discord credentials:"
echo -e "     ${CYAN}nano .env${NC}"
echo -e "     (Fill in ${BOLD}DISCORD_TOKEN${NC}, and optionally ${BOLD}GUILD_ID${NC} & ${BOLD}SANTA_CHANNEL_ID${NC})"
echo ""
echo -e "  2. Test run the bot manually:"
echo -e "     ${CYAN}./start.sh${NC}"
echo ""
echo -e "  3. (Optional) Install as a 24/7 background systemd service:"
echo -e "     ${CYAN}./scripts/install_service.sh${NC}"
echo ""

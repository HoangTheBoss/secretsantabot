#!/usr/bin/env bash
# ==============================================================================
# Buda Secret Santa - Systemd Service Installer for Debian / Ubuntu
# Configures the bot to run 24/7 in the background with auto-restart on boot/crash.
# ==============================================================================

set -euo pipefail

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${SCRIPT_DIR}"

SERVICE_NAME="budasecretsanta"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
TEMPLATE_FILE="${SCRIPT_DIR}/systemd/budasecretsanta.service.template"

echo -e "${CYAN}${BOLD}"
echo "=========================================================="
echo "   ⚙️ Installing Buda Secret Santa as a Systemd Service   "
echo "=========================================================="
echo -e "${NC}"

# Check systemd availability
if ! command -v systemctl >/dev/null 2>&1; then
    log_error "systemctl not found. This system does not appear to use systemd as init system."
    exit 1
fi

# Determine sudo privilege
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        log_error "'sudo' is required to install systemd services. Please run as root."
        exit 1
    fi
fi

# Detect user and group
CURRENT_USER="$(id -un)"
CURRENT_GROUP="$(id -gn)"

log_info "Configuring service parameters:"
echo "  • Service name:      ${SERVICE_NAME}.service"
echo "  • Working directory: ${SCRIPT_DIR}"
echo "  • Execution user:    ${CURRENT_USER}"
echo "  • Execution group:   ${CURRENT_GROUP}"
echo "  • Python binary:     ${SCRIPT_DIR}/.venv/bin/python3"
echo ""

if [ ! -f "${SCRIPT_DIR}/.venv/bin/python3" ]; then
    log_error "Virtual environment not found at ${SCRIPT_DIR}/.venv"
    log_error "Please run ./setup.sh before installing the service."
    exit 1
fi

if [ ! -f "${TEMPLATE_FILE}" ]; then
    log_error "Service template not found at ${TEMPLATE_FILE}"
    exit 1
fi

# Generate temporary service file with replacements
TEMP_SERVICE="$(mktemp)"
sed \
    -e "s|{{USER}}|${CURRENT_USER}|g" \
    -e "s|{{GROUP}}|${CURRENT_GROUP}|g" \
    -e "s|{{WORKDIR}}|${SCRIPT_DIR}|g" \
    "${TEMPLATE_FILE}" > "${TEMP_SERVICE}"

log_info "Writing service file to ${SERVICE_FILE}..."
${SUDO} cp "${TEMP_SERVICE}" "${SERVICE_FILE}"
${SUDO} chmod 644 "${SERVICE_FILE}"
rm -f "${TEMP_SERVICE}"

log_info "Reloading systemd daemon..."
${SUDO} systemctl daemon-reload

log_info "Enabling ${SERVICE_NAME}.service on boot..."
${SUDO} systemctl enable "${SERVICE_NAME}.service"

log_info "Starting ${SERVICE_NAME}.service..."
${SUDO} systemctl restart "${SERVICE_NAME}.service"

sleep 1
if ${SUDO} systemctl is-active --quiet "${SERVICE_NAME}.service"; then
    log_ok "${SERVICE_NAME}.service is ACTIVE and RUNNING!"
else
    log_warn "${SERVICE_NAME}.service was created, but may have exited."
    log_warn "Check status with: sudo systemctl status ${SERVICE_NAME}"
fi

echo ""
echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo -e "${GREEN}${BOLD}   🎉 Service Installation Complete!                      ${NC}"
echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo ""
echo -e "${BOLD}Useful Management Commands:${NC}"
echo -e "  • Check live logs:       ${CYAN}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  • Check service status:  ${CYAN}sudo systemctl status ${SERVICE_NAME}${NC}"
echo -e "  • Restart bot:           ${CYAN}sudo systemctl restart ${SERVICE_NAME}${NC}"
echo -e "  • Stop bot:              ${CYAN}sudo systemctl stop ${SERVICE_NAME}${NC}"
echo ""

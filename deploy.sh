#!/bin/bash
set -e

# ============================================================
#  Crypto Signal Aggregator — Zero-Setup Backend Deploy Script
#  Deploys FastAPI backend on any Linux server.
#  Frontend is deployed separately (e.g. Vercel).
#
#  Usage:
#    chmod +x deploy.sh
#    ./deploy.sh
#
#  Port (edit below):
#    API_PORT = 8603   (FastAPI — public, serves /docs)
# ============================================================

API_PORT=8603
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$APP_DIR/apps/api"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${CYAN}[→]${NC} $1"; }

echo ""
echo "============================================"
echo "  Crypto Signal Aggregator — Backend Deploy "
echo "============================================"
echo ""

# ----------------------------------------------------------
# 1. Detect OS and install system dependencies
# ----------------------------------------------------------
info "Checking system dependencies..."

install_python() {
    if ! command -v python3 &>/dev/null; then
        info "Installing Python 3..."
        if command -v apt-get &>/dev/null; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv curl
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3 python3-pip python3-virtualenv curl
        elif command -v yum &>/dev/null; then
            sudo yum install -y python3 python3-pip python3-virtualenv curl
        fi
        log "Python installed: $(python3 --version)"
    else
        log "Python already installed: $(python3 --version)"
    fi
}

install_node() {
    if ! command -v node &>/dev/null; then
        info "Installing Node.js 18 (needed for PM2)..."
        if command -v apt-get &>/dev/null; then
            curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
            sudo apt-get install -y nodejs
        elif command -v dnf &>/dev/null; then
            curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
            sudo dnf install -y nodejs
        elif command -v yum &>/dev/null; then
            curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
            sudo yum install -y nodejs
        else
            err "Unsupported package manager. Install Node.js 18+ manually."
            exit 1
        fi
        log "Node.js installed: $(node --version)"
    else
        log "Node.js already installed: $(node --version)"
    fi
}

install_pm2() {
    if ! command -v pm2 &>/dev/null; then
        info "Installing PM2..."
        npm install -g pm2
        log "PM2 installed: $(pm2 --version)"
    else
        log "PM2 already installed: $(pm2 --version)"
    fi
}

install_python
install_node
install_pm2

# ----------------------------------------------------------
# 2. Check for .env file
# ----------------------------------------------------------
info "Checking environment configuration..."

if [ ! -f "$APP_DIR/.env" ] && [ ! -f "$API_DIR/.env" ]; then
    warn "No .env file found!"
    warn "Creating a template at $APP_DIR/.env — edit it with your values."

    cat > "$APP_DIR/.env" <<'ENVEOF'
# === Database (remote PostgreSQL) ===
DATABASE_URL=postgresql+asyncpg://user:password@your-db-host:5432/crypto_signals

# === Redis (remote) ===
REDIS_URL=rediss://default:password@your-redis-host:6379

# === Telegram ===
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=

# === App ===
SECRET_KEY=change-me-to-a-long-random-string
DEBUG=false

# === Email (optional) ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
NOTIFICATION_FROM_EMAIL=

# === API Keys (optional) ===
MORALIS_API_KEY=
COINMARKETCAP_API_KEY=
ENVEOF

    err "Please edit $APP_DIR/.env with your actual values, then re-run this script."
    exit 1
fi

log "Environment file found"

# ----------------------------------------------------------
# 3. Set up Python virtual environment & install backend deps
# ----------------------------------------------------------
info "Setting up FastAPI backend..."

cd "$API_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    log "Python virtual environment created"
fi

source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
log "Backend dependencies installed"

deactivate

# ----------------------------------------------------------
# 4. Detect public IP
# ----------------------------------------------------------
PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || curl -s --max-time 5 icanhazip.com 2>/dev/null || echo "localhost")
info "Detected public IP: $PUBLIC_IP"

# ----------------------------------------------------------
# 5. Create PM2 ecosystem file
# ----------------------------------------------------------
info "Creating PM2 process configuration..."

cat > "$APP_DIR/ecosystem.config.js" <<PMEOF
module.exports = {
  apps: [
    {
      name: 'api',
      cwd: '${API_DIR}',
      script: 'venv/bin/uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port ${API_PORT}',
      interpreter: 'none',
      env: {
        PATH: '${API_DIR}/venv/bin:' + process.env.PATH,
      },
      max_memory_restart: '1G',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
    },
  ],
};
PMEOF

log "PM2 ecosystem config created"

# ----------------------------------------------------------
# 6. Stop existing instances (if any) and start fresh
# ----------------------------------------------------------
info "Starting API service..."

cd "$APP_DIR"
pm2 delete ecosystem.config.js 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save

# ----------------------------------------------------------
# 7. Set up PM2 to start on boot
# ----------------------------------------------------------
info "Configuring auto-start on reboot..."
pm2 startup 2>/dev/null | tail -1 | grep -q "sudo" && {
    warn "Run the 'sudo env PATH=...' command printed above to enable auto-start on boot."
}

# ----------------------------------------------------------
# 8. Done!
# ----------------------------------------------------------
echo ""
echo "============================================"
echo -e "  ${GREEN}Backend Deployment Complete!${NC}"
echo "============================================"
echo ""
echo -e "  API (FastAPI):        ${CYAN}http://${PUBLIC_IP}:${API_PORT}${NC}"
echo -e "  API Docs (Swagger):   ${CYAN}http://${PUBLIC_IP}:${API_PORT}/docs${NC}"
echo -e "  API Docs (ReDoc):     ${CYAN}http://${PUBLIC_IP}:${API_PORT}/redoc${NC}"
echo -e "  Health Check:         ${CYAN}http://${PUBLIC_IP}:${API_PORT}/health${NC}"
echo -e "  WebSocket:            ${CYAN}ws://${PUBLIC_IP}:${API_PORT}/api/v1/live/stream${NC}"
echo ""
echo "  Useful commands:"
echo "    pm2 status          — Check if the API is running"
echo "    pm2 logs api        — View API logs"
echo "    pm2 restart api     — Restart the API"
echo "    pm2 stop api        — Stop the API"
echo ""
echo "  Vercel environment variables for your frontend:"
echo -e "    API_URL              = ${CYAN}http://${PUBLIC_IP}:${API_PORT}${NC}"
echo -e "    NEXT_PUBLIC_WS_URL   = ${CYAN}ws://${PUBLIC_IP}:${API_PORT}/api/v1/live/stream${NC}"
echo ""
echo -e "  ${YELLOW}Make sure port ${API_PORT} is open in your firewall.${NC}"
echo ""

#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  NagaForge — One-shot server setup script
#  Run as root on AWS Lightsail (Ubuntu 22.04) after uploading code
#  Usage:  bash setup.sh
# ─────────────────────────────────────────────────────────────

set -e  # stop on any error

# ── Colours ──────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
info() { echo -e "${YELLOW}→ $1${NC}"; }
err()  { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo ""
echo "======================================================"
echo "   NagaForge Construction ERP — Server Setup"
echo "======================================================"
echo ""

# ── Detect uploaded folder ────────────────────────────────────
info "Looking for uploaded project folder..."
if   [ -d "/root/Construction" ];   then SRC="/root/Construction"
elif [ -d "/home/ubuntu/Construction" ]; then SRC="/home/ubuntu/Construction"
elif [ -d "$(pwd)/Construction" ];  then SRC="$(pwd)/Construction"
elif [ -d "$(pwd)/backend" ];       then SRC="$(pwd)"
else
  err "Cannot find the Construction folder. Make sure you uploaded it first.
  Expected location: /root/Construction  or  /home/ubuntu/Construction"
fi
ok "Found project at: $SRC"

APP_DIR="/opt/nagaforge"
BACKEND="$APP_DIR/backend"
FRONTEND="$APP_DIR/frontend"

# ── 1. System packages ────────────────────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx git curl
ok "System packages installed"

# ── 2. Copy project to /opt/nagaforge ────────────────────────
info "Setting up app directory at $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r "$SRC/"* "$APP_DIR/"
ok "Files copied to $APP_DIR"

# ── 3. Python virtual environment ────────────────────────────
info "Creating Python virtual environment..."
cd "$BACKEND"
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet gunicorn
ok "Python dependencies installed"

# ── 4. Initialise database ────────────────────────────────────
info "Initialising database..."
cd "$BACKEND"
source venv/bin/activate
python3 - <<'PYEOF'
from database import engine
from models import Base
Base.metadata.create_all(engine)
print("  Database tables created")
PYEOF

# Create subscription plans if not exist
python3 - <<'PYEOF'
from database import SessionLocal
from models import SubscriptionPlan
db = SessionLocal()
if db.query(SubscriptionPlan).count() == 0:
    plans = [
        SubscriptionPlan(name="free",         display_name="Free",         price_monthly=0,    price_annual=0,     max_users=3,   max_projects=2,  max_storage_gb=1,  features=["projects","workers","tasks"]),
        SubscriptionPlan(name="starter",      display_name="Starter",      price_monthly=2499, price_annual=24990, max_users=10,  max_projects=5,  max_storage_gb=10, features=["projects","workers","tasks","finance","documents","inventory"]),
        SubscriptionPlan(name="professional", display_name="Professional",  price_monthly=7999, price_annual=79990, max_users=50,  max_projects=20, max_storage_gb=50, features=["projects","workers","tasks","finance","documents","inventory","bim","qc","safety","structural","scheduling","siteops"]),
        SubscriptionPlan(name="enterprise",   display_name="Enterprise",    price_monthly=0,    price_annual=0,     max_users=-1,  max_projects=-1, max_storage_gb=500,features=["all"]),
    ]
    for p in plans:
        db.add(p)
    db.commit()
    print("  Subscription plans created")
db.close()
PYEOF
ok "Database ready"

# ── 5. Systemd service ────────────────────────────────────────
info "Creating systemd service..."
cat > /etc/systemd/system/nagaforge.service <<EOF
[Unit]
Description=NagaForge Construction ERP
After=network.target

[Service]
User=root
WorkingDirectory=$BACKEND
Environment="PATH=$BACKEND/venv/bin"
ExecStart=$BACKEND/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nagaforge
systemctl start nagaforge
sleep 3

if systemctl is-active --quiet nagaforge; then
  ok "NagaForge service running"
else
  err "Service failed to start. Check: journalctl -u nagaforge -n 50"
fi

# ── 6. Nginx config ───────────────────────────────────────────
info "Configuring nginx..."
cat > /etc/nginx/sites-available/nagaforge <<'EOF'
server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 50M;
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# Remove default site, enable ours
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/nagaforge /etc/nginx/sites-enabled/nagaforge

nginx -t && systemctl restart nginx
ok "Nginx configured and running"

# ── 7. Firewall (ufw) ─────────────────────────────────────────
info "Configuring firewall..."
ufw allow 22/tcp   > /dev/null 2>&1 || true
ufw allow 80/tcp   > /dev/null 2>&1 || true
ufw allow 443/tcp  > /dev/null 2>&1 || true
ufw --force enable > /dev/null 2>&1 || true
ok "Firewall configured"

# ── 8. Summary ────────────────────────────────────────────────
SERVER_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "YOUR_SERVER_IP")

echo ""
echo "======================================================"
echo -e "${GREEN}  NagaForge is LIVE!${NC}"
echo "======================================================"
echo ""
echo "  App URL      →  http://$SERVER_IP/app"
echo "  Landing page →  http://$SERVER_IP"
echo "  Demo         →  http://$SERVER_IP/demo"
echo "  LinkedIn     →  http://$SERVER_IP/linkedin"
echo "  Walkthrough  →  http://$SERVER_IP/walkthrough"
echo "  API Docs     →  http://$SERVER_IP/docs"
echo ""
echo "  Default login:  admin / Admin@123"
echo ""
echo "  Useful commands:"
echo "  → View logs:     journalctl -u nagaforge -f"
echo "  → Restart app:   systemctl restart nagaforge"
echo "  → App status:    systemctl status nagaforge"
echo ""
echo "  Optional — add free HTTPS (need a domain first):"
echo "  → apt install certbot python3-certbot-nginx -y"
echo "  → certbot --nginx -d yourdomain.com"
echo "======================================================"

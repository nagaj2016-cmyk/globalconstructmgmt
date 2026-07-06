#!/usr/bin/env bash
# NagaForge — pull latest from GitHub and restart the service on the server.
# Run manually (bash deploy/deploy.sh) or from CI (see .github/workflows/deploy.yml).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nagaforge/globalconstructmgmt}"
SERVICE="${SERVICE:-nagaforge}"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"

echo "▶ Fetching latest ($BRANCH)…"
git fetch --all --quiet
git reset --hard "origin/${BRANCH}"      # server mirrors GitHub exactly (no local edits kept)

echo "▶ Installing backend dependencies…"
./venv/bin/pip install -q -r backend/requirements.txt

# The app runs its idempotent DB migration automatically on boot, so a restart is
# all that's needed. Restart via systemd (falls back to a friendly message if the
# unit isn't installed yet).
echo "▶ Restarting service ($SERVICE)…"
if systemctl list-unit-files | grep -q "^${SERVICE}.service"; then
  sudo systemctl restart "$SERVICE"
  sudo systemctl --no-pager --lines=0 status "$SERVICE" || true
else
  echo "  (systemd unit '${SERVICE}' not found — start the app manually or install the unit from deploy/nagaforge.service)"
fi

echo "✅ Deployed commit: $(git rev-parse --short HEAD)"

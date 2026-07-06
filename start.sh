#!/bin/bash
# NagaForge — Quick Start Script

echo "======================================"
echo "  NagaForge — Starting up..."
echo "======================================"

# ── Local dev environment ─────────────────────────────────────────────
# DEBUG=true relaxes the production security guard. For a real deployment,
# leave DEBUG unset and export a strong SECRET_KEY + ADMIN_PASSWORD instead.
export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-dev-only-secret-$(whoami)-change-for-prod}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"
# Comma-separated CORS allowlist (never '*').
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:8000,http://127.0.0.1:8000}"

# Install deps
cd backend
pip install -r requirements.txt --quiet

# The app runs an idempotent migration on boot: it adds tenant columns, seeds
# roles, languages, country code packs + proofs, and creates the demo account.
echo "▶ Starting FastAPI backend on http://localhost:8000"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

sleep 3

echo ""
echo "✅ NagaForge running at: http://localhost:8000"
echo "📖 API Docs at:          http://localhost:8000/docs"
echo ""
echo "🔑 Accounts:"
echo "   • admin / \$ADMIN_PASSWORD  (platform admin — sees everything)"
echo "   • demo  / demo123          (demo workspace — use the Load/Delete demo data buttons)"
echo "   New real accounts start empty and see only their own company's data."
echo ""
echo "▶ Opening browser..."
sleep 1
open "http://localhost:8000" 2>/dev/null || xdg-open "http://localhost:8000" 2>/dev/null || echo "   → Open http://localhost:8000 in your browser"
echo ""
echo "Press Ctrl+C to stop."
wait $BACKEND_PID

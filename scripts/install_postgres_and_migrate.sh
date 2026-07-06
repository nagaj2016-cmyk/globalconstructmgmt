#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/nagaforge-gpt}"
SERVICE_NAME="${SERVICE_NAME:-nagaforgese}"
DB_NAME="${DB_NAME:-nagaforge}"
DB_USER="${DB_USER:-nagaforge}"
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 24)}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
POSTGRES_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo or as root."
  exit 1
fi

if [[ -f "${APP_DIR}/backend/construction.db" ]]; then
  SQLITE_DB="${APP_DIR}/backend/construction.db"
elif [[ -f "${APP_DIR}/construction.db" ]]; then
  SQLITE_DB="${APP_DIR}/construction.db"
else
  echo "Could not find construction.db under ${APP_DIR} or ${APP_DIR}/backend."
  exit 1
fi

echo "Using SQLite source: ${SQLITE_DB}"
echo "Installing PostgreSQL..."
apt-get update
apt-get install -y postgresql postgresql-contrib libpq-dev

systemctl enable postgresql
systemctl start postgresql

echo "Creating PostgreSQL user/database..."
sudo -u postgres psql <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
      CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
   ELSE
      ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
   END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\\gexec
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

echo "Backing up SQLite database..."
cp -a "${SQLITE_DB}" "${SQLITE_DB}.backup.$(date +%Y%m%d-%H%M%S)"

echo "Installing PostgreSQL Python driver..."
"${APP_DIR}/venv/bin/pip" install "psycopg2-binary>=2.9.0"

echo "Migrating SQLite data to PostgreSQL..."
"${APP_DIR}/venv/bin/python" "${APP_DIR}/scripts/migrate_sqlite_to_postgres.py" \
  --app-dir "${APP_DIR}" \
  --sqlite "${SQLITE_DB}" \
  --postgres-url "${POSTGRES_URL}"

echo "Writing systemd DATABASE_URL override..."
mkdir -p "/etc/systemd/system/${SERVICE_NAME}.service.d"
cat >"/etc/systemd/system/${SERVICE_NAME}.service.d/database.conf" <<EOF
[Service]
Environment="DATABASE_URL=${POSTGRES_URL}"
EOF

systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"

echo "Verifying service..."
systemctl status "${SERVICE_NAME}" --no-pager

cat <<EOF

PostgreSQL migration complete.

Database: ${DB_NAME}
User:     ${DB_USER}
Password: ${DB_PASSWORD}

IMPORTANT: Store this password safely.
Systemd override:
  /etc/systemd/system/${SERVICE_NAME}.service.d/database.conf

SQLite backup was created next to:
  ${SQLITE_DB}
EOF

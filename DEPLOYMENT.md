# Deploying NagaForge to globalconstructmgmt.com

This is the concrete checklist to take the platform live on your domain, on PostgreSQL, over HTTPS.

## What you need (the short list)

| # | Requirement | Notes |
|---|-------------|-------|
| 1 | A Linux server (VPS/EC2), Ubuntu 22.04, 2 vCPU / 4 GB RAM minimum | DigitalOcean, Hetzner, AWS EC2, etc. |
| 2 | PostgreSQL 14+ | On the same box, or managed (AWS RDS / DO Managed DB) |
| 3 | The domain `globalconstructmgmt.com` with DNS you control | An `A` record for `@` and `www` → server IP |
| 4 | A TLS certificate | Free via Let's Encrypt / certbot |
| 5 | Secrets set as env vars | `SECRET_KEY`, DB password, admin/demo passwords |
| 6 | Nginx as reverse proxy | Provided config in `deploy/` |
| 7 | Python 3.10+ | For the FastAPI backend |
| 8 | (Optional) SMTP + object storage (S3) | Only when you outgrow local email/uploads |

Everything else (schema, roles, languages, country code packs, the demo account) is created automatically on first boot by the built-in migration.

---

## 1. DNS

Point the domain at your server's public IP:

```
A     @      <SERVER_IP>
A     www    <SERVER_IP>
```

Wait for propagation (`dig globalconstructmgmt.com +short` should return your IP).

## 2. Server packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx postgresql postgresql-contrib \
                    libpq-dev certbot python3-certbot-nginx git
```

(Skip `postgresql*` if you use a managed database.)

## 3. Create the database

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE nagaforge LOGIN PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE nagaforge OWNER nagaforge;
GRANT ALL PRIVILEGES ON DATABASE nagaforge TO nagaforge;
SQL
```

## 4. Application user + code

```bash
sudo useradd --system --create-home --home-dir /opt/nagaforge-gpt nagaforge
sudo -u nagaforge -H bash
cd /opt/nagaforge-gpt
git clone <YOUR_REPO> .            # or copy the project here
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt   # includes psycopg2 + gunicorn
mkdir -p uploads
exit
```

## 5. Environment / secrets

```bash
sudo cp /opt/nagaforge-gpt/.env.example /etc/nagaforge.env
sudo nano /etc/nagaforge.env      # fill in every CHANGE_ME
# generate the signing key:
python3 -c "import secrets;print(secrets.token_urlsafe(48))"
sudo chmod 600 /etc/nagaforge.env
sudo chown nagaforge:nagaforge /etc/nagaforge.env
```

Required values: `SECRET_KEY`, `DATABASE_URL` (the `postgresql+psycopg2://...` URL), `ADMIN_PASSWORD`, `DEMO_PASSWORD`, and `CORS_ORIGINS=https://globalconstructmgmt.com,https://www.globalconstructmgmt.com`. Keep `DEBUG=false` — the app **refuses to start** in production with a default secret, a default admin password, or `CORS_ORIGINS=*`.

## 6. (Only if migrating existing data) SQLite → PostgreSQL

If you have real data in `construction.db` you want to keep:

```bash
sudo -u nagaforge /opt/nagaforge-gpt/venv/bin/python \
     /opt/nagaforge-gpt/scripts/migrate_sqlite_to_postgres.py \
     --app-dir /opt/nagaforge-gpt \
     --sqlite  /opt/nagaforge-gpt/backend/construction.db \
     --postgres-url "postgresql+psycopg2://nagaforge:CHANGE_ME_DB_PASSWORD@127.0.0.1:5432/nagaforge"
```

This copies rows, resets sequences, then creates and seeds the platform tables (roles, languages, country code packs, proofs, demo tenant). If you're starting fresh, skip this — first boot seeds everything.

## 7. Run as a service

```bash
sudo cp /opt/nagaforge-gpt/deploy/nagaforge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nagaforge
sudo systemctl status nagaforge          # should be active (running)
curl -s localhost:8000/api/info          # health check
```

On this first start the app runs its idempotent migration: adds tenant columns, seeds the 13 roles, 4 languages, 6 countries + code packs with official proof sources, and creates the `admin` and `demo` accounts.

## 8. Nginx + HTTPS

```bash
sudo cp /opt/nagaforge-gpt/deploy/nginx-globalconstructmgmt.conf \
        /etc/nginx/sites-available/globalconstructmgmt.com
sudo ln -s /etc/nginx/sites-available/globalconstructmgmt.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Issue + auto-install the TLS certificate and the HTTP→HTTPS redirect:
sudo certbot --nginx -d globalconstructmgmt.com -d www.globalconstructmgmt.com
```

Certbot sets up auto-renewal. Your site is now live at `https://globalconstructmgmt.com`.

## 9. First login

- `admin` / `ADMIN_PASSWORD` — platform operator, sees everything.
- `demo` / `DEMO_PASSWORD` — demo workspace; use the **Load / Delete demo data** buttons.
- New real accounts (self-signup or created by an admin) start empty and see **only their own company's data**.
- The **language selector on the login screen** sets the language for the whole session and is remembered on that browser.

---

## Operations

**Backups (do this before launch):**

```bash
# nightly Postgres dump
echo '0 2 * * * nagaforge pg_dump "$DATABASE_URL" | gzip > /opt/nagaforge-gpt/backups/db-$(date +\%F).sql.gz' \
  | sudo tee /etc/cron.d/nagaforge-backup
# also back up /opt/nagaforge-gpt/uploads (rsync/S3)
```

**Updating the app:**

```bash
sudo -u nagaforge -H bash -c 'cd /opt/nagaforge-gpt && git pull && ./venv/bin/pip install -r backend/requirements.txt'
sudo systemctl restart nagaforge     # migration re-runs idempotently on boot
```

**Logs:** `journalctl -u nagaforge -f`

## Go-live security checklist

- [ ] `DEBUG=false` and a real 48-char `SECRET_KEY` in `/etc/nagaforge.env`
- [ ] `ADMIN_PASSWORD` and `DEMO_PASSWORD` changed from defaults
- [ ] `CORS_ORIGINS` lists only your https origins (no `*`)
- [ ] HTTPS working; HTTP redirects to HTTPS (certbot)
- [ ] Firewall: allow 80/443/22 only (`ufw allow 'Nginx Full' && ufw allow OpenSSH && ufw enable`)
- [ ] PostgreSQL not exposed to the public internet (bind to localhost or a private subnet)
- [ ] Nightly DB backups verified restorable
- [ ] `.env`, `*.db`, `uploads/` excluded from git (already in `.gitignore`)

## Scaling notes (later, not needed for launch)

- Move uploads to S3 + CloudFront when local disk/backup becomes a bottleneck.
- Add Redis for caching/sessions (already stubbed in requirements).
- Put the app behind a load balancer and run multiple `nagaforge` service instances; Postgres stays the single source of truth and tenant isolation holds across instances.

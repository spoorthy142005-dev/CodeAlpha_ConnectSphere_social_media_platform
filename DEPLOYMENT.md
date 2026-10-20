# ConnectSphere — Production Deployment & Operations Guide

This document describes the operational architecture, environment configuration, database management, static and media pipelines, and deployment procedures for **ConnectSphere**.

---

## 1. Architecture Overview

- **Web Framework:** Django 6.1 (Python 3.12 / 3.13)
- **Application Server (WSGI):** Gunicorn (multi-worker UNIX socket / TCP listener)
- **Static Assets:** WhiteNoise with manifest cache-busting and Brotli/gzip compression
- **Media Storage:** Isolated `media/` directory with local storage or S3-compatible object storage
- **Relational Database:** 
  - Local / Staging: SQLite (`db.sqlite3`)
  - Production: PostgreSQL (`psycopg` v3 driver via `dj-database-url`)
- **Reverse Proxy / TLS Termination:** Nginx, Caddy, or Cloud Load Balancer (AWS ALB, Cloudflare)

---

## 2. Environment Variables & Configuration

ConnectSphere utilizes `python-dotenv` to load environment variables from a local `.env` file or direct container/systemd environment injections.

Copy `.env.example` to `.env` to begin:
```bash
cp .env.example .env
```

| Variable | Required in Prod? | Default | Description |
| :--- | :---: | :--- | :--- |
| `DJANGO_DEBUG` | Yes | `True` | Must be set to `False` in production. Disables debug tracebacks and enables security hardening. |
| `DJANGO_SECRET_KEY` | Yes | *None (Fails if empty)* | Cryptographically random 50+ character secret key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `DJANGO_ALLOWED_HOSTS` | Yes | `127.0.0.1,localhost` | Comma-separated list of valid Host headers (e.g. `connectsphere.example.com`). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Yes | *Empty* | Comma-separated list of origins permitted to issue POST requests (e.g. `https://connectsphere.example.com`). |
| `DATABASE_URL` | Optional | *SQLite fallback* | PostgreSQL connection string. Format: `postgres://<user>:<password>@<host>:<port>/<dbname>`. |
| `DJANGO_SECURE_SSL_REDIRECT` | Optional | `True` | Enforces HTTPS redirection. Set to `False` if SSL is terminated at an edge proxy and forwarded via `X-Forwarded-Proto`. |
| `DJANGO_SECURE_HSTS_SECONDS` | Optional | `31536000` | HTTP Strict Transport Security duration (1 year). |
| `GUNICORN_BIND` | Optional | `0.0.0.0:8000` | Address and port for Gunicorn binding. |
| `GUNICORN_WORKERS` | Optional | `4` | Number of worker processes (`2 * CPU cores`). |
| `GUNICORN_TIMEOUT` | Optional | `30` | Request timeout before worker restart. |

---

## 3. Database Management & Migration Procedures

### Local Development (SQLite)
By default, when `DATABASE_URL` is omitted, ConnectSphere operates on `db.sqlite3`:
```bash
python manage.py migrate
```

### Production (PostgreSQL)
1. Provision a PostgreSQL 15+ database instance and dedicated user:
   ```sql
   CREATE DATABASE connectsphere_prod;
   CREATE USER connectsphere_user WITH PASSWORD 'secure_generated_password';
   GRANT ALL PRIVILEGES ON DATABASE connectsphere_prod TO connectsphere_user;
   ALTER DATABASE connectsphere_prod OWNER TO connectsphere_user;
   ```
2. Configure `DATABASE_URL` in your production environment:
   ```bash
   export DATABASE_URL="postgres://connectsphere_user:secure_generated_password@127.0.0.1:5432/connectsphere_prod"
   ```
3. Run migrations against PostgreSQL:
   ```bash
   python manage.py migrate --noinput
   ```

### Backup and Disaster Recovery
- **SQLite:** 
  ```bash
  # Atomic backup using SQLite backup API or copy while idle
  sqlite3 db.sqlite3 ".backup 'backups/db_backup_$(date +%Y%m%d_%H%M%S).sqlite3'"
  ```
- **PostgreSQL:**
  ```bash
  # Automated daily logical dump
  pg_dump -Fc -h localhost -U connectsphere_user connectsphere_prod > "backups/pg_dump_$(date +%Y%m%d_%H%M%S).dump"
  
  # Point-in-time restore
  pg_restore -c -h localhost -U connectsphere_user -d connectsphere_prod "backups/pg_dump_20261020.dump"
  ```

---

## 4. Static Assets & User Media Architecture

### Static Assets (WhiteNoise)
ConnectSphere uses **WhiteNoise** with `CompressedManifestStaticFilesStorage`. Static assets (CSS, JavaScript, brand SVGs) are post-processed, hashed with unique content digests for infinite caching, and compressed (gzip/Brotli).
```bash
python manage.py collectstatic --noinput
```
*Note: Static files are served directly by the application server or reverse proxy from `staticfiles/`.*

### User Uploaded Media (`media/`)
User avatars, post images, and community icons are stored in `media/`.
- **Isolation:** Media files are strictly segregated from static assets.
- **Production Serving:**
  - When self-hosting on a single VM, configure Nginx to serve `/media/` directly from disk with restrictive execute permissions (`X-Content-Type-Options: nosniff`).
  - For horizontally scaled deployments, use `django-storages` with an S3 / Google Cloud Storage bucket.

---

## 5. Production Server Startup

### Using Gunicorn (Linux Production Environment)
Execute using the included production configuration file:
```bash
gunicorn -c gunicorn.conf.py config.wsgi:application
```

### Systemd Service Configuration (`/etc/systemd/system/connectsphere.service`)
```ini
[Unit]
Description=ConnectSphere Django Gunicorn Daemon
After=network.target postgresql.service

[Service]
User=connectsphere
Group=connectsphere
WorkingDirectory=/var/www/connectsphere
EnvironmentFile=/var/www/connectsphere/.env
ExecStart=/var/www/connectsphere/venv/bin/gunicorn -c gunicorn.conf.py config.wsgi:application
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy Configuration
```nginx
server {
    listen 80;
    server_name connectsphere.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name connectsphere.example.com;

    ssl_certificate /etc/letsencrypt/live/connectsphere.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/connectsphere.example.com/privkey.pem;

    client_max_body_size 5M;

    # Media uploads
    location /media/ {
        alias /var/www/connectsphere/media/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Static assets fallback
    location /static/ {
        alias /var/www/connectsphere/staticfiles/;
        expires 365d;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # Application WSGI proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

---

## 6. Automated Testing & Quality Checks

Run all verification suites prior to code deployment:
```bash
# 1. Django System Consistency Check
python manage.py check

# 2. Production Security Audit
python manage.py check --deploy

# 3. Migration Completeness Validation
python manage.py makemigrations --check --dry-run

# 4. Static Asset Manifest Verification
python manage.py collectstatic --noinput

# 5. Full Automated Test Suite
python manage.py test --verbosity=2
```

---

## 7. Deployment & Zero-Downtime Rollback Procedures

### Standard Deployment Sequence
1. Pull latest verified commit:
   ```bash
   git pull origin master
   ```
2. Activate virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run database migrations:
   ```bash
   python manage.py migrate --noinput
   ```
4. Collect and hash static assets:
   ```bash
   python manage.py collectstatic --noinput
   ```
5. Reload application workers gracefully:
   ```bash
   sudo systemctl reload connectsphere
   ```

### Rollback Procedure
If a regression or runtime issue occurs post-deploy:
1. Revert to the previous stable Git commit:
   ```bash
   git checkout <PREVIOUS_STABLE_COMMIT_HASH>
   ```
2. If migrations need rollback:
   ```bash
   python manage.py migrate <app_name> <previous_migration_name>
   ```
3. Re-collect static assets and reload workers:
   ```bash
   python manage.py collectstatic --noinput
   sudo systemctl restart connectsphere
   ```

---

## 8. Known Limitations & Unverified External Portions

- **PostgreSQL Production Instance:** ConnectSphere includes full driver compatibility via `psycopg` and `dj-database-url`. While verified locally with SQLite and through dry-run migration checks, connection to an external live PostgreSQL cluster requires setting `DATABASE_URL` in your production environment.
- **External Media Storage:** The codebase is configured for local media directory storage. For horizontal multi-server clusters, an S3 backend (`django-storages`) should be configured for the media bucket.

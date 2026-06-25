# GitHub Actions CI/CD Guide

## Pipeline Overview

```
Pull Request → CI (lint + typecheck + tests)
Push to main → Build (Docker build + push to GHCR)
Tag v*.*.* → Deploy (SSH to Oracle VM + alembic + health check)
Manual → Rollback (pull previous tag + restart)
Weekly → Security (Trivy + pip-audit + Gitleaks)
```

---

## Workflows

### `ci.yml` — PR Validation

Triggered on every PR to `main`.

| Job | Tool | What it checks |
|---|---|---|
| `lint` | ruff | Code style, unused imports, formatting |
| `typecheck` | mypy | Type annotation correctness |
| `test` | pytest | All tests with real PostgreSQL + Redis services |

Coverage report uploaded to Codecov.

### `build.yml` — Docker Build & Push

Triggered on push to `main`.

- Builds `apps/api/Dockerfile`
- Pushes to `ghcr.io/OWNER/newsiq/newsiq-api` with tags:
  - `sha-<short>` (always)
  - `latest` (always, for main branch)
- Uses GitHub Actions cache for Docker layer caching

### `deploy.yml` — Production Deployment

Triggered on tag push matching `v*.*.*`.

```bash
git tag v1.2.0
git push origin v1.2.0
```

Steps:
1. Pull new Docker image on Oracle VM
2. Run `alembic upgrade head` against Neon
3. Restart `--profile prod` services
4. Health check `GET /ready` × 5 attempts
5. Tag release in Sentry (if configured)

### `rollback.yml` — Manual Rollback

Triggered manually via GitHub UI (`workflow_dispatch`).

Inputs:
- `target_tag` — the image tag to roll back to (e.g. `v1.1.0` or `sha-abc1234`)
- `reason` — audit log reason

Steps:
1. Pull target image
2. Restart prod services with that image
3. Validate health

> [!CAUTION]
> Rollback does NOT run `alembic downgrade`. Schema changes are never automatically reverted.
> If a schema migration is incompatible, restore from Neon point-in-time recovery.

### `security.yml` — Security Scanning

Triggered weekly (Monday 08:00 UTC) + on push to `main`.

| Job | Tool | What it scans |
|---|---|---|
| `trivy-image` | Trivy | Container image CVEs (CRITICAL + HIGH) |
| `dependency-audit` | pip-audit | Python dependency vulnerabilities |
| `secret-scan` | Gitleaks | Committed secrets in git history |

Results uploaded to GitHub Security tab (SARIF format).

---

## Required GitHub Secrets

Go to **Repository → Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `ORACLE_VM_HOST` | Oracle VM public IP or hostname |
| `ORACLE_VM_USER` | SSH username (e.g. `ubuntu` or `opc`) |
| `ORACLE_VM_SSH_KEY` | Private SSH key (RSA or Ed25519 PEM format) |
| `ORACLE_VM_PORT` | SSH port (optional, defaults to 22) |
| `DEPLOY_DIR` | Deployment directory on VM (e.g. `/opt/newsiq`) |
| `SENTRY_AUTH_TOKEN` | Sentry release tracking (optional) |
| `SENTRY_ORG` | Sentry org slug (optional) |
| `SENTRY_PROJECT` | Sentry project slug (optional) |

> [!IMPORTANT]
> `GITHUB_TOKEN` is automatically provided by GitHub Actions — no manual configuration needed for pushing to GHCR.

---

## Deployment Directory Structure on Oracle VM

```
/opt/newsiq/
  .env.production          ← All production env vars
  docker-compose.yml       ← Pulled from repository
  grafana/
    provisioning/          ← Grafana dashboards and datasources
```

---

## First-Time Setup on Oracle VM

```bash
ssh user@ORACLE_VM_IP

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Create deployment directory
sudo mkdir -p /opt/newsiq
sudo chown $USER:$USER /opt/newsiq
cd /opt/newsiq

# Clone repo (or copy docker-compose.yml)
git clone https://github.com/OWNER/NewsIQ.git .

# Create production env file
cp .env.example .env.production
nano .env.production  # Fill in Neon + Upstash + R2 credentials

# Pull and start
docker compose --env-file .env.production --profile prod --profile monitor up -d
```

---

## Monitoring Deployments

```bash
# Tail deployment logs
docker compose --profile prod logs -f user-api

# Check health
curl http://localhost:8000/ready | python3 -m json.tool

# View Celery task queue
curl http://localhost:5555  # Flower (if --profile tools)
```

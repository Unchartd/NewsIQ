# Deploying NewsIQ: web on Vercel, API on Render

**Goal:** a live, public NewsIQ that a reviewer can open — no ingestion
pipeline, no admin dashboard.

Everything below was verified against this repo, not assumed. Where something
will bite you, it says so.

---

## What gets deployed, and what does not

| Component | Where | Why |
|---|---|---|
| `apps/web` (Next.js) | Vercel | Public site |
| `apps/api` (FastAPI, read-only) | Render | Serves stories to the site |
| Postgres | Render | Required |
| Redis | Render | Required — `/ready` fails without it |
| Celery worker + beat | **not deployed** | The pipeline. Needs 1.5 GB of ML deps, Qdrant, and spends crawl credits |
| `apps/admin` | **not deployed** | Internal tool |
| Qdrant | **not deployed** | Pipeline only |
| Meilisearch | **not deployed** | Search falls back to a Postgres `ILIKE` query |

---

## The one thing that makes this possible

`apps/api/pyproject.toml` lists `sentence-transformers`, which pulls **torch**.
Installed, the full dependency set is **1.5 GB** — it will not build or run on
a small Render instance.

It is also unnecessary. Every pipeline service imports its ML libraries lazily,
inside function bodies, so importing `app.main` loads **none** of them.
Verified in a clean virtualenv:

```text
app.main imported OK with slim deps
heavy ML modules loaded: NONE
slim venv:  294M
full venv:  1.5G
```

`apps/api/requirements-web.txt` is that slim set. Render uses it instead of
`pyproject.toml`. Keep the two in sync when you add a dependency the API
*serves requests* with.

---

## 1. Backend on Render

The repo now has `render.yaml`, so use a **Blueprint**:

1. Render dashboard → **New** → **Blueprint** → select this repo.
2. It creates `newsiq-db` (Postgres), `newsiq-redis`, and `newsiq-api`.
3. It prompts for `CORS_ORIGINS`. Leave it for now — you don't know the
   Vercel URL yet. Set it in step 3.

Things already handled for you, so don't go hunting for them:

* **`DATABASE_URL` format.** Render issues `postgresql://…?sslmode=require`.
  `app/core/database.py` rewrites it to `postgresql+asyncpg://` and strips the
  query string, which asyncpg rejects.
* **Migrations.** `preDeployCommand: alembic upgrade head`. `alembic/env.py`
  is async-native, so it uses the same URL — no psycopg2 needed.
* **Redis eviction.** Set to `volatile-lru` in the blueprint: only keys with
  a TTL are evictable, and every cache key has one while Celery's queues do
  not. The old self-hosted Redis had no limit and grew to 6.46 GB, which
  helped fill the VM disk and take production down.

---

## 2. Frontend on Vercel

Vercel → **Add New Project** → import the repo, then:

| Setting | Value |
|---|---|
| **Root Directory** | `apps/web` ← the monorepo will not build without this |
| Framework | Next.js (auto-detected) |
| Build command | default (`npm run build`) |

Environment variables:

```
NEXT_PUBLIC_API_URL = https://newsiq-api.onrender.com/api/v1
NEXT_PUBLIC_GA_MEASUREMENT_ID = G-2RJHNS23RH     (optional)
```

**Do not set `INTERNAL_API_URL`.** On the Oracle VM it pointed at a private
Docker hostname. Vercel has no private network to Render, so leave it unset —
`lib/server-api.ts` falls back to `NEXT_PUBLIC_API_URL`, which is correct here.

**`NEXT_PUBLIC_*` are inlined at build time**, not read at runtime. Set them
*before* the first build, and redeploy after changing one. (A stale copy of
these in the old `docker-compose.yml` runtime env is what nearly misled a
previous analytics debug session.)

The build runs a `postbuild` gate that fails if analytics is misconfigured. It
passes cleanly when no GA id is set.

---

## 3. Connect them

Once Vercel gives you a URL, set this on the Render service and redeploy:

```
CORS_ORIGINS = ["https://your-app.vercel.app","https://newsiq.online"]
```

JSON array, not a comma-separated string — the field is `list[str]` and
pydantic-settings parses it as JSON. The default is localhost-only, so until
you do this **every browser request from the deployed site is blocked**.

Verify:

```bash
curl -s https://newsiq-api.onrender.com/health
curl -s https://newsiq-api.onrender.com/ready      # expects {"status":"ready"}
curl -s "https://newsiq-api.onrender.com/api/v1/stories?limit=3"
```

---

## 4. Data: use the existing Neon database

Production data was never on the Oracle VM — `DATABASE_URL` points at **Neon**
(`ap-southeast-1`, Singapore), so it survived the VM going away. A fresh Render
Postgres would be **empty**: the site would deploy, return 200 everywhere, and
show nothing.

So either:

1. **Point the API at Neon directly** (simplest): set `DATABASE_URL` on the
   Render service to the Neon connection string and delete the `newsiq-db`
   block from `render.yaml`. Render's Singapore region keeps it close.
2. **Copy Neon into Render Postgres**, if you want the database on Render:
   ```bash
   pg_dump -Fc "$NEON_URL" > newsiq.dump
   pg_restore -d "$RENDER_DATABASE_URL" --no-owner --no-acl newsiq.dump
   ```

Get the current connection string from the Neon console (Project → Connect).
The copy in the local `.env.prod` has an outdated password.

---

## 5. Free-tier limits worth knowing before a reviewer clicks your link

* **Render free web services sleep after 15 minutes idle.** The next request
  takes roughly 50 seconds to wake. A reviewer opening a cold link sees a
  spinner and may assume it is broken. The **$7/month Starter** plan removes
  this, and it is the single highest-value dollar in this setup.
* **Render free Postgres is deleted after 30 days.** If the application will
  be reviewed later than that, use a paid instance.
* Vercel's Hobby tier is genuinely fine for this, with no sleep.

---

## Cost summary

| | Free | Recommended |
|---|---|---|
| Vercel (web) | $0 | $0 |
| Render API | $0, sleeps | $7/mo |
| Render Postgres | $0, 30-day expiry | ~$6/mo |
| Render Redis | $0 | $0 |
| **Total** | **$0** | **~$13/mo** |

---

## Not deployed, and what that costs you

Without the pipeline the site is a **static archive** of whatever is in the
database — no new stories arrive. Everything else works: story pages, search,
trending, categories, auth.

That is the right trade for a credits application. Turning ingestion back on
means the ML dependency set, a Qdrant instance, and per-crawl provider spend.

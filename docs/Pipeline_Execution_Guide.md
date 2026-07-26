# NewsIQ Pipeline X-Ray — Execution Guide

> **Purpose:** Step-by-step instructions for launching and running the interactive pipeline notebook.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | ≥ 3.12 (matches `apps/api/.venv`) |
| Jupyter | `jupyter lab` ≥ 7 |
| PostgreSQL | Running and seeded with at least one `Source` |
| Redis | Reachable at `REDIS_URL` in `.env` |
| Qdrant | Reachable at `QDRANT_URL` in `.env` |
| `.env` | `apps/api/.env` fully populated |

---

## Step 1 — Register the Jupyter Kernel (one-time)

The notebook must run against `apps/api/.venv`, not system Python.

```powershell
# From repo root
cd apps\api
.venv\Scripts\activate
pip install ipykernel psutil python-dateutil
python -m ipykernel install --user --name=newsiq-api --display-name="NewsIQ API (.venv)"
```

Verify:
```powershell
jupyter kernelspec list
# newsiq-api  C:\Users\<user>\AppData\Roaming\jupyter\kernels\newsiq-api
```

---

## Step 2 — Launch Jupyter from `notebooks/`

```powershell
cd NewsIQ\notebooks
jupyter lab
```

> **Always launch from `NewsIQ/notebooks/`.** SETUP cell 1 computes paths relative to `os.getcwd()`.

---

## Step 3 — Select Kernel

1. Open `Pipeline_XRay.ipynb`
2. **Kernel → Change Kernel…** → `NewsIQ API (.venv)`

---

## Step 4 — Run SETUP (4 cells)

| Cell | Validates |
|------|-----------|
| SETUP 1/4 | `sys.path`, CWD, `.env` |
| SETUP 2/4 | imports, logging |
| SETUP 3/4 | display helpers |
| SETUP 4/4 | `app.core.config.settings` |

---

## Step 5 — Run Section 0 (Infra Health)

Checks PostgreSQL, Redis, Qdrant, Meilisearch, and loads the Prompt Repository.  
Failed services are flagged; downstream cells skip them gracefully.

---

## Step 6 — Execute Sections 1–23 in Order

Each section = one pipeline stage. All variables persist in notebook memory.  
Re-run any individual cell independently without restarting the kernel.

---

## Changing the Input Article

```python
SELECTED_SOURCE_INDEX = 2   # Section 2 — pick a different source
SELECTED_ENTRY_INDEX  = 5   # Section 3 — pick a different article
```

Re-run from Section 2 onward.

---

## Cost Control

| Stage | Model | Est. Cost |
|-------|-------|-----------|
| Section 10 NER | gemini-flash | < $0.001 |
| Section 11 Events | gemini-flash | < $0.001 |
| Section 14 Reflection | gemini-flash | < $0.001 |
| Section 15 Judge | gemini-pro | ~$0.005 |
| **Section 18 Synthesis** | **gemini-2.5-pro** | **~$0.01–$0.05** |

> Cell `[18.5]` shows the cost estimate before you run the actual LLM call.  
> To skip, set `story_summary = None` and jump to Section 19.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: app` | Wrong kernel — switch to `NewsIQ API (.venv)` |
| `FileNotFoundError: .env` | Launched Jupyter from wrong directory |
| `asyncio` errors in VS Code | Add `import nest_asyncio; nest_asyncio.apply()` to SETUP 1 |
| `IntegrityError` on Article INSERT | Duplicate — cell auto-loads existing record |
| `Qdrant Connection refused` | Run `docker start newsiq-qdrant` |

---

## Preserve State Across Sessions

```python
import pickle, json

# Save embedding
with open("debug_embedding.pkl", "wb") as f:
    pickle.dump(embedding_vector, f)

# Save API response
with open("debug_api_response.json", "w") as f:
    json.dump(api_response_json, f, indent=2, default=str)
```

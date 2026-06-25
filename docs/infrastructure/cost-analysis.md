# Cost Analysis — NewsIQ Cloud-Native MVP

## Infrastructure Cost Model

| Service | Provider | Free Tier | Paid | Notes |
|---|---|---|---|---|
| PostgreSQL | Neon | 0.5 GB storage, 5 compute-hrs/day | From $19/mo | Autosuspend saves cost |
| Redis (cache) | Upstash | 10k commands/day | ~$0.2/100k commands | |
| Redis (broker) | Upstash | 10k commands/day | ~$0.2/100k commands | |
| Redis (backend) | Upstash | 10k commands/day | ~$0.2/100k commands | |
| Object Storage | Cloudflare R2 | 10 GB, 1M ops | $0.015/GB, $4.50/M ops | Zero egress fees |
| Compute (VM) | Oracle Cloud | Always free (4 OCPU, 24 GB) | $0 forever | ARM instance |
| Langfuse | Langfuse Cloud | 50k observations/mo | From $59/mo | LLM tracing |
| LLM (Gemini) | Google AI | Rate limits | ~$0.35/1M tokens | Flash 2.5 |

---

## Estimated Monthly Cost by User Scale

### 100 Users (MVP)

| Item | Provider | Cost |
|---|---|---|
| PostgreSQL | Neon free tier | $0 |
| Redis × 3 | Upstash free tier | $0 |
| Object storage | Cloudflare R2 free tier | $0 |
| Compute | Oracle Cloud free tier | $0 |
| LLM calls | Gemini Flash (light usage) | ~$2 |
| Langfuse | Cloud free tier | $0 |
| **Total** | | **~$2/month** |

### 1,000 Users (Early Growth)

| Item | Provider | Cost |
|---|---|---|
| PostgreSQL | Neon Launch ($19/mo) | $19 |
| Redis × 3 | Upstash pay-as-you-go | ~$10 |
| Object storage | R2 (~2 GB) | $1 |
| Compute | Oracle Cloud free tier | $0 |
| LLM calls | Gemini Flash (moderate) | ~$25 |
| Langfuse | Cloud free tier | $0 |
| **Total** | | **~$55/month** |

### 10,000 Users (Growth)

| Item | Provider | Cost |
|---|---|---|
| PostgreSQL | Neon Scale ($69/mo) | $69 |
| Redis × 3 | Upstash Pro ($30 each) | $90 |
| Object storage | R2 (~20 GB) | $10 |
| Compute | 2× Oracle ARM VMs | $0 |
| LLM calls | Gemini Flash (heavy) | ~$150 |
| Langfuse | Cloud Pro ($59/mo) | $59 |
| **Total** | | **~$378/month** |

### 100,000 Users (Scale)

| Item | Provider | Cost |
|---|---|---|
| PostgreSQL | Neon Business ($299/mo) | $299 |
| Redis × 3 | Upstash Pro ($100+ each) | $300 |
| Object storage | R2 (~200 GB) | $30 |
| Compute | 4× VMs (or Hetzner) | ~$100 |
| LLM calls | Gemini + OpenAI mix | ~$1,000 |
| Langfuse | Self-hosted | $0 |
| **Total** | | **~$1,729/month** |

---

## Cost Optimization Levers

1. **Neon autosuspend** — Development DB suspends after 5 min idle. Free tier provides 5 compute-hours/day.
2. **Upstash per-request pricing** — You pay only for commands executed. Idle periods cost nothing.
3. **R2 zero egress** — No charges for bandwidth serving assets to users (unlike AWS S3).
4. **Celery rate limiting** — `--concurrency=2` limits parallel LLM API calls. Use Gemini Flash instead of Pro where possible.
5. **Oracle Cloud Always Free** — 4 OCPU, 24 GB RAM ARM instance — zero cost indefinitely for MVP compute.
6. **Langfuse sampling** — At 10k+ users, set `LANGFUSE_SAMPLE_RATE=0.1` to reduce observation count.

---

## Migration Cost to Self-Hosted

If managed services become too expensive at scale, migration to self-hosted requires only env var changes:

| Service | Self-hosted alternative | Estimated cost |
|---|---|---|
| Neon PostgreSQL | PostgreSQL on Hetzner VPS | ~$5–10/mo |
| Upstash Redis | Redis on Hetzner VPS | ~$3–5/mo |
| Langfuse Cloud | Langfuse self-hosted | ~$5–10/mo (extra VPS) |
| **Total self-hosted** | | **~$13–25/mo at scale** |

No code changes required for this migration.

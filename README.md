# 🎬 clip-it-up (Phase 0 Foundation)

> High-performance SaaS pipeline that turns long-form videos into short vertical clips. Phase 0 provides the foundation: direct S3 uploads via presigned URLs, asynchronous Celery task pipelines, realtime SSE streaming, per-stage ₹ INR cost accounting, and Next.js UI.

---

## 📚 Documentation & Onboarding

> **Start here**: [CONTRIBUTING.md](CONTRIBUTING.md) $\rightarrow$ [IMPLEMENTATION.md](IMPLEMENTATION.md) $\rightarrow$ [ARCHITECTURE.md](ARCHITECTURE.md)

- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Developer setup in under 10 commands, PR workflow, code standards, conflict avoidance, and Definition of Done.
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)**: Goals, v1 scope, 8-phase delivery roadmap, task checklists tagged by subsystem, and developer ownership split.
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: System topology diagram, pipeline execution & idempotency rules, data flows, and key architectural decisions.
- **[docs/cost-sheet.md](docs/cost-sheet.md)**: Per-stage ₹ INR rate card and measurement methodology.

---

## 🏛 Architecture Diagram

```text
               +-------------------------------------------------------------+
               |                       Next.js (Web UI)                      |
               |       - Direct S3/MinIO upload with part progress & retry   |
               |       - Realtime SSE stream with Last-Event-ID reconnect    |
               +-------------+-------------------------------+---------------+
                             |                               |
                   Presigned | PUT                 SSE Stream| & API Calls
                             v                               v
               +-------------+-------------+   +-------------+---------------+
               |       MinIO / S3 / R2     |   |         FastAPI (API)       |
               |   - Presigned single PUT  |   |  - Clerk JWKS / Dev Bypass  |
               |   - Multipart (parts/comp)|   |  - Presigned URL generation |
               |   - Storage key isolation |   |  - Ownership isolation      |
               +-------------+-------------+   +------+--------------+-------+
                             ^                        |              |
                    HEAD /   | Read Video             | Enqueue      | Job State
                    Download |                        v              v
               +-------------+-------------+   +------+-------+ +----+-------+
               |       Celery Worker       |<--| Redis Queue  | | PostgreSQL |
               |  - 6 Idempotent stages    |   |  & Pub/Sub   | | - Users    |
               |  - Simulation & progress  |   +------+-------+ | - Videos   |
               |  - ₹ INR cost recording   |          ^         | - Jobs     |
               |  - Upserted usage rows    |----------+         | - Stages   |
               +---------------------------+  Publish Events    | - Usage    |
                                                                +------------+
```

---

## 🚀 Quickstart (Under 10 Commands)

```bash
# 1. Clone & copy environment variables
cp .env.example .env

# 2. Start all services via Docker Compose
docker compose up -d --build

# 3. Run database migrations
docker compose exec api alembic upgrade head

# 4. (Optional) Seed development database
docker compose exec api python -m clip_shared.db.seed

# 5. Open Web UI in browser
# Visit: http://localhost:3000
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Runtime environment (`development`, `staging`, `production`) |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/clip_it_up` | Async SQLAlchemy DB URI |
| `DATABASE_SYNC_URL`| `postgresql://postgres:postgres@localhost:5432/clip_it_up` | Sync SQLAlchemy DB URI (Celery & Alembic) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker and Pub/Sub connection URL |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | S3 / MinIO internal API endpoint |
| `S3_PUBLIC_ENDPOINT_URL` | `http://localhost:9000` | S3 endpoint accessible by the browser for presigned URLs |
| `S3_BUCKET_NAME` | `clip-it-up-videos` | S3 bucket for storing uploaded videos |
| `DEV_AUTH_BYPASS` | `true` | Allows local development without Clerk API keys (dev mode only) |
| `MAX_UPLOAD_SIZE_BYTES` | `5368709120` (5 GB) | Maximum allowed file upload size |
| `MULTIPART_THRESHOLD_BYTES` | `104857600` (100 MB) | File size threshold to trigger multipart chunked upload |
| `PIPELINE_STAGE_DURATION_SECONDS` | `2` | Duration simulated for each pipeline stage |
| `INJECT_RANDOM_FAILURE` | `false` | Injects random stage failures to test retry / failure handling |

---

## 🧪 Running Tests & Quality Checks

### 1. API & Worker Tests
```bash
# Via Makefile
make test

# Or directly in container
docker compose exec api pytest -v
docker compose exec worker pytest -v
```

### 2. Linting & Formatting
```bash
# Lint Python (ruff & mypy) and TypeScript (eslint & tsc)
make lint

# Autoformat code
make fmt
```

### 3. Playwright Smoke Test
```bash
cd apps/web
pnpm test:smoke
```

---

## 🛠 How to Add a New Pipeline Stage

1. **Register the Stage Name**:
   - Update `packages/shared/src/types.ts`: add your stage to `PipelineStageName` and `PIPELINE_STAGES`.
   - Update `apps/worker/src/worker/tasks/pipeline.py`: add your stage name to `PIPELINE_STAGES` in the desired execution order.

2. **Configure Pricing & Metrics**:
   - In `packages/shared-py/src/clip_shared/rates.py`:
     ```python
     RATES_PER_SOURCE_HOUR["my_new_stage"] = Decimal("5.00") # ₹5.00 / hr
     STAGE_METRICS["my_new_stage"] = "gpu_seconds"
     ```

3. **Add UI Metadata**:
   - In `apps/web/src/components/StageStepper.tsx`: add the stage metadata, icon, and description in `STAGES_METADATA`.

4. **Deploy Migrations / Restart**:
   - Re-run `make up` to rebuild and run the pipeline with your newly registered stage.

---

## 📁 Repository Layout

```text
clip-it-up/
  ├── apps/
  │   ├── api/            # FastAPI backend (auth, SSE, S3 presigned URLs, jobs)
  │   ├── worker/         # Celery task worker (6-stage pipeline, simulation, costs)
  │   └── web/            # Next.js 14 App Router, Tailwind, Zustand, SSE client
  ├── packages/
  │   ├── shared/         # Shared TypeScript contracts, models & API client
  │   └── shared-py/      # Shared Python models, Alembic migrations, rates, S3 & Redis
  ├── infra/              # docker-compose.yml, MinIO bucket initialization, env templates
  ├── docs/               # cost-sheet.md (₹ per source-hour rates & methodology)
  ├── eval/               # Evaluation benchmark placeholder (Phase 2)
  ├── Makefile            # Convenience CLI targets (up, down, migrate, test, lint)
  ├── CONTRIBUTING.md     # Developer guide, git workflow, and definition of done
  ├── IMPLEMENTATION.md   # Goals, phase table, task checklist, and team split
  ├── ARCHITECTURE.md     # Topology diagram, idempotency rules, and ADR decisions
  └── README.md
```

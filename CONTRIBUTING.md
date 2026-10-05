# Contributing Guidelines

> Developer setup, branching strategy, coding standards, and definition of done for clip-it-up.

## 1. Quickstart Setup (Under 10 Commands)

```bash
# 1. Copy local environment variables
cp .env.example .env

# 2. Start all Docker Compose services (Postgres, Redis, MinIO, API, Worker, Web)
make up

# 3. Apply database migrations
make migrate

# 4. Seed development user & project
make seed

# 5. Run test suite to verify installation
make test

# 6. Open frontend in browser: http://localhost:3000
```

---

## 2. Git & PR Workflow

- **Branch Naming**: Short-lived branches created from `main`:
  - `feat/transcribe-whisper`
  - `fix/sse-reconnect`
  - `chore/docker-uv-upgrade`
- **Commit Messages**: Follow [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat(worker): add audio extraction task`
  - `fix(web): prevent duplicate part uploads in multipart`
- **PR Rules**:
  - Keep PRs small (<400 lines changed).
  - Require **1 approval** from the other developer (`<DEV_A>` or `<DEV_B>`).
  - Merge strategy: **Squash and merge**.

---

## 3. Engineering Standards & Rules

1. **Shared Contracts First**: Any API endpoint or schema change must update TypeScript types in [`packages/shared/`](packages/shared) and Pydantic schemas in [`packages/shared-py/`](packages/shared-py) in the **same PR**.
2. **Database Migrations**:
   - Exactly one Alembic migration per PR in [`packages/shared-py/alembic/versions/`](packages/shared-py/alembic/versions).
   - **Never** modify or edit an already-merged migration file.
3. **No Hardcoded Secrets**: Secrets belong in `.env`. Never commit API keys or credentials.
4. **Code Quality & Linters**:
   - Python: `uv run ruff check` and `uv run mypy` (enforced in CI).
   - TypeScript: `pnpm lint` and `tsc --noEmit` (strict mode enabled).
5. **Testing**: Unit tests are required for new API endpoints and worker pipeline tasks.

---

## 4. Conflict Avoidance Protocol

- **Area Ownership**:
  - `<DEV_A>` owns `apps/api`, `apps/worker`, and `packages/shared-py`.
  - `<DEV_B>` owns `apps/web` and frontend components.
- **Cross-Cutting Notification**: Notify your pair before modifying:
  1. [`infra/docker-compose.yml`](infra/docker-compose.yml) or base images.
  2. Database models in [`packages/shared-py/src/clip_shared/db/models.py`](packages/shared-py/src/clip_shared/db/models.py).
  3. Shared contracts in [`packages/shared/src/types.ts`](packages/shared/src/types.ts).

---

## 5. Definition of Done (DoD) Checklist

Before requesting review, ensure your branch satisfies:
- [ ] Code passes formatting and lint checks (`make lint` and `make fmt`).
- [ ] Unit/integration tests pass locally (`make test`).
- [ ] New/modified API endpoints are reflected in [`packages/shared/src/types.ts`](packages/shared/src/types.ts).
- [ ] DB migrations run cleanly (`make migrate`) and downgrade cleanly.
- [ ] No regressions introduced in Docker Compose startup (`make up`).
- [ ] PR description clearly explains the changes and test evidence.

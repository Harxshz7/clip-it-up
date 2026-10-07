.PHONY: up down logs migrate test lint fmt seed clean ps

# Infra & Services
up:
	docker compose -f infra/docker-compose.yml up -d --build

down:
	docker compose -f infra/docker-compose.yml down -v

logs:
	docker compose -f infra/docker-compose.yml logs -f

ps:
	docker compose -f infra/docker-compose.yml ps

# Database migrations
migrate:
	docker compose -f infra/docker-compose.yml exec api alembic upgrade head

# Seed test data
seed:
	docker compose -f infra/docker-compose.yml exec api python -m clip_shared.db.seed

# Tests
test: test-api test-worker

test-api:
	docker compose -f infra/docker-compose.yml exec api pytest -v

test-worker:
	docker compose -f infra/docker-compose.yml exec worker pytest -v

# Benchmark & Evaluation
bench:
	python scripts/bench_transcribe.py

eval:
	python -m eval.run

tune:
	python -m eval.tune



# Linting & Formatting
lint:
	@echo "Linting Python with ruff & mypy..."
	uv run ruff check apps/api apps/worker packages/shared-py
	uv run mypy apps/api apps/worker packages/shared-py
	@echo "Linting Web with eslint & tsc..."
	cd apps/web && pnpm lint && pnpm typecheck

fmt:
	uv run ruff format apps/api apps/worker packages/shared-py
	cd apps/web && pnpm format

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

# Stage 1: Base builder with uv
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy shared package and API package
COPY packages/shared-py /app/packages/shared-py
COPY apps/api /app/apps/api

# Install dependencies into virtualenv
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN uv pip install -e /app/packages/shared-py
RUN uv pip install -e /app/apps/api

# Stage 2: Runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies (libpq for Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r clipapp && useradd -r -g clipapp -d /app clipapp

COPY --from=builder /opt/venv /opt/venv
COPY packages/shared-py /app/packages/shared-py
COPY apps/api /app/apps/api
COPY alembic.ini /app/alembic.ini

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/packages/shared-py/src:/app/apps/api/src:/app"

RUN chown -R clipapp:clipapp /app
USER clipapp

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

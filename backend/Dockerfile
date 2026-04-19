# syntax=docker/dockerfile:1.6

# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /build

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 smartspend \
    && useradd --system --uid 1001 --gid smartspend --create-home smartspend

WORKDIR /app

COPY --from=builder --chown=smartspend:smartspend /build/.venv /app/.venv
COPY --from=builder --chown=smartspend:smartspend /build/app /app/app
COPY --from=builder --chown=smartspend:smartspend /build/alembic /app/alembic
COPY --from=builder --chown=smartspend:smartspend /build/alembic.ini /app/alembic.ini

USER smartspend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

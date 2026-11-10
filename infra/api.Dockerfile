# Production API image (Render). Build context: repo root.
#   docker build -f infra/api.Dockerfile -t bachatcheck-api .
# Unlike backend/Dockerfile (local dev), this bakes in the read-only data files the API needs:
# demo funds and tax rules. MUFAP exports are never copied (see .dockerignore).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    LOG_JSON=true
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/bachatcheck/__init__.py bachatcheck/__init__.py
RUN pip install --no-cache-dir .

COPY backend/ ./
COPY data/demo data/demo
COPY data/tax_rules.yaml data/tax_rules.yaml
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home app
USER app

EXPOSE 8000
# Migrations run on every start; they're idempotent. One worker fits the free tier's 512 MB.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn bachatcheck.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

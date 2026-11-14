# Self-contained API image for any Docker host (Render, Fly, a VPS...). Build context: repo root.
#   docker build -f infra/api.Dockerfile -t bachatcheck-api .
# The default deployment is Vercel (see DEPLOY.md); this image is the alternative.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_JSON=true
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/bachatcheck/__init__.py bachatcheck/__init__.py
RUN pip install --no-cache-dir .

COPY backend/ ./
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home app
USER app

EXPOSE 8000
# Migrations run on every start; they're idempotent.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn bachatcheck.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

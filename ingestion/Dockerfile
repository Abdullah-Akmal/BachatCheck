# Build context is the repo root (see docker-compose.yml): ingestion needs backend/ and data/.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /repo

COPY backend/pyproject.toml backend/
COPY backend/bachatcheck/__init__.py backend/bachatcheck/__init__.py
COPY ingestion/pyproject.toml ingestion/
COPY ingestion/ingestion/__init__.py ingestion/ingestion/__init__.py
RUN pip install --no-cache-dir -e backend -e "ingestion[dev]"

COPY backend backend
COPY ingestion ingestion
COPY data data

RUN useradd --create-home app && chown -R app /repo
USER app
WORKDIR /repo/ingestion
ENTRYPOINT ["python", "-m", "ingestion"]
CMD ["list"]

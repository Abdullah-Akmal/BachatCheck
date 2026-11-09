FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY bachatcheck/__init__.py bachatcheck/__init__.py
RUN pip install --no-cache-dir -e .

COPY . .

RUN useradd --create-home app
USER app

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn bachatcheck.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

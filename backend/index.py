"""Vercel entrypoint. Vercel's FastAPI support looks for an `app` object in index.py.

Locally and in Docker the app runs with `uvicorn bachatcheck.main:app` instead.
"""

from bachatcheck.main import app

__all__ = ["app"]

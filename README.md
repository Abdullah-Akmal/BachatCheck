# BachatCheck — "Where should my savings go?"

A web app for Pakistani savers: enter an amount and a time horizon, then see how that money would
have grown in bank savings, mutual funds, T-bills, the KSE-100, USD and gold. It also shows the
**real return after inflation and tax**.

> For education only. Not investment advice. Data may be delayed or inaccurate.

## Repo layout

| Path | What |
|---|---|
| `backend/` | FastAPI API (`/api/v1`), SQLAlchemy 2 models, Alembic migrations, returns engine |
| `ingestion/` | Daily data jobs: `python -m ingestion run <source>` |
| `frontend/` | Next.js (App Router) + TypeScript + Tailwind |
| `data/` | Versioned config: tax rules, manual gold CSV, demo seed data |
| `infra/` | Deployment config |
| `docker-compose.yml` | Local Postgres + API + web |

## Run locally

With Docker:

```bash
cp .env.example .env
docker compose up
```

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

Without Docker (Python 3.11+, Node 20+):

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e "backend[dev]" -e "ingestion[dev]"
cd backend && uvicorn bachatcheck.main:app --reload
```

```bash
cd frontend && npm install && npm run dev
```

## Data sources and licensing notes

- **MUFAP** (mutual fund NAVs): MUFAP's Terms of Use allow personal, non-commercial use only.
  BachatCheck therefore ingests a **manually downloaded** "Performance Summary" Excel export, and
  MUFAP data is **not shown on the public deployment** unless MUFAP gives written permission.
- Other sources (SBP EasyData, Frankfurter, PSX via `psxdata`) are documented on the methodology
  page as they're added.

_Status: Milestone 1 (skeleton)._

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
| `data/` | Versioned inputs: tax rules, manual gold CSV, MUFAP inbox (git-ignored) — see `data/README.md` |
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

Without Docker (Python 3.11+, Node 20+, macOS/Linux/WSL):

> **Windows note:** Windows 11 *Smart App Control* blocks the unsigned compiled extensions that
> SQLAlchemy, psycopg and pydantic ship in their wheels, so the Python side won't import natively.
> Run it in Docker or WSL instead. The frontend works natively.


```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -e "backend[dev]" -e "ingestion[dev]"
cd backend && uvicorn bachatcheck.main:app --reload
```

```bash
cd frontend && npm install && npm run dev
```

## Ingestion

Every source sits behind a `Provider` (`fetch() -> raw payloads`, `parse() -> records`). The
runner saves each raw payload to `raw_snapshots` **before** parsing, validates every record
(bad rows are logged and skipped), upserts idempotently on `(source, identifier, date)`, and
writes a `job_runs` row. If a source fails, existing data is untouched.

```bash
docker compose run --rm ingestion list
docker compose run --rm ingestion run sbp            # also: frankfurter, psx, mufap, gold, tax_rules
docker compose run --rm ingestion backfill sbp --from 2016-07-01
docker compose run --rm ingestion run sbp --series CPI_YOY,TBILL_3M
docker compose run --rm ingestion run psx --symbols KSE100,OGDC
```

Exit codes: `0` success, `1` failed, `2` usage error, `3` partial.

## Data sources and licensing notes

| Data | Source | Notes |
|---|---|---|
| CPI, policy rate, T-bill yields, KIBOR, deposit rates | [SBP EasyData API](https://easydata.sbp.org.pk/) | Needs a free API key (`SBP_EASYDATA_API_KEY`) that **expires every 90 days**. Limits: 2,000 requests/day, 250/hour. National CPI starts Jul 2016 (2015-16 base). |
| USD/PKR | [Frankfurter v2](https://api.frankfurter.dev/v2/providers), SBP provider | Free, no key. SBP rates are published monthly, so they lag by up to a few weeks. |
| KSE-100, PSX stocks | [`psxdata`](https://github.com/mtauha/psxdata) (MIT) | ⚠️ See below. |
| Mutual funds (NAV + trailing returns) | MUFAP "Performance Summary" Excel export | Manual download; local only. See below. |
| Gold (PKR per tola, 24k) | `data/gold/gold_pkr_per_tola_24k.csv` | No free reliable source found, so it's maintained by hand and labelled "manually updated". |
| Tax rates | `data/tax_rules.yaml` | **Placeholders** until verified against current FBR rules. |

**MUFAP:** MUFAP's Terms of Use allow personal, non-commercial use only, and the site blocks
automated requests. BachatCheck ingests a **manually downloaded** export (kept out of git), and
the public deployment shows **demo fund data** (`FUNDS_DATA_MODE=demo`) unless MUFAP gives
written permission.

**PSX:** PSX's [Terms of Use](https://psx.com.pk/psx/terms-of-use) prohibit automated retrieval
("systematic retrieval to create collections, compilations, databases") and public display
without PSX's prior written permission. `psxdata` scrapes the PSX website. The project owner has
chosen to use it anyway for this portfolio project; usage is kept polite (one run per day after
market close, a short watchlist), and `STOCKS_DATA_MODE=demo` switches stock data to demo
values. Licensing contact: marketdatarequest@psx.com.pk.

**Deposit rates:** SBP's weighted-average deposit rates include zero-profit current accounts,
so they understate what a savings account pays. The bank-savings benchmark is configurable.

_Status: Milestone 2 (data model + ingestion)._

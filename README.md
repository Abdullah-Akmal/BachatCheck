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

## API

Versioned under `/api/v1`, with OpenAPI docs at `/docs`. Heavy GETs are cached in-process for
`CACHE_TTL_SECONDS` (default 300, `X-Cache: HIT|MISS`), and every client IP gets
`RATE_LIMIT_PER_MINUTE` requests (default 60; `/health` is exempt). CORS allows only
`CORS_ORIGINS`. Decimals are returned as **strings**: money rounded to 2 dp, returns as
fractions rounded to 6 dp (`"0.126825"` = 12.68%).

| Endpoint | What |
|---|---|
| `GET /compare?amount=&years=&shariah=&filer_status=&savings_rate=` | Nominal, real and post-tax growth per asset class, plus a CPI line |
| `GET /funds`, `/funds/categories`, `/funds/{symbol}` | Funds explorer (sort/filter), NAV history |
| `GET /stocks/search?q=`, `/stocks/{symbol}?period=` | Price history and return vs KSE-100 |
| `GET /macro`, `/macro/{code}` | CPI, policy rate, T-bills, KIBOR, deposit rates |
| `GET /freshness` | Last successful run per source and latest data date per dataset |
| `GET /tax-rules`, `/config` | Tax assumptions and data modes (for the methodology page) |

## How returns are calculated

All math lives in `backend/bachatcheck/returns/` and uses `Decimal` (34 significant digits).

- **Absolute return** `end / start − 1`. **CAGR** `(1 + total)^(365 / days) − 1`.
- **Real return** (exact Fisher): `(1 + nominal) / (1 + inflation) − 1`.
- **Inflation** comes from a price index chained from SBP's month-on-month national CPI. It runs
  from the CPI month at/before the start date to the one at/before the end date.
- **Bank savings:** profit credited monthly at the rate in force (SBP's average deposit rate,
  or the user's own rate), then reinvested.
- **T-bills (3/6/12 months):** bought at the latest auction cut-off yield, rolled over at each
  maturity, actual/365. The last partial period accrues pro rata.
- **KSE-100 / KMI-30, USD, gold:** buy at the start price or rate, value at the end. Index
  levels don't include dividends.
- **Mutual funds:** the category median of MUFAP's trailing 1/2/3-year return, so horizons are
  1–3 years only. Annualized categories compound `(1 + r)^years`; absolute ones are used as is.
  The chart line in between is illustrative.
- **Tax:** applied only when `tax_rules` holds a **verified** rate. Accrual assets withhold tax
  on each profit credit; price assets pay tax on the gain at the end, and losses aren't
  refunded. Otherwise the API returns `tax.status = "unverified"` and no post-tax figures.
- **Shariah-compliant mode** excludes interest-bearing savings and T-bills, swaps the KSE-100
  for the KMI-30, and uses Shariah-compliant fund categories.

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

_Status: Milestone 3 (returns engine + API)._

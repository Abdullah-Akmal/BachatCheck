# AGENTS.md: working on BachatCheck

Onboarding for AI coding agents (and humans) who will change this codebase. Read this before
editing. The end-user overview is in [README.md](README.md), hosting is in [DEPLOY.md](DEPLOY.md),
and the long-form explanation is in [docs/BachatCheck-Project-Dossier.pdf](docs/BachatCheck-Project-Dossier.pdf).

**What it is:** a web app that shows Pakistani savers how an amount would have grown in bank savings,
T-bills, mutual funds, the KSE-100, USD and gold, and the **real return after inflation (and tax)**.
Educational only: never present output as investment advice.

- Live site: https://bachatcheck-akteam321.vercel.app
- Live API: https://bachatcheck-api-akteam321.vercel.app (`/docs`, `/api/v1/health`, `/api/v1/freshness`)
- Repo: https://github.com/Abdullah-Akmal/BachatCheck (`main` auto-deploys)

---

## 1. Non-negotiable rules

Breaking any of these is a bug, even if tests pass.

1. **Money is never a float.** Python uses `Decimal`; Postgres uses `NUMERIC`; the API sends decimals as
   **strings**. Convert third-party floats with `to_decimal()` (it goes through `repr()`). The frontend
   converts strings to numbers **only for display** (`frontend/src/lib/format.ts`).
2. **Never fake or fill data.** If data is missing, return `available: false` with a human-readable
   `reason`, or a `partial` flag. Never interpolate, extrapolate or invent values. The only exceptions are
   the explicitly labelled demo/synthetic datasets (rule 5).
3. **Tax rates are data, never code, and never guessed.** They live in `data/tax_rules.yaml`. After-tax
   figures appear only for rules with `verified: true` and a `rate`. Don't add rates from memory: leave
   `rate: null` and a TODO for the owner to verify against FBR.
4. **Respect data-source terms.** MUFAP allows personal use only and blocks bots: never scrape it, and
   only parse the manually downloaded Excel export. PSX restricts automated retrieval; the owner accepted
   that risk for `psxdata`, so keep usage polite (one daily run, short watchlist). **Never write code that
   evades bot protection or rate limits.**
5. **Demo and synthetic data must always be labelled.** `FUNDS_DATA_MODE=demo` serves
   `backend/bachatcheck/demo_data/funds.json` with a "Demo data" badge. `ingestion seed` writes
   `source="demo_seed"` rows and the UI shows a site-wide banner. Never mix synthetic and real rows (the
   seed command refuses by default).
6. **Secrets never enter git, logs, URLs we store, or chat.** `.env` is git-ignored. Production
   secrets live in Vercel env vars and the GitHub environment `BachatCheck`. Don't paste
   connection strings or API keys into dashboards or tools on the owner's behalf: tell the owner where to
   put them. The SBP key goes only in the `api_key` query param at request time; `runner.redact()` scrubs it.
7. **Return math lives in one place:** `backend/bachatcheck/returns/`. Pure functions, unit-tested
   against hand-worked values (show the arithmetic in a test comment). Don't compute returns in the
   API layer or the frontend.
8. **Ingestion stays idempotent.** Every data table has a unique key on (source, identifier, date), and writes
   use `INSERT … ON CONFLICT DO UPDATE` via `ingestion/ingestion/writers.py`. Re-running a job must not add rows.

---

## 2. Repository map

```
backend/                      FastAPI app + shared DB layer (package: bachatcheck)
  bachatcheck/config.py       Settings (pydantic-settings). Every env var is defined here.
  bachatcheck/db.py           Engine/session, Base with naming convention, optional_session (health)
  bachatcheck/models/         SQLAlchemy 2 models: instruments, macro, ops (job_runs, raw_snapshots), tax
  bachatcheck/returns/        core.py (formulas) · series.py (CPI index, accrual, price paths) · compare.py (engine)
  bachatcheck/repo.py         Read queries used by the API (returns dataclasses, not ORM objects)
  bachatcheck/api/v1/         compare, funds, stocks, meta (macro/freshness/tax-rules/config), health, schemas
  bachatcheck/api/middleware.py   ASGI TTL cache + per-IP rate limit
  bachatcheck/demo_data/funds.json  Synthetic demo funds (package data; served when FUNDS_DATA_MODE=demo)
  alembic/                    Migrations (0001 baseline, 0002 core schema)
  index.py                    Vercel entrypoint (`from bachatcheck.main import app`)
  vercel.json, .python-version, .vercelignore   Vercel config (Python 3.12, region sin1)
  tests/                      pytest; conftest seeds a rolled-back Postgres transaction
ingestion/                    Data jobs (package: ingestion), depends on backend's models
  ingestion/providers/        base.py (Provider, RawPayload, FetchContext) + one module per source:
                              sbp, frankfurter, psx, mufap, gold, tax_rules, demo_seed
  ingestion/records.py        Typed records + validate(); to_decimal(); today_pkt()
  ingestion/runner.py         raw-first → parse → validate → upsert → job_runs; redaction; abandoned-run cleanup
  ingestion/writers.py        Idempotent chunked upserts
  ingestion/cli.py            `python -m ingestion list|run|backfill|seed`
  tests/fixtures/             Trimmed REAL payloads (SBP, Frankfurter, PSX). MUFAP is synthetic (licensing).
frontend/                     Next.js 15 App Router + TS + Tailwind 4 + Recharts
  src/app/                    / (compare), /funds, /funds/[symbol], /stocks, /stocks/[symbol], /methodology
  src/components/             compare/* (form, headline, chart, asset list), price-chart, ui, nav, synthetic-banner
  src/lib/                    api.ts (typed client + error handling), format.ts, params.ts, series.ts (chart colours)
data/                         tax_rules.yaml · gold/gold_pkr_per_tola_24k.csv · mufap_inbox/ (git-ignored)
infra/api.Dockerfile          Self-contained API image (alternative to Vercel)
.github/workflows/            ci.yml (every push/PR) · ingest.yml (scheduled ingestion, uses env "BachatCheck")
docs/                         Dossier (HTML source + PDF) and README screenshots
```

---

## 3. Running and checking things

**Use Docker for Python.** On the owner's Windows machine, *Smart App Control* blocks the compiled wheels
(SQLAlchemy, psycopg, pydantic-core) natively. Run all Python through the `ingestion` compose service, which has
backend + ingestion + dev tools installed and the source mounted. The frontend runs natively (`npm`).

```bash
cp .env.example .env                       # first time; fresh clones default to demo fund data
docker compose up -d                       # Postgres :5432, API :8000 (/docs), web :3000
docker compose run --rm ingestion seed     # synthetic data, no keys needed (banner shows)
```

Checks: run these before every commit. They are exactly what CI runs.

```bash
# Python (backend + ingestion), inside Docker:
docker compose run --rm --entrypoint sh ingestion -c "cd /repo/backend && ruff check . && ruff format --check . && mypy bachatcheck tests index.py && python -m pytest -q"
docker compose run --rm --entrypoint sh ingestion -c "cd /repo/ingestion && ruff check . && ruff format --check . && mypy ingestion tests scripts && python -m pytest -q"
# Frontend, native:
cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build
```

Current baselines: **57** backend, **53** ingestion and **27** frontend tests, all passing. mypy is `strict`.
DB-backed tests need the compose `db` running and migrated (`alembic upgrade head`); they run inside a
transaction that's rolled back, so they never touch real data.

Other useful commands:

```bash
docker compose run --rm ingestion run sbp --series CPI_MOM,TBILL_3M   # one source / subset
docker compose run --rm ingestion backfill psx --from 2016-07-01 --symbols KSE100
docker compose run --rm --no-deps backend alembic revision --autogenerate -m "describe change"  # then REVIEW it
docker compose run --rm ingestion seed --clear                        # remove synthetic rows
```

Exit codes from the ingestion CLI: `0` success, `1` failed, `2` usage error, `3` partial.

---

## 4. How the pieces fit

```
Sources ──fetch──▶ raw_snapshots ──parse/validate──▶ upsert ──▶ Postgres ◀──read── FastAPI ◀──SSR fetch── Next.js
(SBP, FX, PSX,       (exact bytes,                   (chunked,          (Neon)       (/api/v1, cache,       (server
 MUFAP xlsx, CSV,     secrets stripped)               idempotent)                     rate limit, CORS)      components)
 YAML)                     + job_runs row per run (status, rows, redacted error) → /freshness
```

- **Write path and read path are separate.** Ingestion (cron in GitHub Actions) writes and the API only reads. A
  failing source never breaks serving: the last good data stays, with its real "as of" date.
- **The frontend calls the API server-side** (`apiBaseUrl()` uses `API_URL_INTERNAL` on the server in Docker,
  otherwise `NEXT_PUBLIC_API_URL`). Only the compare form and the charts are client components.
- **Compare inputs live in the URL** (`src/lib/params.ts`: parse plus a round-trip test).

### Units and conventions (easy to get wrong)

| Thing | Unit / format |
|---|---|
| API money fields | string, 2 dp (`"125085.66"`) |
| API return/rate fields (`Rate`) | **fraction** string, 6 dp (`"0.250857"` = 25.09%) |
| MUFAP fund returns (`ret_*`) and macro series values | **percent** as published (`"10.83"` = 10.83%), passed through `Exact` |
| Tax `rate` in YAML/DB | fraction as a **quoted string** (`"0.15"`), so YAML yields a Decimal |
| Day count | actual/365 |
| Dates | ISO `YYYY-MM-DD`; "today" means Pakistan time (`clock.today_pkt()`, UTC+5, no DST) |
| Chart colours | fixed slot per asset in `src/lib/series.ts` (colour follows the entity, never rank); max 4 lines |

### Return models (`returns/compare.py`)

- **Savings:** monthly credit at the rate in force (`DEPOSIT_RATE_FRESH`, or the user's `savings_rate`), reinvested.
- **T-bills:** buy at the latest cut-off yield, roll at maturity (91/182/364 days), simple interest within a bill, pro-rata last period.
  Tax is withheld per credit when verified.
- **KSE-100/KMI-30, USD, gold:** price on/before the start date → latest price. No dividends.
- **Funds:** category **median** of the MUFAP trailing return for 1/2/3 years only; annualized categories compound.
- **Inflation:** CPI index chained from month-on-month changes (`CPI_MOM`). Real return = `(1+n)/(1+i)−1`.
- **Shariah mode:** excludes savings and T-bills (with a reason), uses KMI-30 and Shariah fund categories.

---

## 5. Common tasks: how to do them right

**Add a data source**
1. Create `ingestion/ingestion/providers/<name>.py` with a `Provider` subclass. `fetch()` returns `RawPayload`s with
   **no secrets in `url`**; `parse()` returns records from `records.py`. Put non-fatal fetch errors in `ctx.errors`.
2. Register it in `providers/__init__.py`. Add it to `BACKFILLABLE` in `cli.py` if it supports history.
3. Save a small **real** payload under `tests/fixtures/` (or a synthetic one if licensing forbids) and test the
   parser with hand-checked values. Add a validation test for a bad row.
4. If it needs a new table or column: change the models, autogenerate the migration, **review it**, and run it.
5. Add it to `ingest.yml` (and its schedule) and to the Methodology page's `SOURCES`.

**Add a macro series from SBP:** append a `MacroSeriesDef` to `SERIES` in `providers/sbp.py` with a stable
`code`. Verify the key with `GET /api/v1/dataset/{dataset}/meta` (it needs the key). Some SBP datasets return only
blank "Missing value" rows (the detailed `TS_GP_BAM_WALDR_M` has since 2024), so check that the values are real.

**Add an API endpoint:** a router in `api/v1/`, queries in `repo.py`, response models using the `Money`/`Rate`/`Exact`
annotated types from `schemas.py`, registration in `api/v1/__init__.py`, and tests in `tests/test_api.py` (seed data in
`conftest.seed`). Add its prefix to `CACHED_PREFIXES` in `main.py` if it's heavy. Add the type to `frontend/src/lib/api.ts`.

**Change return math:** edit `returns/`, add hand-worked tests first, and update the README's "How returns are
calculated" section, the Methodology page and the dossier if the behaviour changes.

**Change the schema:** never edit an applied migration. Add a new revision. Production migrations run from
`ingest.yml` (Vercel functions have no startup hook), so after deploying a schema change, run the workflow manually.

---

## 6. Deployment facts

| Piece | Where |
|---|---|
| Frontend | Vercel project `bachatcheck` (team `akteam321`), root `frontend`, region sin1. Env: `NEXT_PUBLIC_API_URL` |
| API | Vercel project `bachatcheck-api`, root `backend`, framework FastAPI, Python 3.12, region sin1. Env: `DATABASE_URL` (Neon **pooled**, set by the owner as Sensitive), `CORS_ORIGINS`, `FUNDS_DATA_MODE=demo`, `STOCKS_DATA_MODE=real`, `TRUST_FORWARDED_FOR=true`, `LOG_JSON=true`, `CACHE_TTL_SECONDS=600`, `ENVIRONMENT=production` |
| Database | Neon Postgres 18 (project `divine-mud-61325171`, branch `production`). `.env` holds `DATABASE_URL` (pooled) and `DATABASE_URL_UNPOOLED` (direct), **quoted** |
| Scheduled data | GitHub Actions `ingest.yml`, job `environment: BachatCheck` with secrets `DATABASE_URL_UNPOOLED` (preferred), `DATABASE_URL`, `SBP_EASYDATA_API_KEY`. 22:30 PKT daily (SBP, FX, gold, tax), 16:00 PKT weekdays (PSX) |
| Deployment protection | Vercel Authentication on **previews only**, so production is public |

A push to `main` runs CI and redeploys both Vercel projects. Env var changes need a redeploy to take effect.

---

## 7. Gotchas learned the hard way

- **Quoted connection strings.** Values copied from `.env` include quotes. `Settings._use_psycopg_driver` strips quotes,
  whitespace and a `DATABASE_URL=` prefix, and rewrites `postgres(ql)://` to `postgresql+psycopg://`. Keep that.
- **The health check must never 500.** It uses `optional_session`, so a bad URL reports `"database":"unavailable"`.
- **The Postgres bind-parameter limit (65,535)** breaks large single INSERTs. `writers.CHUNK_ROWS = 1000`.
- **Killed jobs leave `running` rows.** `runner._close_abandoned` fails them after 2 hours. Don't remove it.
- **Vercel blocks vulnerable Next.js versions** (CVE-2025-66478 blocked 15.5.4). Keep `next`, `react` and `eslint-config-next`
  on patched releases, pinned exactly.
- **GitHub secrets scoping.** Environment secrets are invisible unless the job declares `environment:`. The guard step
  "Check secrets" fails fast with a clear message.
- **`notFound()` behind a root `loading.tsx` returns HTTP 200.** That file was removed deliberately; don't add it back.
- **Pages fetched at build time can bake in errors.** `/methodology` is `force-dynamic`; keep data pages dynamic.
- **Frankfurter v1 is gone.** Use `/v2/rates` with `providers=SBP`, which publishes monthly (it lags).
- **SBP EasyData keys expire every 90 days**, with limits of 2,000 calls/day and 250/hour. The key only works as a query param.
- **The GitHub API rate-limits unauthenticated polling** (60/hour). Read the Actions pages instead of looping on the API.
- **psxdata returns floats and flags anomalies.** Validation skips rows where the close falls outside the low–high range.
- **The `api` root path `/` returns 404 by design.** The API lives under `/api/v1` and `/docs`.

---

## 8. Status and backlog

Done: milestones 1–6 (skeleton, ingestion, returns and API, frontend, deploy, portfolio polish) and the live deployment.

Owner actions pending:
- Verify and fill `data/tax_rules.yaml` from current FBR sources (all rates are `null`, so no after-tax figures yet).
- Rotate the SBP key and Neon password (both were exposed in screenshots/chat), then update Vercel, the GitHub
  `BachatCheck` environment and `.env`.
- Add rows to the gold CSV if gold should appear.

Good next steps (each its own PR):
- Redirect the API root `/` to `/docs`.
- Stretch goals from the brief: portfolio tracker with **XIRR**, **Zakat calculator**, weekly email digest, **Urdu toggle** (RTL).
- Alerting on failed ingestion runs; Redis for a shared cache and rate limit if traffic grows; Playwright end-to-end tests.
- Pursue MUFAP/PSX permission or licensed feeds before showing real fund or stock data publicly.

---

## 9. Decision log

| Decision | Why | Revisit if |
|---|---|---|
| Monorepo: `backend` + `ingestion` share one model package | One schema and one migration history | Ingestion needs independent releases |
| Provider pattern, raw-first storage | Parser bugs never lose data; replayable | — |
| Decimal / NUMERIC / string JSON | Exact money math | — |
| Inflation via chained MoM CPI index | Exact over any window | SBP changes the CPI base |
| Tax rules as versioned YAML with `verified` | Never show a guessed tax number | — |
| MUFAP local-only, demo funds in production | MUFAP Terms of Use | Written permission obtained |
| psxdata despite PSX terms (owner's call) | Portfolio project; documented; kill switch `STOCKS_DATA_MODE=demo` | PSX objects or a licence is offered |
| API on Vercel (not Render) | Render's Blueprint asked for a card; Vercel is free with fast cold starts | Need long-running workers |
| Migrations run in GitHub Actions, not on API start | Serverless has no startup hook | Moving to a container host |
| In-process cache and rate limit | Right-sized for free-tier traffic | Multiple instances or heavy traffic → Redis |
| Fund comparison = category median of trailing returns, 1–3 years only | MUFAP gives no NAV history | Our daily NAV snapshots accumulate enough history |
| Savings default = SBP average deposit rate + user override | Only official series; it understates real savings rates, so it's disclosed | A better official savings-rate series appears |

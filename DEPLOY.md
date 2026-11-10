# Deploying BachatCheck

Everything runs on free tiers. Nothing here needs a credit card (as of November 2026: check
each provider's pricing page before you sign up, because free tiers change often).

```mermaid
flowchart LR
  U[Browser] --> V[Vercel<br/>Next.js frontend]
  V -- server-side fetch --> R[Render<br/>FastAPI API]
  R --> N[(Neon<br/>Postgres)]
  G[GitHub Actions<br/>daily cron] -- ingestion jobs --> N
  G -- fetch --> S[SBP EasyData<br/>Frankfurter<br/>PSX]
```

| Piece | Host | Why |
|---|---|---|
| Database | **Neon** (free) | Serverless Postgres: 1 GB per project and 100 compute-hours a month, plenty for this app. It doesn't expire, unlike Render's free Postgres, which is deleted after a trial period. |
| API | **Render** (free web service) | A real free tier with no card, Docker deploys from GitHub, a health check, and a Singapore region (close to Pakistan). Trade-off: it **sleeps after 15 min idle** and takes **~1 min to wake**. The frontend waits up to 50 s and otherwise shows a "waking up" message. Fly.io no longer has a free tier for new accounts, and Railway offers only trial credit. |
| Frontend | **Vercel** (Hobby) | First-class Next.js hosting. Hobby is for personal, non-commercial projects, which fits a portfolio piece. |
| Daily ingestion | **GitHub Actions** cron | Free for public repos; jobs write straight to Neon. |

## 1. Database: Neon

1. Sign up at <https://neon.com> and create a project (region: **AWS Asia Pacific (Singapore)**).
2. On the project dashboard, open **Connect** and copy the **pooled** connection string
   (host contains `-pooler`). It looks like
   `postgresql://USER:PASSWORD@ep-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
   You can paste it as is: the app rewrites `postgresql://` to use the psycopg 3 driver.
3. Keep this string private. You'll paste it into Render and GitHub (steps 2 and 4), never into
   the repo.

The schema is created automatically: the API runs `alembic upgrade head` on every start, and so
does the ingestion workflow.

## 2. API: Render

1. Sign up at <https://render.com> with your GitHub account.
2. **New → Blueprint**, pick the `BachatCheck` repo. Render reads [`render.yaml`](render.yaml)
   and proposes a free Docker web service, `bachatcheck-api`, built from
   [`infra/api.Dockerfile`](infra/api.Dockerfile).
3. Fill in the two secret values it asks for:
   - `DATABASE_URL`: the Neon pooled string from step 1.
   - `CORS_ORIGINS`: your Vercel URL from step 3 (e.g. `https://bachatcheck.vercel.app`). If
     you don't have it yet, put `http://localhost:3000` and update it after step 3.
4. Deploy. When it's live, open `https://<your-service>.onrender.com/api/v1/health`. You should
   see `{"status":"ok", ..., "database":"ok"}`. API docs are at `/docs`.

Preset in `render.yaml`: `FUNDS_DATA_MODE=demo` (MUFAP's terms don't allow public display of
its data), `STOCKS_DATA_MODE=real`, `TRUST_FORWARDED_FOR=true` (Render's proxy), JSON logs,
60 requests/min per IP, 10-minute response cache.

## 3. Frontend: Vercel

1. Sign up at <https://vercel.com> with GitHub. **Add New → Project**, import `BachatCheck`.
2. Set **Root Directory** to `frontend`. Vercel detects Next.js.
3. Add an environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://<your-service>.onrender.com` (no trailing slash).
4. Deploy, then copy the production URL back into Render's `CORS_ORIGINS` (step 2.3) and
   redeploy the API.

`frontend/vercel.json` pins functions to Singapore (`sin1`) so they sit next to the API.

## 4. Daily data: GitHub Actions

1. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:
   - `DATABASE_URL`: the same Neon string.
   - `SBP_EASYDATA_API_KEY`: your EasyData key. **It expires every 90 days**: regenerate it at
     easydata.sbp.org.pk (My Data Basket → My Account) and update this secret.
2. Load history once: **Actions → Ingest data → Run workflow**, then:
   - source `daily`, backfill from `2015-01-01` (policy rate history needs pre-2016 data), then
   - source `psx`, backfill from `2016-07-01`.
3. From then on, [`ingest.yml`](.github/workflows/ingest.yml) runs by itself:
   - **22:30 PKT daily**: tax rules, gold CSV, Frankfurter (USD/PKR), SBP.
   - **16:00 PKT weekdays**: PSX, after the 15:30 close.

   Each run writes `job_runs` rows (see `/api/v1/freshness` and the Methodology page). A
   failed source never deletes data, so the site keeps showing the last good values.

> GitHub pauses scheduled workflows in a public repo after **60 days without commits**. If the
> data stops updating, re-enable the workflow under Actions or push any commit.

MUFAP isn't in the workflow on purpose: its export is downloaded by hand for personal use and
stays local (see `data/README.md`).

## 5. Check it works

- [ ] `GET /api/v1/health` returns `"database":"ok"`
- [ ] `GET /api/v1/freshness` lists recent successful runs for `sbp`, `frankfurter`, `psx`
- [ ] The Vercel site's Compare page shows the inflation headline and the chart
- [ ] The Funds page shows the **Demo data** badge
- [ ] The Methodology page lists every source with a "Last updated" date
- [ ] From another origin, a browser request to the API is blocked by CORS (only your Vercel URL is allowed)

## Updating

- **Code:** push to `main`. CI runs; Render and Vercel redeploy automatically.
- **Tax rates:** edit `data/tax_rules.yaml` (set `rate`, `source_url`, `verified: true`), push,
  then run the workflow with source `tax_rules` (or wait for the nightly run).
- **Gold:** add rows to `data/gold/gold_pkr_per_tola_24k.csv`, push, run source `gold`.

## Costs and limits to watch

| Limit | What happens | What to do |
|---|---|---|
| Render free: sleeps after 15 min idle | First visit after a quiet spell waits ~1 min | Expected; the UI explains it. A paid instance removes it. |
| Render free: 750 instance-hours/month | Service suspended until next month if exceeded | One service sleeping when idle stays well under. |
| Neon free: 1 GB storage | Writes fail when full | `raw_snapshots` grows daily. Prune old rows if needed (`DELETE FROM raw_snapshots WHERE fetched_at < now() - interval '90 days'`). |
| SBP API: key expires every 90 days, 2,000 calls/day | SBP job fails (other sources unaffected) | Renew the key and update the GitHub secret. |
| PSX data | PSX's terms restrict automated retrieval and public display | Set `STOCKS_DATA_MODE=demo` on Render to switch stocks off. |

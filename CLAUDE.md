# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Run Python through Docker (`docker compose run --rm ingestion …`). Native Python on the owner's Windows machine can't
  load SQLAlchemy/psycopg/pydantic wheels (Smart App Control). The frontend works natively with `npm`.
- The owner pushes via Git Credential Manager in an interactive terminal. A non-interactive shell can't prompt for
  GitHub sign-in, so push from a terminal tab.
- The owner enters every secret themselves (Vercel env vars, GitHub environment `BachatCheck`, `.env`). Never paste
  connection strings or keys into tools or dashboards, and never echo values from `.env`.
- Before calling a data change "done", check `/api/v1/freshness` on the live API and the GitHub Actions run page.

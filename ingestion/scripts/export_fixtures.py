"""Dev helper: export small, trimmed real payloads from raw_snapshots into tests/fixtures/.

    docker compose run --rm --entrypoint python ingestion scripts/export_fixtures.py

MUFAP payloads are deliberately NOT exported (MUFAP's terms: personal use only); its parser is
tested against a synthetic workbook built in the test itself.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from bachatcheck.db import _session_factory
from bachatcheck.models import RawSnapshot

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def latest(session: Session, url_like: str) -> RawSnapshot:
    stmt = (
        select(RawSnapshot)
        .where(RawSnapshot.url.like(url_like))
        .order_by(RawSnapshot.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with _session_factory()() as s:
        for name, pattern, keep in [
            ("sbp_cpi_yoy.json", "%P00011516/data%", 4),
            ("sbp_tbill_3m.json", "%TB0010/data%", 3),
            ("sbp_missing_values.json", "%WALDR_M.WALD01360000/data%", 2),
        ]:
            data = json.loads(latest(s, pattern).content)
            data["rows"] = data["rows"][:keep]
            (OUT / name).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")

        fx = json.loads(latest(s, "%frankfurter.dev%").content)[:5]
        (OUT / "frankfurter_usd_pkr.json").write_text(json.dumps(fx, indent=1) + "\n")

        raw = latest(s, "psxdata://stocks/KSE100%")
        rows = list(csv.reader(io.StringIO(raw.content.decode())))[:6]
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerows(rows)
        (OUT / "psx_kse100.csv").write_text(buf.getvalue())
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()

"""Pakistan time. Pakistan has no DST, so a fixed UTC+5 offset is exact."""

from datetime import date, datetime, timedelta, timezone

PKT = timezone(timedelta(hours=5), name="PKT")


def today_pkt() -> date:
    return datetime.now(PKT).date()

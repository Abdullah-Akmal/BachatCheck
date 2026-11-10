from datetime import date

from ingestion.providers.base import FetchContext
from ingestion.providers.demo_seed import DemoSeedProvider, generate
from ingestion.records import FxRateRecord, MacroObservationRecord, PriceBarRecord

AS_OF = date(2026, 11, 10)


def test_generation_is_deterministic() -> None:
    assert generate(AS_OF) == generate(AS_OF)


def test_every_generated_record_passes_validation() -> None:
    provider = DemoSeedProvider()
    [payload] = provider.fetch(FetchContext(as_of=AS_OF))
    records = provider.parse(payload)
    problems = [r for r in records if r.validate(AS_OF) is not None]
    assert problems == []

    codes = {r.series.code for r in records if isinstance(r, MacroObservationRecord)}
    assert {"CPI_MOM", "POLICY_RATE", "TBILL_3M", "TBILL_12M", "DEPOSIT_RATE_FRESH"} <= codes
    symbols = {r.instrument.symbol for r in records if isinstance(r, PriceBarRecord)}
    assert symbols == {"KSE100", "KMI30", "DEMOA", "DEMOB", "GOLD24K_TOLA"}
    assert any(isinstance(r, FxRateRecord) for r in records)
    # Everything is tagged as demo data.
    assert {
        r.source for r in records if isinstance(r, PriceBarRecord | MacroObservationRecord)
    } == {"demo_seed"}
    assert {r.provider for r in records if isinstance(r, FxRateRecord)} == {"demo_seed"}


def test_nothing_after_as_of() -> None:
    data = generate(date(2020, 1, 15))
    assert max(d for d, *_ in data["bars"]["KSE100"]) <= "2020-01-15"
    assert max(d for d, _ in data["macro"]["CPI_MOM"]) <= "2020-01-15"

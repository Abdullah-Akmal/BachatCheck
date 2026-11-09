"""Data-source providers. Each implements `Provider` and is registered in `REGISTRY`."""

from ingestion.providers.base import Provider
from ingestion.providers.frankfurter import FrankfurterProvider
from ingestion.providers.gold import GoldCsvProvider
from ingestion.providers.mufap import MufapProvider
from ingestion.providers.psx import PsxProvider
from ingestion.providers.sbp import SbpProvider
from ingestion.providers.tax_rules import TaxRulesProvider

REGISTRY: dict[str, type[Provider]] = {
    p.name: p
    for p in (
        FrankfurterProvider,
        GoldCsvProvider,
        MufapProvider,
        PsxProvider,
        SbpProvider,
        TaxRulesProvider,
    )
}

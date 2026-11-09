# data/

Versioned inputs that aren't fetched from an API.

| File | What | How it's loaded |
|---|---|---|
| `tax_rules.yaml` | Tax assumptions (rates are **placeholders** until verified against FBR) | `python -m ingestion run tax_rules` |
| `gold/gold_pkr_per_tola_24k.csv` | Gold, PKR per tola (24k), maintained by hand. Columns: `date,price_pkr,source_note` | `python -m ingestion run gold` |
| `mufap_inbox/` | **Not committed.** MUFAP "Performance Summary" Excel exports you download by hand | `python -m ingestion run mufap` |

## Gold CSV

No free, reliable source of Pakistani local gold prices was found, so this file is updated by
hand and the app labels gold as "manually updated". Add one row per date, with the price of 24k
gold per tola in PKR and a short note on where the number came from (e.g. the Sarafa association
rate you read). Don't invent or interpolate values.

## MUFAP exports

1. Open https://www.mufap.com.pk/Industry/IndustryStatDaily?tab=1 (Performance Summary).
2. Click **Excel** and save the file into `data/mufap_inbox/`.
3. Run `python -m ingestion run mufap`.

MUFAP's Terms of Use allow personal, non-commercial use only, so these files stay out of git
and the public deployment shows demo fund data instead.

/**
 * Chart identity. Each asset owns a FIXED categorical slot (color follows the entity, never
 * its rank or position). Shariah variants share their conventional counterpart's slot —
 * the two never appear in the same view. Slot colors are CSS variables in globals.css
 * (reference palette, validated for adjacent-pair CVD separation in light and dark).
 */

export const SERIES_SLOT: Record<string, number> = {
  savings: 1,
  tbill_3m: 2,
  kse100: 3,
  kmi30: 3,
  "fund:money_market": 4,
  "fund:shariah_compliant_money_market": 4,
  usd: 5,
  gold: 6,
  "fund:income": 7,
  "fund:shariah_compliant_income": 7,
  "fund:equity": 8,
  "fund:shariah_compliant_equity": 8,
};

/** At most this many asset lines at once, so the chart stays legible on a phone. */
export const MAX_CHART_SERIES = 4;

export const DEFAULT_CHART_KEYS = [
  "savings",
  "tbill_3m",
  "kse100",
  "kmi30",
  "fund:money_market",
  "fund:shariah_compliant_money_market",
];

export function seriesColor(key: string): string {
  const slot = SERIES_SLOT[key];
  return slot ? `var(--series-${slot})` : "var(--text-muted)";
}

export function chartable(key: string): boolean {
  return key in SERIES_SLOT;
}

import type { CompareParams } from "@/lib/api";

export const YEAR_OPTIONS = [1, 2, 3, 5, 10] as const;
export const DEFAULT_PARAMS: CompareParams = {
  amount: 100_000,
  years: 3,
  shariah: false,
  filer_status: "filer",
};
export const MAX_AMOUNT = 100_000_000_000;

type Raw = Record<string, string | string[] | undefined>;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/** Parse untrusted URL params into valid compare inputs, falling back to defaults. */
export function parseCompareParams(raw: Raw): CompareParams {
  const amount = Number(first(raw.amount)?.replace(/,/g, ""));
  const years = Number(first(raw.years));
  const rate = first(raw.savings_rate);
  const rateNum = rate === undefined || rate === "" ? undefined : Number(rate);
  return {
    amount: Number.isFinite(amount) && amount > 0 && amount <= MAX_AMOUNT ? Math.round(amount) : DEFAULT_PARAMS.amount,
    years: (YEAR_OPTIONS as readonly number[]).includes(years) ? years : DEFAULT_PARAMS.years,
    shariah: first(raw.shariah) === "true",
    filer_status: first(raw.filer_status) === "non_filer" ? "non_filer" : "filer",
    savings_rate: rateNum !== undefined && Number.isFinite(rateNum) && rateNum >= 0 && rateNum <= 50 ? rateNum : undefined,
  };
}

export function compareQuery(p: CompareParams): string {
  const q = new URLSearchParams({ amount: String(p.amount), years: String(p.years) });
  if (p.shariah) q.set("shariah", "true");
  if (p.filer_status !== "filer") q.set("filer_status", p.filer_status);
  if (p.savings_rate !== undefined) q.set("savings_rate", String(p.savings_rate));
  return q.toString();
}

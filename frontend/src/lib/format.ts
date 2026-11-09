/**
 * Display formatting. Inputs are the API's decimal strings; we only convert to Number here,
 * for display, after all money math has been done server-side in Decimal.
 */

const grouped = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

function toNumber(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** "1250000.40" -> "Rs 1,250,000". Negative -> "-Rs 1,250". */
export function formatPKR(v: string | number | null | undefined): string {
  const n = toNumber(v);
  if (n === null) return "—";
  const abs = grouped.format(Math.abs(Math.round(n)));
  return `${n < 0 ? "-" : ""}Rs ${abs}`;
}

/** Compact axis labels: 1,250,000 -> "Rs 1.25M", 125,000 -> "Rs 125k". */
export function formatPKRCompact(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}Rs ${(abs / 1e9).toFixed(abs >= 1e10 ? 0 : 1)}B`;
  if (abs >= 1e6) return `${sign}Rs ${(abs / 1e6).toFixed(abs >= 1e7 ? 0 : 2)}M`;
  if (abs >= 1e3) return `${sign}Rs ${(abs / 1e3).toFixed(abs >= 1e4 ? 0 : 1)}k`;
  return `${sign}Rs ${abs.toFixed(0)}`;
}

/** Fraction string "0.126825" -> "12.7%". */
export function formatFractionPct(v: string | null | undefined, digits = 1): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

/** Signed fraction: "0.0230" -> "+2.3%". */
export function formatSignedPct(v: string | null | undefined, digits = 1): string {
  const n = toNumber(v);
  if (n === null) return "—";
  const s = (n * 100).toFixed(digits);
  return n > 0 ? `+${s}%` : `${s}%`;
}

/** Percent string as published (MUFAP): "10.83" -> "10.83%". */
export function formatPercentValue(v: string | null | undefined, digits = 2): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return `${n.toFixed(digits)}%`;
}

export function formatNumber(v: string | null | undefined, digits = 2): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit", timeZone: "UTC" });

/** "2026-11-06" -> "6 Nov 2026". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return Number.isNaN(d.getTime()) ? "—" : dateFmt.format(d);
}

/** Axis tick: "2026-11-06" -> "Nov 26". */
export function formatMonth(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : monthFmt.format(d);
}

export function isPositive(v: string | null | undefined): boolean | null {
  const n = toNumber(v);
  return n === null ? null : n > 0;
}

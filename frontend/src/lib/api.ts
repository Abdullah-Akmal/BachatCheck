/**
 * Typed client for the BachatCheck API.
 *
 * The API sends money and rates as decimal strings (never floats). We keep them as strings
 * in these types and convert only at display time in lib/format.ts.
 */

export type Dec = string; // decimal string, e.g. "125085.66" or "0.126825"

export function apiBaseUrl(): string {
  if (typeof window === "undefined" && process.env.API_URL_INTERNAL) {
    return process.env.API_URL_INTERNAL;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

export async function apiGet<T>(path: string, query: Query = {}, revalidate = 300): Promise<T> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  let res: Response;
  try {
    res = await fetch(`${apiBaseUrl()}/api/v1${path}${qs ? `?${qs}` : ""}`, {
      next: { revalidate },
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    throw new ApiError(0, "Couldn't reach the BachatCheck API. Please try again shortly.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

// --- /compare ------------------------------------------------------------------------

export type TaxInfo = {
  status: "applied" | "unverified" | "not_applicable";
  asset_class: string;
  tax_type: string;
  rate: Dec | null;
  source_url: string | null;
};

export type CompareAsset = {
  key: string;
  label: string;
  group: string;
  available: boolean;
  reason: string | null;
  notes: string[];
  demo: boolean;
  data_as_of: string | null;
  path_kind: "actual" | "interpolated";
  end_value: Dec | null;
  nominal_return: Dec | null;
  cagr: Dec | null;
  real_end_value: Dec | null;
  real_return: Dec | null;
  tax: TaxInfo | null;
  post_tax_end_value: Dec | null;
  post_tax_return: Dec | null;
  post_tax_real_return: Dec | null;
  nominal_series: (Dec | null)[];
  real_series: (Dec | null)[];
};

export type CompareResponse = {
  amount: Dec;
  years: number;
  start: string;
  end: string;
  shariah_only: boolean;
  filer_status: "filer" | "non_filer";
  cpi_as_of: string | null;
  headline: {
    amount: Dec;
    inflation: Dec | null;
    inflation_cagr: Dec | null;
    amount_needed_to_keep_up: Dec | null;
    beat_inflation: string[];
    lost_to_inflation: string[];
    best_real: string | null;
  };
  dates: string[];
  inflation_series: (Dec | null)[];
  assets: CompareAsset[];
  disclaimer: string;
};

export type CompareParams = {
  amount: number;
  years: number;
  shariah: boolean;
  filer_status: "filer" | "non_filer";
  savings_rate?: number;
};

// --- /funds --------------------------------------------------------------------------

export type DataMeta = {
  data_mode: "real" | "demo";
  as_of: string | null;
  source: string;
  notes: string[];
};

export const RETURN_KEYS = [
  "ret_ytd",
  "ret_mtd",
  "ret_1d",
  "ret_15d",
  "ret_30d",
  "ret_90d",
  "ret_180d",
  "ret_270d",
  "ret_365d",
  "ret_2y",
  "ret_3y",
] as const;
export type ReturnKey = (typeof RETURN_KEYS)[number];

export type Fund = {
  symbol: string;
  name: string;
  category: string;
  sector: string | null;
  amc: string | null;
  rating: string | null;
  is_shariah: boolean;
  return_basis: "annualized" | "absolute" | null;
  as_of_date: string;
  nav: Dec;
} & { [K in ReturnKey]: Dec | null };

export type FundsResponse = { meta: DataMeta; total: number; funds: Fund[] };
export type FundCategory = {
  category: string;
  is_shariah: boolean;
  return_basis: string | null;
  count: number;
};
export type FundDetail = { meta: DataMeta; fund: Fund; nav_history: [string, Dec][] };

// --- /stocks -------------------------------------------------------------------------

export type Instrument = {
  kind: "stock" | "index";
  symbol: string;
  name: string;
  is_shariah: boolean | null;
  first_date: string | null;
  last_date: string | null;
};

export type Performance = {
  start: string;
  end: string;
  start_price: Dec;
  end_price: Dec;
  total_return: Dec;
  cagr: Dec | null;
};

export const STOCK_PERIODS = ["1m", "3m", "6m", "1y", "3y", "5y", "max"] as const;
export type StockPeriod = (typeof STOCK_PERIODS)[number];

export type StockResponse = {
  meta: DataMeta;
  instrument: Instrument;
  period: StockPeriod;
  requested_start: string;
  partial: boolean;
  prices: [string, Dec][];
  performance: Performance | null;
  benchmark: Performance | null;
  benchmark_symbol: string;
  rebased: [string, Dec | null, Dec | null][];
};

// --- meta ----------------------------------------------------------------------------

export type Freshness = {
  sources: {
    source: string;
    last_success_at: string | null;
    last_run_at: string | null;
    last_status: string | null;
    last_error: string | null;
  }[];
  data_as_of: Record<string, string | null>;
};

export type TaxRule = {
  asset_class: string;
  tax_type: string;
  filer_status: string;
  rate: Dec | null;
  effective_from: string;
  effective_to: string | null;
  source_url: string | null;
  notes: string | null;
  verified: boolean;
};

export type MacroSeries = {
  code: string;
  name: string;
  unit: string;
  frequency: string;
  source: string;
  first_date: string | null;
  last_date: string | null;
  observations: number;
};

export type AppConfig = {
  funds_data_mode: "real" | "demo";
  stocks_data_mode: "real" | "demo";
  savings_benchmark_series: string;
};

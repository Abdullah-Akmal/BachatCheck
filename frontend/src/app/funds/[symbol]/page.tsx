import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { NavChart } from "./nav-chart";
import { AsOf, Card, DemoBadge, EmptyState, ErrorState, Notice } from "@/components/ui";
import { ApiError, apiGet, type FundDetail } from "@/lib/api";
import { formatNumber, formatPercentValue } from "@/lib/format";

type Props = { params: Promise<{ symbol: string }> };

const PERIODS = [
  ["ret_1d", "1 day"],
  ["ret_15d", "15 days"],
  ["ret_30d", "30 days"],
  ["ret_90d", "90 days"],
  ["ret_180d", "180 days"],
  ["ret_270d", "270 days"],
  ["ret_365d", "1 year"],
  ["ret_2y", "2 years"],
  ["ret_3y", "3 years"],
  ["ret_mtd", "Month to date"],
  ["ret_ytd", "Year to date"],
] as const;

async function load(symbol: string): Promise<FundDetail | null> {
  try {
    return await apiGet<FundDetail>(`/funds/${encodeURIComponent(symbol)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { symbol } = await params;
  const d = await load(symbol).catch(() => null);
  return { title: d?.fund.name ?? "Fund" };
}

export default async function FundPage({ params }: Props) {
  const { symbol } = await params;
  let data: FundDetail | null;
  try {
    data = await load(symbol);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Unexpected error."} />;
  }
  if (!data) notFound();
  const f = data.fund;

  return (
    <div className="space-y-5">
      <Link href="/funds" className="text-sm text-ink-2 hover:text-ink">
        ← All funds
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-bold tracking-tight">
            {f.name} {data.meta.data_mode === "demo" && <DemoBadge />}
          </h1>
          <p className="mt-1 text-sm text-ink-2">
            {f.category}
            {f.is_shariah && " · Shariah-compliant"}
            {f.rating && ` · Rating ${f.rating}`}
          </p>
        </div>
        <AsOf date={f.as_of_date} label="NAV as of" />
      </div>

      {data.meta.data_mode === "demo" && <Notice>{data.meta.notes[0]}</Notice>}

      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <p className="text-xs text-muted">NAV (PKR per unit)</p>
          <p className="mt-1 text-2xl font-semibold tabular">{formatNumber(f.nav, 4)}</p>
        </Card>
        <Card>
          <p className="text-xs text-muted">1-year return</p>
          <p className="mt-1 text-2xl font-semibold tabular">{formatPercentValue(f.ret_365d)}</p>
        </Card>
        <Card>
          <p className="text-xs text-muted">How returns are quoted</p>
          <p className="mt-1 font-medium">{f.return_basis === "annualized" ? "Annualized" : "Absolute (not annualized)"}</p>
        </Card>
      </div>

      <Card>
        <h2 className="font-semibold">Trailing returns</h2>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          {PERIODS.map(([k, label]) => (
            <div key={k} className="flex justify-between gap-2 border-b border-line pb-1">
              <dt className="text-ink-2">{label}</dt>
              <dd className="tabular">{formatPercentValue(f[k])}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card>
        <h2 className="font-semibold">NAV history</h2>
        {data.nav_history.length < 2 ? (
          <div className="mt-3">
            <EmptyState title="History is still building">
              MUFAP publishes only the current NAV, so BachatCheck stores a snapshot each day. This fund has{" "}
              {data.nav_history.length} so far.
            </EmptyState>
          </div>
        ) : (
          <div className="mt-3">
            <NavChart history={data.nav_history} name={f.name} />
          </div>
        )}
      </Card>
      <p className="text-xs text-muted">Source: {data.meta.source}.</p>
    </div>
  );
}

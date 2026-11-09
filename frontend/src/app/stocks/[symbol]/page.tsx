import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StockChart } from "./stock-chart";
import { AsOf, Card, ErrorState, Notice } from "@/components/ui";
import { ApiError, STOCK_PERIODS, apiGet, type Performance, type StockPeriod, type StockResponse } from "@/lib/api";
import { formatDate, formatFractionPct, formatNumber, formatSignedPct, isPositive } from "@/lib/format";

type Props = {
  params: Promise<{ symbol: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

const PERIOD_LABEL: Record<StockPeriod, string> = {
  "1m": "1M",
  "3m": "3M",
  "6m": "6M",
  "1y": "1Y",
  "3y": "3Y",
  "5y": "5Y",
  max: "Max",
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return { title: (await params).symbol.toUpperCase() };
}

function PerfCard({ title, perf }: { title: string; perf: Performance | null }) {
  const pos = isPositive(perf?.total_return);
  return (
    <Card>
      <p className="text-xs text-muted">{title}</p>
      {perf ? (
        <>
          <p className={`mt-1 text-2xl font-semibold tabular ${pos ? "text-good" : "text-bad"}`}>
            <span aria-hidden>{pos ? "▲ " : "▼ "}</span>
            {formatSignedPct(perf.total_return)}
          </p>
          <p className="text-xs text-ink-2 tabular">
            {formatNumber(perf.start_price)} → {formatNumber(perf.end_price)}
            {perf.cagr && ` · ${formatFractionPct(perf.cagr)} a year`}
          </p>
          <p className="text-xs text-muted">
            {formatDate(perf.start)} – {formatDate(perf.end)}
          </p>
        </>
      ) : (
        <p className="mt-1 text-sm text-ink-2">Not enough data for this period.</p>
      )}
    </Card>
  );
}

export default async function StockPage({ params, searchParams }: Props) {
  const symbol = (await params).symbol.toUpperCase();
  const rawPeriod = (await searchParams).period;
  const p = Array.isArray(rawPeriod) ? rawPeriod[0] : rawPeriod;
  const period: StockPeriod = (STOCK_PERIODS as readonly string[]).includes(p ?? "") ? (p as StockPeriod) : "1y";

  let data: StockResponse;
  try {
    data = await apiGet<StockResponse>(`/stocks/${encodeURIComponent(symbol)}`, { period });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    if (e instanceof ApiError && e.status === 503) return <Notice>Stock data isn&apos;t available on this deployment.</Notice>;
    return <ErrorState message={e instanceof ApiError ? e.message : "Unexpected error."} />;
  }
  const isBenchmark = data.instrument.symbol === data.benchmark_symbol;

  return (
    <div className="space-y-5">
      <Link href="/stocks" className="text-sm text-ink-2 hover:text-ink">
        ← Stock lookup
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{data.instrument.symbol}</h1>
          <p className="mt-1 text-sm text-ink-2">
            {data.instrument.name !== data.instrument.symbol && `${data.instrument.name} · `}
            {data.instrument.kind === "index" ? "Index" : "PSX stock"}
            {data.instrument.is_shariah && " · Shariah index"}
          </p>
        </div>
        <AsOf date={data.meta.as_of} label="Prices as of" />
      </div>

      <nav aria-label="Period" className="flex gap-1 overflow-x-auto">
        {STOCK_PERIODS.map((key) => (
          <Link
            key={key}
            href={`/stocks/${data.instrument.symbol}?period=${key}`}
            aria-current={key === period ? "page" : undefined}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              key === period ? "bg-brand text-brand-ink" : "border border-line bg-surface text-ink-2"
            }`}
          >
            {PERIOD_LABEL[key]}
          </Link>
        ))}
      </nav>

      {data.partial && (
        <Notice title="Shorter history than the period you picked">
          Our prices for {data.instrument.symbol} start on {formatDate(data.prices[0]?.[0])}, after the period&apos;s
          start ({formatDate(data.requested_start)}). The figures below cover only the dates we have.
        </Notice>
      )}

      <div className={`grid gap-3 ${isBenchmark ? "" : "sm:grid-cols-2"}`}>
        <PerfCard title={`${data.instrument.symbol} price return`} perf={data.performance} />
        {!isBenchmark && <PerfCard title={`${data.benchmark_symbol} over the same dates`} perf={data.benchmark} />}
      </div>

      <Card>
        <h2 className="font-semibold">{isBenchmark ? "Index level" : `${data.instrument.symbol} vs ${data.benchmark_symbol}, rebased to 100`}</h2>
        <div className="mt-3">
          <StockChart data={data} isBenchmark={isBenchmark} />
        </div>
      </Card>

      <p className="text-xs text-muted">
        {data.meta.notes.join(" ")} Source: {data.meta.source}.
      </p>
    </div>
  );
}

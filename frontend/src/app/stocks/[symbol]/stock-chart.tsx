"use client";

import { EmptyState } from "@/components/ui";
import { PriceChart } from "@/components/price-chart";
import type { StockResponse } from "@/lib/api";
import { formatNumber } from "@/lib/format";

export function StockChart({ data, isBenchmark }: { data: StockResponse; isBenchmark: boolean }) {
  if (data.prices.length < 2) {
    return <EmptyState title="Not enough price history for this period" />;
  }
  if (isBenchmark) {
    const rows = data.prices.map(([date, v]) => ({ date, level: Number(v) }));
    return (
      <PriceChart
        rows={rows}
        series={[{ key: "level", label: data.instrument.symbol, color: "var(--series-3)" }]}
        valueFormat={(v) => formatNumber(String(v), 0)}
        ariaLabel={`${data.instrument.symbol} level over ${rows.length} trading days.`}
      />
    );
  }
  const rows = data.rebased.map(([date, s, b]) => ({
    date,
    stock: s === null ? null : Number(s),
    bench: b === null ? null : Number(b),
  }));
  const last = rows[rows.length - 1];
  return (
    <PriceChart
      rows={rows}
      series={[
        { key: "stock", label: data.instrument.symbol, color: "var(--series-1)" },
        { key: "bench", label: data.benchmark_symbol, color: "var(--text-secondary)", dashed: true },
      ]}
      valueFormat={(v) => formatNumber(String(v), 0)}
      ariaLabel={`${data.instrument.symbol} ends at ${formatNumber(String(last?.stock ?? ""), 1)} and ${data.benchmark_symbol} at ${formatNumber(String(last?.bench ?? ""), 1)}, both starting at 100.`}
    />
  );
}

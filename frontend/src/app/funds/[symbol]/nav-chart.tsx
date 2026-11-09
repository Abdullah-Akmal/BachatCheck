"use client";

import { PriceChart } from "@/components/price-chart";
import { formatNumber } from "@/lib/format";

export function NavChart({ history, name }: { history: [string, string][]; name: string }) {
  const rows = history.map(([date, nav]) => ({ date, nav: Number(nav) }));
  const last = history[history.length - 1];
  return (
    <PriceChart
      rows={rows}
      series={[{ key: "nav", label: "NAV", color: "var(--series-1)" }]}
      valueFormat={(v) => formatNumber(String(v), 2)}
      ariaLabel={`NAV history for ${name}: ${history.length} snapshots, latest ${formatNumber(last?.[1] ?? null, 4)}.`}
    />
  );
}

"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatDate, formatMonth } from "@/lib/format";

export type ChartSeries = { key: string; label: string; color: string; dashed?: boolean };

/** Single-axis line chart over date rows. Used for NAV history and stock-vs-index charts. */
export function PriceChart({
  rows,
  series,
  valueFormat,
  ariaLabel,
}: {
  rows: ({ date: string } & Record<string, number | string | null>)[];
  series: ChartSeries[];
  valueFormat: (v: number) => string;
  ariaLabel: string;
}) {
  return (
    <div className="h-64 sm:h-72" role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatMonth}
            minTickGap={32}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            stroke="var(--axis)"
            tickLine={false}
          />
          <YAxis
            tickFormatter={valueFormat}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            width={60}
            axisLine={false}
            tickLine={false}
            domain={["auto", "auto"]}
          />
          <Tooltip
            cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            content={({ active, label, payload }) =>
              active && payload?.length ? (
                <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-md">
                  <p className="font-medium">{formatDate(String(label))}</p>
                  {payload.map((p) => (
                    <p key={String(p.dataKey)} className="mt-0.5 flex items-center justify-between gap-3">
                      <span className="flex items-center gap-1.5 text-ink-2">
                        <span aria-hidden className="inline-block size-2 rounded-full" style={{ background: String(p.color) }} />
                        {series.find((s) => s.key === p.dataKey)?.label}
                      </span>
                      <span className="tabular text-ink">{valueFormat(Number(p.value))}</span>
                    </p>
                  ))}
                </div>
              ) : null
            }
          />
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={2}
              strokeDasharray={s.dashed ? "5 4" : undefined}
              dot={rows.length < 3 ? { r: 4 } : false}
              activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

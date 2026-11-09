"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { CompareResponse } from "@/lib/api";
import { formatDate, formatMonth, formatPKR, formatPKRCompact } from "@/lib/format";
import { DEFAULT_CHART_KEYS, MAX_CHART_SERIES, chartable, seriesColor } from "@/lib/series";

type Mode = "real" | "nominal";
type Row = { date: string } & Record<string, number | string | null>;

const INFLATION = "__inflation";

function toNum(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function GrowthChart({ data }: { data: CompareResponse }) {
  const candidates = useMemo(() => data.assets.filter((a) => a.available && chartable(a.key)), [data.assets]);
  const [mode, setMode] = useState<Mode>("real");
  const [selected, setSelected] = useState<string[]>(() =>
    candidates
      .filter((a) => DEFAULT_CHART_KEYS.includes(a.key))
      .slice(0, MAX_CHART_SERIES)
      .map((a) => a.key),
  );

  const shown = candidates.filter((a) => selected.includes(a.key));
  const rows: Row[] = useMemo(
    () =>
      data.dates.map((date, i) => {
        const row: Row = { date };
        // In real terms, keeping up with inflation is a flat line at the starting amount.
        row[INFLATION] = mode === "real" ? Number(data.amount) : toNum(data.inflation_series[i]);
        for (const a of candidates) {
          row[a.key] = toNum((mode === "real" ? a.real_series : a.nominal_series)[i] ?? null);
        }
        return row;
      }),
    [data, candidates, mode],
  );

  function toggle(key: string) {
    setSelected((cur) =>
      cur.includes(key) ? cur.filter((k) => k !== key) : cur.length >= MAX_CHART_SERIES ? cur : [...cur, key],
    );
  }

  const labels = new Map(candidates.map((a) => [a.key, a.label]));
  const last = rows[rows.length - 1];
  const summary = shown
    .map((a) => `${a.label} ends at ${formatPKR(last?.[a.key] as number | null)}`)
    .join("; ");

  return (
    <section aria-labelledby="chart-title" className="rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="chart-title" className="text-lg font-semibold">
          Growth of {formatPKR(data.amount)}
        </h2>
        <div role="radiogroup" aria-label="Show values" className="flex rounded-lg bg-surface-2 p-0.5 text-sm">
          {(["real", "nominal"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={mode === m}
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1.5 ${mode === m ? "bg-surface font-medium text-ink shadow-sm" : "text-ink-2"}`}
            >
              {m === "real" ? "After inflation" : "Rupees (nominal)"}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1 text-xs text-ink-2">
        {mode === "real"
          ? `In ${formatDate(data.start)} rupees. Above the dashed line = beat inflation.`
          : "Dashed line = what you'd need just to keep up with prices."}
      </p>

      <fieldset className="mt-3">
        <legend className="text-xs text-muted">
          Show up to {MAX_CHART_SERIES} (legend)
        </legend>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {candidates.map((a) => {
            const on = selected.includes(a.key);
            const disabled = !on && selected.length >= MAX_CHART_SERIES;
            return (
              <button
                key={a.key}
                type="button"
                aria-pressed={on}
                disabled={disabled}
                onClick={() => toggle(a.key)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
                  on ? "border-ink/30 bg-surface-2 text-ink" : "border-line text-ink-2"
                } disabled:opacity-40`}
              >
                <span
                  aria-hidden
                  className="inline-block size-2.5 rounded-full"
                  style={{ background: on ? seriesColor(a.key) : "transparent", boxShadow: `inset 0 0 0 1.5px ${seriesColor(a.key)}` }}
                />
                {a.label}
              </button>
            );
          })}
          <span className="inline-flex items-center gap-1.5 px-1 text-xs text-ink-2">
            <svg width="16" height="4" aria-hidden>
              <line x1="0" y1="2" x2="16" y2="2" stroke="var(--text-secondary)" strokeWidth="2" strokeDasharray="4 3" />
            </svg>
            Inflation
          </span>
        </div>
      </fieldset>

      <div className="mt-3 h-72 sm:h-80" role="img" aria-label={`Line chart. ${summary}.`}>
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
              tickFormatter={formatPKRCompact}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              width={64}
              stroke="var(--axis)"
              tickLine={false}
              axisLine={false}
              domain={["auto", "auto"]}
            />
            <Tooltip
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
              content={({ active, label, payload }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-md">
                    <p className="font-medium">{formatDate(String(label))}</p>
                    <ul className="mt-1 space-y-0.5">
                      {[...payload]
                        .sort((a, b) => Number(b.value) - Number(a.value))
                        .map((p) => (
                          <li key={String(p.dataKey)} className="flex items-center justify-between gap-3">
                            <span className="flex items-center gap-1.5 text-ink-2">
                              <span aria-hidden className="inline-block size-2 rounded-full" style={{ background: String(p.color) }} />
                              {p.dataKey === INFLATION ? "Inflation" : labels.get(String(p.dataKey))}
                            </span>
                            <span className="tabular text-ink">{formatPKR(p.value as number)}</span>
                          </li>
                        ))}
                    </ul>
                  </div>
                ) : null
              }
            />
            <Line
              dataKey={INFLATION}
              stroke="var(--text-secondary)"
              strokeDasharray="5 4"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            {shown.map((a) => (
              <Line
                key={a.key}
                dataKey={a.key}
                stroke={seriesColor(a.key)}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {shown.some((a) => a.path_kind === "interpolated") && (
        <p className="mt-2 text-xs text-muted">
          Mutual fund lines are drawn between start and end values from MUFAP&apos;s trailing returns; the path in between is
          illustrative.
        </p>
      )}
    </section>
  );
}

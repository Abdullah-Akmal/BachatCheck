import type { Metadata } from "next";
import Link from "next/link";

import { EmptyState, ErrorState, Notice } from "@/components/ui";
import { ApiError, apiGet, type Instrument } from "@/lib/api";
import { formatDate } from "@/lib/format";

export const metadata: Metadata = { title: "Stock lookup" };

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

const QUICK_PICKS = ["KSE100", "KMI30", "OGDC", "PPL", "HBL", "MCB", "UBL", "MEBL", "LUCK", "HUBC", "FFC", "SYS"];

export default async function StocksPage({ searchParams }: Props) {
  const raw = (await searchParams).q;
  const q = (Array.isArray(raw) ? raw[0] : raw)?.trim().slice(0, 40) ?? "";

  let results: Instrument[] | null = null;
  let error: ApiError | null = null;
  if (q) {
    try {
      results = await apiGet<Instrument[]>("/stocks/search", { q });
    } catch (e) {
      error = e instanceof ApiError ? e : new ApiError(500, "Unexpected error.");
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Stock lookup</h1>
        <p className="mt-1 text-sm text-ink-2">
          Search a PSX ticker to see its price history and how it did against the KSE-100.
        </p>
      </div>

      <form method="get" action="/stocks" role="search" className="flex gap-2">
        <label className="sr-only" htmlFor="q">
          Ticker or company
        </label>
        <input
          id="q"
          name="q"
          defaultValue={q}
          placeholder="e.g. OGDC, HBL"
          autoCapitalize="characters"
          className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-2.5 uppercase"
        />
        <button type="submit" className="rounded-lg bg-brand px-4 py-2.5 font-medium text-brand-ink">
          Search
        </button>
      </form>

      {error?.status === 503 ? (
        <Notice>Stock data isn&apos;t available on this deployment.</Notice>
      ) : error ? (
        <ErrorState message={error.message} />
      ) : results ? (
        results.length === 0 ? (
          <EmptyState title={`No matches for “${q}”`}>
            We track a short watchlist of PSX symbols. Try one of the quick picks below.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
            {results.map((r) => (
              <li key={r.symbol}>
                <Link href={`/stocks/${r.symbol}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-2">
                  <span>
                    <span className="font-medium">{r.symbol}</span>
                    {r.name !== r.symbol && <span className="ml-2 text-sm text-ink-2">{r.name}</span>}
                    {r.kind === "index" && <span className="ml-2 text-xs text-muted">Index</span>}
                  </span>
                  <span className="text-xs text-muted">to {formatDate(r.last_date)}</span>
                </Link>
              </li>
            ))}
          </ul>
        )
      ) : null}

      <section aria-labelledby="picks">
        <h2 id="picks" className="text-sm font-medium text-ink-2">
          Quick picks
        </h2>
        <div className="mt-2 flex flex-wrap gap-2">
          {QUICK_PICKS.map((s) => (
            <Link key={s} href={`/stocks/${s}`} className="rounded-full border border-line bg-surface px-3 py-1.5 text-sm hover:bg-surface-2">
              {s}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";

import { AsOf, DemoBadge, EmptyState, ErrorState, Notice } from "@/components/ui";
import { ApiError, apiGet, type Fund, type FundCategory, type FundsResponse } from "@/lib/api";
import { formatNumber, formatPercentValue } from "@/lib/format";

export const metadata: Metadata = { title: "Mutual funds" };

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

const COLUMNS = [
  { key: "ret_30d", label: "30 days" },
  { key: "ret_90d", label: "90 days" },
  { key: "ret_365d", label: "1 year" },
  { key: "ret_ytd", label: "YTD" },
] as const;
const SORTS = new Set(["name", "category", "nav", ...COLUMNS.map((c) => c.key)]);

function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

function ReturnCell({ fund, k }: { fund: Fund; k: (typeof COLUMNS)[number]["key"] }) {
  const v = fund[k];
  const n = v === null ? null : Number(v);
  return (
    <span className={n === null ? "text-muted" : n < 0 ? "text-bad" : ""}>{formatPercentValue(v)}</span>
  );
}

export default async function FundsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const category = one(sp.category) ?? "";
  const shariah = one(sp.shariah) ?? "";
  const q = (one(sp.q) ?? "").slice(0, 80);
  const sortRaw = one(sp.sort) ?? "ret_365d";
  const sort = SORTS.has(sortRaw) ? sortRaw : "ret_365d";
  const order = one(sp.order) === "asc" ? "asc" : "desc";

  let data: FundsResponse;
  let categories: FundCategory[];
  try {
    [data, categories] = await Promise.all([
      apiGet<FundsResponse>("/funds", {
        category: category || undefined,
        shariah: shariah || undefined,
        q: q || undefined,
        sort,
        order,
      }),
      apiGet<FundCategory[]>("/funds/categories"),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Unexpected error."} />;
  }

  const sortHref = (key: string) => {
    const p = new URLSearchParams();
    if (category) p.set("category", category);
    if (shariah) p.set("shariah", shariah);
    if (q) p.set("q", q);
    p.set("sort", key);
    p.set("order", sort === key && order === "desc" ? "asc" : "desc");
    return `/funds?${p}`;
  };
  const arrow = (key: string) => (sort === key ? (order === "desc" ? " ↓" : " ↑") : "");
  const ariaSort = (key: string) => (sort === key ? (order === "desc" ? "descending" : "ascending") : "none");
  const basis = categories.find((c) => c.category === category)?.return_basis;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            Mutual funds {data.meta.data_mode === "demo" && <DemoBadge />}
          </h1>
          <p className="mt-1 text-sm text-ink-2">{data.meta.source}</p>
        </div>
        <AsOf date={data.meta.as_of} />
      </div>

      {data.meta.data_mode === "demo" && (
        <Notice title="You're looking at demo data">
          {data.meta.notes.map((n) => (
            <p key={n}>{n}</p>
          ))}
        </Notice>
      )}

      <form method="get" action="/funds" className="grid gap-3 rounded-xl border border-line bg-surface p-4 sm:grid-cols-4">
        <label className="flex flex-col gap-1 text-sm sm:col-span-2">
          <span className="font-medium">Search</span>
          <input
            name="q"
            defaultValue={q}
            placeholder="Fund or AMC name"
            className="rounded-lg border border-line bg-surface px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Category</span>
          <select name="category" defaultValue={category} className="rounded-lg border border-line bg-surface px-3 py-2">
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.category} value={c.category}>
                {c.category} ({c.count})
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Shariah</span>
          <select name="shariah" defaultValue={shariah} className="rounded-lg border border-line bg-surface px-3 py-2">
            <option value="">All funds</option>
            <option value="true">Shariah-compliant</option>
            <option value="false">Conventional</option>
          </select>
        </label>
        <input type="hidden" name="sort" value={sort} />
        <input type="hidden" name="order" value={order} />
        <div className="flex gap-2 sm:col-span-4">
          <button type="submit" className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-ink">
            Apply
          </button>
          <Link href="/funds" className="rounded-lg px-4 py-2 text-sm text-ink-2 hover:text-ink">
            Reset
          </Link>
        </div>
      </form>

      <p className="text-xs text-muted">
        {data.total} funds. Returns are MUFAP&apos;s published figures: money market and income funds are{" "}
        <strong>annualized</strong>; equity and most others are <strong>absolute</strong> (not annualized), so compare
        within a category.
        {basis && ` This category's returns are ${basis}.`}
      </p>

      {data.funds.length === 0 ? (
        <EmptyState title="No funds match these filters">Try another category or clear the search.</EmptyState>
      ) : (
        <>
          {/* Phones: cards */}
          <ul className="space-y-2 md:hidden">
            {data.funds.map((f) => (
              <li key={f.symbol}>
                <Link href={`/funds/${f.symbol}`} className="block rounded-xl border border-line bg-surface p-3">
                  <p className="font-medium">{f.name}</p>
                  <p className="text-xs text-ink-2">
                    {f.category}
                    {f.is_shariah && " · Shariah"} · NAV {formatNumber(f.nav, 4)}
                  </p>
                  <dl className="mt-2 grid grid-cols-4 gap-1 text-xs tabular">
                    {COLUMNS.map((c) => (
                      <div key={c.key}>
                        <dt className="text-muted">{c.label}</dt>
                        <dd>
                          <ReturnCell fund={f} k={c.key} />
                        </dd>
                      </div>
                    ))}
                  </dl>
                </Link>
              </li>
            ))}
          </ul>

          {/* Wider screens: sortable table */}
          <div className="hidden overflow-x-auto rounded-xl border border-line bg-surface md:block">
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-left text-xs text-ink-2">
                <tr>
                  <th scope="col" aria-sort={ariaSort("name")} className="px-3 py-2">
                    <Link href={sortHref("name")}>Fund{arrow("name")}</Link>
                  </th>
                  <th scope="col" aria-sort={ariaSort("category")} className="px-3 py-2">
                    <Link href={sortHref("category")}>Category{arrow("category")}</Link>
                  </th>
                  <th scope="col" aria-sort={ariaSort("nav")} className="px-3 py-2 text-right">
                    <Link href={sortHref("nav")}>NAV{arrow("nav")}</Link>
                  </th>
                  {COLUMNS.map((c) => (
                    <th key={c.key} scope="col" aria-sort={ariaSort(c.key)} className="px-3 py-2 text-right">
                      <Link href={sortHref(c.key)}>
                        {c.label}
                        {arrow(c.key)}
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="tabular">
                {data.funds.map((f) => (
                  <tr key={f.symbol} className="border-t border-line hover:bg-surface-2">
                    <td className="px-3 py-2">
                      <Link href={`/funds/${f.symbol}`} className="font-medium hover:underline">
                        {f.name}
                      </Link>
                      {f.rating && <span className="ml-2 text-xs text-muted">{f.rating}</span>}
                    </td>
                    <td className="px-3 py-2 text-ink-2">
                      {f.category}
                      {f.return_basis === "annualized" && <span className="ml-1 text-xs text-muted">(ann.)</span>}
                    </td>
                    <td className="px-3 py-2 text-right">{formatNumber(f.nav, 4)}</td>
                    {COLUMNS.map((c) => (
                      <td key={c.key} className="px-3 py-2 text-right">
                        <ReturnCell fund={f} k={c.key} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

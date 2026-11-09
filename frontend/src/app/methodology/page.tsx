import type { Metadata } from "next";

import { Card, ErrorState } from "@/components/ui";
import { ApiError, apiGet, type AppConfig, type Freshness, type MacroSeries, type TaxRule } from "@/lib/api";
import { formatDate, formatFractionPct } from "@/lib/format";

export const metadata: Metadata = { title: "Methodology" };

const SOURCES = [
  {
    key: "sbp",
    name: "SBP EasyData",
    what: "CPI inflation, policy rate, T-bill cut-off yields, KIBOR, average deposit rates",
    url: "https://easydata.sbp.org.pk/",
  },
  {
    key: "frankfurter",
    name: "Frankfurter (State Bank of Pakistan rates)",
    what: "USD/PKR exchange rate (SBP's daily average; published monthly)",
    url: "https://frankfurter.dev/",
  },
  {
    key: "psx",
    name: "PSX via psxdata (unofficial)",
    what: "KSE-100, KMI-30 and selected PSX stocks, daily",
    url: "https://github.com/mtauha/psxdata",
  },
  {
    key: "mufap",
    name: "MUFAP Performance Summary",
    what: "Mutual fund NAVs and trailing returns",
    url: "https://www.mufap.com.pk/Industry/IndustryStatDaily?tab=1",
  },
  { key: "gold", name: "Manually maintained CSV", what: "Gold, PKR per tola (24k)", url: null },
  { key: "tax_rules", name: "Versioned tax-rules file", what: "Tax assumptions (see below)", url: null },
];

const ASSET_LABEL: Record<string, string> = {
  bank_savings: "Bank savings",
  tbill: "T-bills",
  mutual_fund: "Mutual funds",
  stock: "Stocks / index",
  gold: "Gold",
  usd: "US dollars",
};

export default async function MethodologyPage() {
  let freshness: Freshness, rules: TaxRule[], config: AppConfig, macro: MacroSeries[];
  try {
    [freshness, rules, config, macro] = await Promise.all([
      apiGet<Freshness>("/freshness", {}, 60),
      apiGet<TaxRule[]>("/tax-rules"),
      apiGet<AppConfig>("/config"),
      apiGet<MacroSeries[]>("/macro"),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Unexpected error."} />;
  }
  const bySource = new Map(freshness.sources.map((s) => [s.source, s]));
  const unverified = rules.filter((r) => !r.verified || r.rate === null).length;

  return (
    <article className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Methodology</h1>
        <p className="mt-1 text-ink-2">Where the numbers come from, how they&apos;re calculated, and what they leave out.</p>
      </header>

      <section aria-labelledby="calc" className="space-y-3">
        <h2 id="calc" className="text-lg font-semibold">
          How returns are calculated
        </h2>
        <Card className="space-y-3 text-sm leading-relaxed">
          <p>
            All money math runs on the server with exact decimal arithmetic (never floating point). Returns cover the
            period you choose, ending today.
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Total return</strong> = end value ÷ start value − 1. <strong>Per year (CAGR)</strong> = (1 + total
              return)<sup>365 ÷ days</sup> − 1.
            </li>
            <li>
              <strong>Real return</strong> (after inflation) uses the exact Fisher equation: (1 + nominal) ÷ (1 +
              inflation) − 1, not the shortcut &ldquo;nominal minus inflation&rdquo;.
            </li>
            <li>
              <strong>Inflation</strong> is a price index we build by chaining SBP&apos;s month-on-month national CPI.
              It runs from the CPI month at or before your start date to the latest month published.
            </li>
            <li>
              <strong>Bank savings:</strong> profit credited monthly at the rate in force, then reinvested. By default
              that rate is SBP&apos;s average deposit rate ({config.savings_benchmark_series}). It includes
              zero-profit current accounts, so it understates a typical savings account. Enter your bank&apos;s rate for
              a better estimate.
            </li>
            <li>
              <strong>T-bills:</strong> bought at the latest SBP auction cut-off yield and rolled over at each maturity
              (actual/365 day count).
            </li>
            <li>
              <strong>KSE-100 / KMI-30, US dollars, gold:</strong> bought at the start, valued at the end. Index levels
              don&apos;t include dividends.
            </li>
            <li>
              <strong>Mutual funds:</strong> the median of each category&apos;s trailing 1, 2 or 3-year return as
              published by MUFAP, so fund comparisons are available for 1 to 3 years only. MUFAP quotes money market and
              income funds as annualized returns, and equity funds as absolute (not annualized) returns.
            </li>
            <li>
              <strong>Shariah-compliant mode</strong> leaves out interest-bearing savings accounts and T-bills, uses the
              KMI-30 instead of the KSE-100, and uses Shariah-compliant fund categories.
            </li>
          </ul>
        </Card>
      </section>

      <section aria-labelledby="tax-title" id="tax" className="space-y-3">
        <h2 id="tax-title" className="text-lg font-semibold">
          Tax assumptions
        </h2>
        <Card className="space-y-3 text-sm">
          <p>
            Tax rates are configuration, not code: each rule has an asset class, tax type, filer status, rate, effective
            date and source. We show after-tax figures <strong>only</strong> when a rule&apos;s rate has been verified
            against a cited FBR source. Savings accounts and T-bills have tax withheld on each profit credit; for other
            assets, tax is taken from the gain at the end, and losses aren&apos;t refunded.
          </p>
          {unverified > 0 && (
            <p className="rounded-lg bg-warn-bg px-3 py-2 text-warn-ink">
              {unverified} of {rules.length} tax rules are not yet verified, so after-tax figures aren&apos;t shown for
              those assets.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-ink-2">
                <tr>
                  <th className="py-1 pr-3">Asset</th>
                  <th className="py-1 pr-3">Tax</th>
                  <th className="py-1 pr-3">Filer status</th>
                  <th className="py-1 pr-3">Rate</th>
                  <th className="py-1 pr-3">From</th>
                  <th className="py-1">Status</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={`${r.asset_class}-${r.tax_type}-${r.filer_status}-${r.effective_from}`} className="border-t border-line">
                    <td className="py-1.5 pr-3">{ASSET_LABEL[r.asset_class] ?? r.asset_class}</td>
                    <td className="py-1.5 pr-3">{r.tax_type.replace(/_/g, " ")}</td>
                    <td className="py-1.5 pr-3">{r.filer_status.replace("_", "-")}</td>
                    <td className="py-1.5 pr-3 tabular">{r.rate ? formatFractionPct(r.rate, 1) : "—"}</td>
                    <td className="py-1.5 pr-3">{formatDate(r.effective_from)}</td>
                    <td className="py-1.5">
                      {r.verified && r.rate ? (
                        r.source_url ? (
                          <a href={r.source_url} className="text-good underline underline-offset-2">
                            ✓ Verified
                          </a>
                        ) : (
                          <span className="text-good">✓ Verified</span>
                        )
                      ) : (
                        <span className="text-muted">Not verified</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      <section aria-labelledby="sources" className="space-y-3">
        <h2 id="sources" className="text-lg font-semibold">
          Data sources &amp; last updated
        </h2>
        <ul className="grid gap-3 md:grid-cols-2">
          {SOURCES.map((s) => {
            const f = bySource.get(s.key);
            const hidden =
              (s.key === "mufap" && config.funds_data_mode === "demo") ||
              (s.key === "psx" && config.stocks_data_mode === "demo");
            return (
              <li key={s.key}>
                <Card className="h-full text-sm">
                  <p className="font-medium">
                    {s.url ? (
                      <a href={s.url} className="underline underline-offset-2" rel="noopener noreferrer">
                        {s.name}
                      </a>
                    ) : (
                      s.name
                    )}
                  </p>
                  <p className="text-ink-2">{s.what}</p>
                  <p className="mt-2 text-xs text-muted">
                    {hidden
                      ? "Not shown on this site: demo data is used instead."
                      : f?.last_success_at
                        ? `Last updated ${formatDate(f.last_success_at)}`
                        : "Not loaded yet"}
                    {f && f.last_status === "failed" && !hidden && " · latest refresh failed, showing last good data"}
                  </p>
                </Card>
              </li>
            );
          })}
        </ul>
        <details className="text-sm">
          <summary className="cursor-pointer text-ink-2">Economic series and their latest dates</summary>
          <ul className="mt-2 space-y-1">
            {macro.map((m) => (
              <li key={m.code} className="flex justify-between gap-3 border-b border-line py-1">
                <span>{m.name}</span>
                <span className="whitespace-nowrap text-muted">to {formatDate(m.last_date)}</span>
              </li>
            ))}
          </ul>
        </details>
      </section>

      <section aria-labelledby="limits" className="space-y-3">
        <h2 id="limits" className="text-lg font-semibold">
          Known limitations
        </h2>
        <Card className="text-sm">
          <ul className="list-disc space-y-1.5 pl-5">
            <li>Past returns don&apos;t predict future returns.</li>
            <li>Fees, sales loads, bank charges, Zakat deduction and exchange-rate spreads aren&apos;t included.</li>
            <li>Index returns ignore dividends, and you can&apos;t buy an index directly.</li>
            <li>
              Mutual fund figures come from MUFAP&apos;s trailing returns, so the chart line between start and end is
              illustrative.
            </li>
            <li>SBP publishes exchange rates monthly, so the latest USD figures can lag by a few weeks.</li>
            <li>Gold prices are entered by hand and may be missing or out of date.</li>
            <li>
              PSX data is retrieved by an unofficial library. PSX&apos;s terms restrict automated retrieval and public
              display without written permission, so this data may be removed.
            </li>
          </ul>
        </Card>
      </section>

      <section aria-labelledby="disclaimer" className="space-y-2">
        <h2 id="disclaimer" className="text-lg font-semibold">
          Disclaimer
        </h2>
        <p className="text-sm text-ink-2">
          BachatCheck is an educational project, not investment, tax or financial advice. Data may be delayed,
          incomplete or inaccurate. Check with a licensed adviser and the original sources before making decisions.
        </p>
      </section>
    </article>
  );
}

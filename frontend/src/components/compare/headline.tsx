import type { CompareResponse } from "@/lib/api";
import { formatDate, formatFractionPct, formatPKR } from "@/lib/format";

export function Headline({ data }: { data: CompareResponse }) {
  const h = data.headline;
  const byKey = new Map(data.assets.map((a) => [a.key, a]));
  const best = h.best_real ? byKey.get(h.best_real) : undefined;
  const compared = h.beat_inflation.length + h.lost_to_inflation.length;

  if (h.inflation === null || h.amount_needed_to_keep_up === null) {
    return (
      <section aria-labelledby="headline" className="rounded-xl bg-surface p-5 ring-1 ring-line">
        <h2 id="headline" className="text-lg font-semibold">
          Inflation data isn&apos;t available for this period yet.
        </h2>
        <p className="mt-1 text-sm text-ink-2">Real (after-inflation) returns can&apos;t be shown.</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="headline" className="rounded-xl bg-surface p-5 ring-1 ring-line">
      <p className="text-sm text-ink-2">Your money vs inflation</p>
      <h2 id="headline" className="mt-1 text-2xl font-semibold leading-snug sm:text-3xl">
        {formatPKR(h.amount)} in {formatDate(data.start)} needs{" "}
        <span className="text-brand">{formatPKR(h.amount_needed_to_keep_up)}</span> today to buy the same things.
      </h2>
      <p className="mt-2 text-sm text-ink-2">
        Prices rose {formatFractionPct(h.inflation)} over {data.years} {data.years === 1 ? "year" : "years"}
        {h.inflation_cagr && <> ({formatFractionPct(h.inflation_cagr)} a year)</>}. CPI data to{" "}
        {formatDate(data.cpi_as_of)}.
      </p>
      {compared > 0 && (
        <p className="mt-3 text-sm">
          <strong>
            {h.beat_inflation.length} of {compared}
          </strong>{" "}
          options beat inflation
          {best && (
            <>
              {" "}
              — best was <strong>{best.label}</strong>
            </>
          )}
          .
        </p>
      )}
    </section>
  );
}

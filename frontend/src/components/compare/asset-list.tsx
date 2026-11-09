import type { CompareAsset } from "@/lib/api";
import { formatDate, formatFractionPct, formatPKR, formatSignedPct, isPositive } from "@/lib/format";
import { seriesColor } from "@/lib/series";
import { DemoBadge } from "@/components/ui";

function RealBadge({ value }: { value: string | null }) {
  const pos = isPositive(value);
  if (pos === null) return <span className="text-sm text-muted">—</span>;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-sm font-semibold tabular ${
        pos ? "bg-good/10 text-good" : "bg-bad/10 text-bad"
      }`}
    >
      <span aria-hidden>{pos ? "▲" : "▼"}</span>
      {formatSignedPct(value)}
      <span className="sr-only">{pos ? " — beat inflation" : " — lost to inflation"}</span>
    </span>
  );
}

function TaxLine({ asset }: { asset: CompareAsset }) {
  if (!asset.tax || asset.tax.status === "not_applicable") return null;
  if (asset.tax.status === "unverified") {
    return (
      <p className="text-xs text-muted">
        After tax: not shown — tax rate not yet verified (
        <a href="/methodology#tax" className="underline underline-offset-2">
          why
        </a>
        )
      </p>
    );
  }
  return (
    <p className="text-xs text-ink-2">
      After tax ({formatFractionPct(asset.tax.rate, 0)}): {formatPKR(asset.post_tax_end_value)} · real{" "}
      {formatSignedPct(asset.post_tax_real_return)}
    </p>
  );
}

export function AssetCard({ asset }: { asset: CompareAsset }) {
  return (
    <li className="rounded-xl border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-start gap-2 font-medium">
            <span
              aria-hidden
              className="mt-1.5 inline-block size-2.5 shrink-0 rounded-full"
              style={{ background: seriesColor(asset.key) }}
            />
            <span>
              {asset.label} {asset.demo && <DemoBadge />}
            </span>
          </p>
          <p className="mt-1 text-2xl font-semibold tabular">{formatPKR(asset.end_value)}</p>
          <p className="text-xs text-ink-2 tabular">
            {formatSignedPct(asset.nominal_return)} total · {formatFractionPct(asset.cagr)} a year
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted">After inflation</p>
          <RealBadge value={asset.real_return} />
          <p className="mt-1 text-xs text-ink-2 tabular">{formatPKR(asset.real_end_value)}</p>
        </div>
      </div>
      <div className="mt-3 space-y-1">
        <TaxLine asset={asset} />
        <p className="text-xs text-muted">Data as of {formatDate(asset.data_as_of)}</p>
        {asset.notes.length > 0 && (
          <details className="text-xs text-ink-2">
            <summary className="cursor-pointer">How this is calculated</summary>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {asset.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </li>
  );
}

export function AssetList({ assets }: { assets: CompareAsset[] }) {
  const available = assets
    .filter((a) => a.available)
    .sort((a, b) => Number(b.real_return ?? -Infinity) - Number(a.real_return ?? -Infinity));
  const missing = assets.filter((a) => !a.available);
  return (
    <section aria-labelledby="results" className="space-y-4">
      <h2 id="results" className="text-lg font-semibold">
        Results, best real return first
      </h2>
      <ul className="grid gap-3 md:grid-cols-2">
        {available.map((a) => (
          <AssetCard key={a.key} asset={a} />
        ))}
      </ul>
      {missing.length > 0 && (
        <div className="rounded-xl border border-dashed border-line p-4">
          <h3 className="text-sm font-medium">Not included</h3>
          <ul className="mt-2 space-y-1 text-sm text-ink-2">
            {missing.map((a) => (
              <li key={a.key}>
                <span className="font-medium text-ink">{a.label}:</span> {a.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

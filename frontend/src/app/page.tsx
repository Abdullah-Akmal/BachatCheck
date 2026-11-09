import { Suspense } from "react";

import { AssetList } from "@/components/compare/asset-list";
import { CompareForm } from "@/components/compare/compare-form";
import { GrowthChart } from "@/components/compare/growth-chart";
import { Headline } from "@/components/compare/headline";
import { DemoBadge, ErrorState, Notice, Skeleton } from "@/components/ui";
import { ApiError, apiGet, type CompareParams, type CompareResponse } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { compareQuery, parseCompareParams } from "@/lib/params";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

async function Results({ params }: { params: CompareParams }) {
  let data: CompareResponse;
  try {
    data = await apiGet<CompareResponse>("/compare", { ...params }, 300);
  } catch (e) {
    return <ErrorState message={e instanceof ApiError ? e.message : "Unexpected error."} />;
  }
  const demo = data.assets.some((a) => a.demo);
  return (
    <div className="space-y-6">
      <Headline data={data} />
      {demo && (
        <Notice title="Mutual fund figures are demo data">
          <p>
            Fund numbers on this site are illustrative, not real MUFAP data. <DemoBadge />
          </p>
        </Notice>
      )}
      <GrowthChart data={data} />
      <AssetList assets={data.assets} />
      <p className="text-xs text-muted">
        {formatDate(data.start)} to {formatDate(data.end)} · {data.shariah_only ? "Shariah-compliant only · " : ""}
        {data.filer_status === "filer" ? "Filer" : "Non-filer"}. {data.disclaimer}
      </p>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading results">
      <Skeleton className="h-36" />
      <Skeleton className="h-96" />
      <div className="grid gap-3 md:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-36" />
        ))}
      </div>
    </div>
  );
}

export default async function ComparePage({ searchParams }: Props) {
  const params = parseCompareParams(await searchParams);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Where should my savings go?</h1>
        <p className="mt-1 text-ink-2">
          See how your money would have grown in each option — and what&apos;s left after inflation.
        </p>
      </div>
      <div className="rounded-xl border border-line bg-surface p-4">
        <CompareForm initial={params} />
      </div>
      <Suspense key={compareQuery(params)} fallback={<ResultsSkeleton />}>
        <Results params={params} />
      </Suspense>
    </div>
  );
}

import { apiGet, type AppConfig } from "@/lib/api";

/** Site-wide warning while the database holds synthetic `ingestion seed` data. */
export async function SyntheticBanner() {
  let config: AppConfig;
  try {
    config = await apiGet<AppConfig>("/config", {}, 60);
  } catch {
    return null; // pages show their own error state
  }
  if (!config.synthetic_data) return null;
  return (
    <div role="note" className="bg-warn-bg px-4 py-2 text-center text-sm text-warn-ink">
      <strong>Synthetic demo data.</strong> Prices, rates and inflation on this instance are made up for
      demonstration — they are not real.
    </div>
  );
}

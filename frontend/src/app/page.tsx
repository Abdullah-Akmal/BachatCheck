import { getHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await getHealth();

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-bold">Where should my savings go?</h1>
      <p className="opacity-80">
        Compare bank savings, mutual funds, T-bills, the KSE-100, USD and gold,
        with your real return after inflation and tax. Coming soon.
      </p>

      <div className="rounded-lg border border-black/10 p-4 text-sm dark:border-white/10">
        <p className="font-medium">System status</p>
        {health ? (
          <ul className="mt-2 space-y-1">
            <li>API: {health.status} (v{health.version})</li>
            <li>Database: {health.database}</li>
          </ul>
        ) : (
          <p className="mt-2 text-red-600 dark:text-red-400">
            API unreachable. Is the backend running on port 8000?
          </p>
        )}
      </div>
    </section>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import type { CompareParams } from "@/lib/api";
import { MAX_AMOUNT, YEAR_OPTIONS, compareQuery } from "@/lib/params";

const grouped = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function CompareForm({ initial }: { initial: CompareParams }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [amountText, setAmountText] = useState(grouped.format(initial.amount));
  const [years, setYears] = useState(initial.years);
  const [shariah, setShariah] = useState(initial.shariah);
  const [filer, setFiler] = useState(initial.filer_status);
  const [rateText, setRateText] = useState(initial.savings_rate?.toString() ?? "");
  const [error, setError] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const amount = Number(amountText.replace(/[^\d.]/g, ""));
    if (!Number.isFinite(amount) || amount <= 0 || amount > MAX_AMOUNT) {
      setError("Enter an amount between Rs 1 and Rs 100 billion.");
      return;
    }
    const rate = rateText.trim() === "" ? undefined : Number(rateText);
    if (rate !== undefined && (!Number.isFinite(rate) || rate < 0 || rate > 50)) {
      setError("Your savings rate should be between 0% and 50%.");
      return;
    }
    setError(null);
    const params: CompareParams = {
      amount: Math.round(amount),
      years,
      shariah,
      filer_status: filer,
      savings_rate: rate,
    };
    startTransition(() => router.push(`/?${compareQuery(params)}`, { scroll: false }));
  }

  return (
    <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" aria-label="Compare savings options">
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Amount (PKR)</span>
        <div className="flex items-center rounded-lg border border-line bg-surface focus-within:ring-2 focus-within:ring-brand">
          <span className="pl-3 text-ink-2">Rs</span>
          <input
            name="amount"
            inputMode="numeric"
            autoComplete="off"
            value={amountText}
            onChange={(e) => {
              const digits = e.target.value.replace(/[^\d]/g, "");
              setAmountText(digits ? grouped.format(Number(digits)) : "");
            }}
            className="w-full bg-transparent px-2 py-2.5 text-base outline-none tabular"
          />
        </div>
      </label>

      <fieldset className="flex flex-col gap-1 text-sm">
        <legend className="mb-1 font-medium">Over the last</legend>
        <div className="flex gap-1" role="radiogroup">
          {YEAR_OPTIONS.map((y) => (
            <button
              key={y}
              type="button"
              role="radio"
              aria-checked={years === y}
              onClick={() => setYears(y)}
              className={`flex-1 rounded-lg border px-2 py-2.5 ${
                years === y ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface text-ink-2"
              }`}
            >
              {y}y
            </button>
          ))}
        </div>
      </fieldset>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          name="shariah"
          checked={shariah}
          onChange={(e) => setShariah(e.target.checked)}
          className="size-4 accent-[var(--brand)]"
        />
        <span>Shariah-compliant options only</span>
      </label>

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Tax status</span>
        <select
          name="filer_status"
          value={filer}
          onChange={(e) => setFiler(e.target.value as CompareParams["filer_status"])}
          className="rounded-lg border border-line bg-surface px-3 py-2.5"
        >
          <option value="filer">Filer (on the Active Taxpayer List)</option>
          <option value="non_filer">Non-filer</option>
        </select>
      </label>

      <details className="text-sm sm:col-span-2" open={rateText !== ""}>
        <summary className="cursor-pointer text-ink-2">Know your bank&apos;s savings rate?</summary>
        <label className="mt-2 flex max-w-xs flex-col gap-1">
          <span>Annual profit rate (%)</span>
          <input
            name="savings_rate"
            inputMode="decimal"
            placeholder="e.g. 10.5"
            value={rateText}
            onChange={(e) => setRateText(e.target.value)}
            className="rounded-lg border border-line bg-surface px-3 py-2.5 tabular"
          />
          <span className="text-xs text-muted">Leave blank to use SBP&apos;s average deposit rate.</span>
        </label>
      </details>

      {error && (
        <p role="alert" className="text-sm text-bad sm:col-span-2">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="rounded-lg bg-brand px-4 py-3 font-medium text-brand-ink disabled:opacity-60 sm:col-span-2 sm:justify-self-start"
      >
        {pending ? "Calculating…" : "Compare"}
      </button>
    </form>
  );
}

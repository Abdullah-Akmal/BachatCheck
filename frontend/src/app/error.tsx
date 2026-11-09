"use client";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div role="alert" className="py-16 text-center">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="mt-2 text-ink-2">Please try again. If it keeps happening, the data service may be down.</p>
      <button onClick={reset} className="mt-4 rounded-lg bg-brand px-4 py-2 font-medium text-brand-ink">
        Try again
      </button>
    </div>
  );
}

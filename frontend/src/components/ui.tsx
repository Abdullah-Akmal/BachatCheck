/** Small shared UI pieces: as-of stamps, badges, notices and states. */

import { formatDate } from "@/lib/format";

export function AsOf({ date, label = "Data as of" }: { date: string | null | undefined; label?: string }) {
  return (
    <p className="text-xs text-muted">
      {label} <time dateTime={date ?? undefined}>{formatDate(date)}</time>
    </p>
  );
}

export function DemoBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-warn-bg px-2 py-0.5 text-xs font-medium text-warn-ink">
      Demo data
    </span>
  );
}

export function Notice({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div role="note" className="rounded-lg bg-warn-bg px-4 py-3 text-sm text-warn-ink">
      {title && <p className="font-medium">{title}</p>}
      <div className={title ? "mt-1" : undefined}>{children}</div>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-line bg-surface px-4 py-6 text-center">
      <p className="font-medium">Couldn&apos;t load the data</p>
      <p className="mt-1 text-sm text-ink-2">{message}</p>
      {/* A plain link re-requests the page server-side, which is what a retry needs. */}
      <a href="" className="mt-3 inline-block rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-ink">
        Try again
      </a>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line px-4 py-8 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-surface-2 ${className}`} />;
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-line bg-surface p-4 ${className}`}>{children}</div>;
}

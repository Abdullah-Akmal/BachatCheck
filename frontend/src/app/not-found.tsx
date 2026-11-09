import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-bold">Not found</h1>
      <p className="mt-2 text-ink-2">We couldn&apos;t find that page, fund or symbol.</p>
      <Link href="/" className="mt-4 inline-block rounded-lg bg-brand px-4 py-2 font-medium text-brand-ink">
        Back to Compare
      </Link>
    </div>
  );
}

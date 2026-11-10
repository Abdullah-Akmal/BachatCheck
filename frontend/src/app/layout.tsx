import type { Metadata, Viewport } from "next";
import Link from "next/link";

import { Nav } from "@/components/nav";
import { SyntheticBanner } from "@/components/synthetic-banner";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "BachatCheck — Where should my savings go?", template: "%s · BachatCheck" },
  description:
    "Compare Pakistani savings options — bank savings, T-bills, mutual funds, KSE-100, USD and gold — by real return after inflation and tax.",
};

// Let server rendering wait out the API host's ~1 minute cold start (Vercel function limit).
export const maxDuration = 60;

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="flex min-h-dvh flex-col antialiased">
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Bachat<span className="text-brand">Check</span>
            </Link>
            <Nav />
          </div>
        </header>
        <SyntheticBanner />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">{children}</main>
        <footer className="border-t border-line bg-surface px-4 py-4 text-center text-xs text-ink-2">
          For education only. Not investment advice. Data may be delayed or inaccurate.{" "}
          <Link href="/methodology" className="underline underline-offset-2">
            How we calculate
          </Link>
        </footer>
      </body>
    </html>
  );
}

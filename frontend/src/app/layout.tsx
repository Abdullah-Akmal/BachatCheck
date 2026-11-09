import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BachatCheck — Where should my savings go?",
  description:
    "Compare Pakistani savings options by real return after inflation and tax.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="flex min-h-dvh flex-col antialiased">
        <header className="border-b border-black/10 px-4 py-3 dark:border-white/10">
          <span className="text-lg font-semibold">BachatCheck</span>
        </header>
        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
          {children}
        </main>
        <footer className="border-t border-black/10 px-4 py-4 text-center text-xs opacity-70 dark:border-white/10">
          For education only. Not investment advice. Data may be delayed or
          inaccurate.
        </footer>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { IndexStatusBar } from "@/components/IndexStatusBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Build Radar",
  description:
    "Find open-source projects, techniques, and workflows to remix into what you're building.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-slate-950 text-slate-100 antialiased">
        <header className="border-b border-slate-800 bg-slate-900/80">
          <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-4 text-sm">
            <Link href="/" className="text-lg font-bold text-sky-400">
              Build Radar
            </Link>
            <Link href="/search" className="text-slate-300 hover:text-white">
              Search
            </Link>
          </nav>
        </header>
        <IndexStatusBar />
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}

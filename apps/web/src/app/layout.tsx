import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Build Radar",
  description:
    "Describe what you're building and see the landscape of projects, techniques, and tools you can remix.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`h-full ${sans.variable}`}>
      <body className="min-h-full font-sans">
        <Link
          href="/"
          className="fixed left-5 top-5 z-50 text-[13px] font-medium tracking-tight text-[var(--muted)] transition-colors hover:text-[var(--ink)]"
        >
          Build Radar
        </Link>
        {children}
      </body>
    </html>
  );
}

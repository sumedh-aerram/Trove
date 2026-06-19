"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { LandscapeGraph } from "@/components/LandscapeGraph";
import { PaintingBackdrop } from "@/components/PaintingBackdrop";
import { ResultPanel } from "@/components/ResultPanel";
import { searchArtifacts } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

export function LandscapeView({ initialQuery }: { initialQuery: string }) {
  const router = useRouter();
  const [input, setInput] = useState(initialQuery);
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(initialQuery));
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    setInput(initialQuery);
    if (!initialQuery) {
      setData(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSelectedId(null);
    searchArtifacts({ q: initialQuery, limit: 18 })
      .then((d) => {
        if (cancelled) return;
        setData(d);
        // Spotlight the best match on confident queries; on weak ones, stay on the
        // overview so the suggested refinement is the first thing the user sees.
        const best = d.results.find((r) => (r.top_rank ?? 999) === 0);
        if (best && (d.query_confidence ?? 0) >= 55) setSelectedId(best.id);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Search failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialQuery]);

  const selected = useMemo(
    () => data?.results.find((r) => r.id === selectedId) || null,
    [data, selectedId],
  );

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || q === initialQuery) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  function useSuggestion(q: string) {
    setInput(q);
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  return (
    <main className="relative flex h-screen flex-col">
      <PaintingBackdrop variant="results" />
      {/* header */}
      <header className="relative z-10 flex shrink-0 items-center gap-4 px-5 pt-5 pl-32">
        <form onSubmit={submit} className="flex-1">
          <div className="flex items-center rounded-xl border border-[var(--line)] bg-[var(--panel)] px-4 transition-colors focus-within:border-white/25">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="mr-2.5 shrink-0 text-[var(--muted)]" aria-hidden>
              <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6" />
              <path d="m20 20-3.2-3.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="w-full bg-transparent py-2.5 text-sm text-[var(--ink)] outline-none placeholder:text-[var(--muted)]"
              placeholder="describe what you're building"
              aria-label="Search"
            />
          </div>
        </form>
        {data && !loading && (
          <span className="hidden shrink-0 items-center gap-2 text-xs text-[var(--muted)] sm:flex">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{
                background:
                  (data.query_confidence ?? 0) >= 70
                    ? "#9ece6a"
                    : (data.query_confidence ?? 0) >= 45
                      ? "#e0af68"
                      : "#e06c75",
              }}
            />
            {data.query_confidence ?? 0}% match confidence · {data.results.length} builds
          </span>
        )}
        {loading && <span className="shrink-0 text-xs text-[var(--muted)]">mapping…</span>}
      </header>

      {/* body */}
      <div className="relative z-10 flex min-h-0 flex-1 flex-col lg:flex-row">
        <section className="relative min-h-0 flex-1">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-[var(--muted)]">
              <span className="animate-pulse">mapping the landscape…</span>
            </div>
          )}
          {!loading && error && (
            <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-[var(--muted)]">
              {error.includes("fetch") || error.includes("Failed")
                ? "backend offline — start the API on :8000"
                : error}
            </div>
          )}
          {!loading && !error && data && data.results.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-[var(--muted)]">
              nothing indexed for this yet — try a broader phrasing
            </div>
          )}
          {!loading && !error && data && data.results.length > 0 && (
            <LandscapeGraph
              query={data.query}
              results={data.results}
              clusters={data.clusters || []}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </section>

        <aside className="min-h-0 shrink-0 overflow-y-auto border-t border-[var(--line)] bg-[var(--bg)]/75 p-5 backdrop-blur-sm lg:w-[380px] lg:border-l lg:border-t-0">
          {data && data.results.length > 0 ? (
            <ResultPanel
              artifact={selected}
              summary={data.landscape_summary || ""}
              confidence={data.query_confidence ?? 0}
              advice={data.query_advice || ""}
              suggestedQuery={data.suggested_query || ""}
              onUseSuggestion={useSuggestion}
              topResults={[...data.results]
                .sort((a, b) => (a.top_rank ?? 999) - (b.top_rank ?? 999))
                .slice(0, 4)}
              onSelect={setSelectedId}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-[var(--muted)]">
              your build landscape appears here
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

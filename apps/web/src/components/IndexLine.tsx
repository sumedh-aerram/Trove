"use client";

import { useEffect, useRef, useState } from "react";
import { getStats, type IndexStats } from "@/lib/api";

const POLL_MS = 10_000;

function relTime(iso?: string | null): string {
  if (!iso) return "just now";
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 90) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export function IndexLine() {
  const [stats, setStats] = useState<IndexStats | null>(null);
  const [down, setDown] = useState(false);
  const [added, setAdded] = useState(0);
  const prev = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const next = await getStats();
        if (cancelled) return;
        setDown(false);
        if (prev.current !== null && next.artifact_count > prev.current) {
          setAdded(next.artifact_count - prev.current);
          window.setTimeout(() => setAdded(0), 9000);
        }
        prev.current = next.artifact_count;
        setStats(next);
      } catch {
        if (!cancelled) setDown(true);
      }
    }
    tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (down) {
    return (
      <p className="mt-6 text-center text-xs text-[var(--muted)]">
        backend offline — start the API on :8000
      </p>
    );
  }
  if (!stats) return <p className="mt-6 h-4" />;

  const today = stats.added_today ?? 0;
  // "Fresh" now means a genuinely NEW build (created), not a re-crawl touch.
  const fresh = stats.crawl_in_progress
    ? "indexing now"
    : `last new ${relTime(stats.last_new_at)}`;

  return (
    <p className="mt-6 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center text-xs tracking-tight text-[var(--muted)]">
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: stats.crawl_in_progress ? "#e0af68" : "#9ece6a" }}
      />
      {stats.artifact_count.toLocaleString()} builds indexed
      {added > 0 ? (
        <span className="text-[#9ece6a]">+{added} just added</span>
      ) : today > 0 ? (
        <span>· +{today.toLocaleString()} today</span>
      ) : null}
      <span>·</span>
      <span>{fresh}</span>
    </p>
  );
}

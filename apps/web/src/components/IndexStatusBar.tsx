"use client";

import { useEffect, useRef, useState } from "react";
import { getApiUrl, getStats, type IndexStats } from "@/lib/api";

const POLL_MS = 15_000;

export function IndexStatusBar() {
  const [stats, setStats] = useState<IndexStats | null>(null);
  const [apiOk, setApiOk] = useState(true);
  const prevCount = useRef<number | null>(null);
  const [justGrew, setJustGrew] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const next = await getStats();
        if (cancelled) return;
        setApiOk(true);
        if (prevCount.current !== null && next.artifact_count > prevCount.current) {
          setJustGrew(true);
          window.setTimeout(() => setJustGrew(false), 8000);
        }
        prevCount.current = next.artifact_count;
        setStats(next);
      } catch {
        if (!cancelled) {
          setApiOk(false);
          setStats(null);
        }
      }
    }

    refresh();
    const id = window.setInterval(refresh, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!apiOk) {
    return (
      <div className="border-b border-red-900/50 bg-red-950/40 px-4 py-2 text-center text-sm text-red-300">
        API unreachable at {getApiUrl()} — start FastAPI:{" "}
        <code className="text-red-200">uvicorn app.main:app --port 8000</code>
      </div>
    );
  }

  if (!stats) return null;

  const embedPct =
    stats.artifact_count > 0
      ? Math.round((stats.embeddings_count / stats.artifact_count) * 100)
      : 0;

  const refreshing = stats.crawl_in_progress || stats.index_is_sparse;

  return (
    <div
      className={`border-b px-4 py-2 text-center text-xs ${
        justGrew
          ? "border-emerald-800/60 bg-emerald-950/40 text-emerald-300"
          : "border-slate-800 bg-slate-900/60 text-slate-500"
      }`}
    >
      <span className="text-slate-400">{stats.artifact_count} indexed artifacts</span>
      {" · "}
      <span>{embedPct}% with embeddings</span>
      {" · "}
      <span className="text-slate-400">instant search · background refresh on search (~1m)</span>
      {refreshing && (
        <>
          {" · "}
          <span className="text-amber-400/90">
            {stats.index_is_sparse ? "bootstrapping index…" : "background crawl running…"}
          </span>
        </>
      )}
      {justGrew && (
        <>
          {" · "}
          <span className="text-emerald-400">new artifacts — search again to see them</span>
        </>
      )}
      {stats.last_crawl_at && (
        <>
          {" · "}
          <span>last crawl {new Date(stats.last_crawl_at).toLocaleString()}</span>
        </>
      )}
    </div>
  );
}

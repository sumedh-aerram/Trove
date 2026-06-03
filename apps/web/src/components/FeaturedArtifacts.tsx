"use client";

import { useEffect, useState } from "react";
import { ArtifactCard } from "@/components/ArtifactCard";
import { listArtifacts } from "@/lib/api";
import type { Artifact } from "@/lib/types";

/** Client-side load so the home page never white-screens while the API warms up. */
export function FeaturedArtifacts() {
  const [items, setItems] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listArtifacts({ limit: 8 })
      .then((data) => {
        if (!cancelled) {
          setItems(data.items);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not load artifacts");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p className="text-slate-500">Loading featured artifacts…</p>;
  }
  if (error) {
    return (
      <p className="text-amber-400/90">
        API unreachable — start FastAPI on port 8000. ({error})
      </p>
    );
  }
  if (items.length === 0) {
    return (
      <p className="text-slate-500">
        Index is empty. Run <code className="text-slate-400">docker compose up -d</code> and wait
        for the crawler, or run <code className="text-slate-400">workers/bootstrap_index.py</code>.
      </p>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {items.map((a) => (
        <ArtifactCard key={a.id} artifact={a} />
      ))}
    </div>
  );
}

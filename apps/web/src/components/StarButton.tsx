"use client";

import { useState } from "react";
import { starArtifact, unstarArtifact } from "@/lib/api";

type Props = {
  artifactId: string;
  compact?: boolean;
};

export function StarButton({ artifactId, compact = false }: Props) {
  const username = "vibecoder";
  const [starred, setStarred] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    setLoading(true);
    setError(null);
    try {
      if (starred) {
        await unstarArtifact(artifactId, username);
        setStarred(false);
      } else {
        await starArtifact(artifactId, username);
        setStarred(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  if (compact) {
    return (
      <button
        type="button"
        onClick={toggle}
        disabled={loading}
        title={starred ? "Unsave" : "Save"}
        className={`rounded-md px-2 py-0.5 text-xs transition-colors ${
          starred
            ? "border border-[var(--line)] text-[var(--ink)]"
            : "border border-[var(--line)] text-[var(--muted)] hover:text-[var(--ink)]"
        }`}
      >
        {starred ? "★" : "☆"}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        disabled={loading}
        className="rounded-md border border-[var(--line)] px-3 py-1 text-sm text-[var(--muted)] transition-colors hover:text-[var(--ink)] disabled:opacity-50"
      >
        {loading ? "…" : starred ? "★ saved" : "☆ save"}
      </button>
      {error && <span className="text-xs text-[var(--muted)]">{error}</span>}
    </div>
  );
}

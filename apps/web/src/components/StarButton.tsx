"use client";

import { useState } from "react";
import { starArtifact, unstarArtifact } from "@/lib/api";

type Props = {
  artifactId: string;
  compact?: boolean;
};

export function StarButton({ artifactId, compact = false }: Props) {
  const [username, setUsername] = useState("vibecoder");
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
        title={starred ? "Unstar" : "Star"}
        className={`rounded px-2 py-0.5 text-xs ${
          starred
            ? "bg-amber-600/80 text-white"
            : "border border-slate-600 text-slate-400 hover:border-amber-600 hover:text-amber-400"
        }`}
      >
        {starred ? "★" : "☆"}
      </button>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
        placeholder="username"
      />
      <button
        type="button"
        onClick={toggle}
        disabled={loading}
        className={`rounded px-3 py-1 text-sm text-white disabled:opacity-50 ${
          starred ? "bg-slate-600 hover:bg-slate-500" : "bg-amber-600 hover:bg-amber-500"
        }`}
      >
        {loading ? "…" : starred ? "Unstar" : "Star"}
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}

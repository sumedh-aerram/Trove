"use client";

import Link from "next/link";
import type { Artifact } from "@/lib/types";

function Bar({ value }: { value: number }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-white/10">
      <div
        className="h-full rounded-full bg-[var(--ink)]/70"
        style={{ width: `${Math.max(3, Math.round(value))}%` }}
      />
    </div>
  );
}

function confColor(c: number) {
  return c >= 70 ? "#9ece6a" : c >= 45 ? "#e0af68" : "#e06c75";
}

export function ResultPanel({
  artifact,
  summary,
  confidence,
  advice,
  suggestedQuery,
  onUseSuggestion,
  topResults,
  onSelect,
}: {
  artifact: Artifact | null;
  summary: string;
  confidence: number;
  advice: string;
  suggestedQuery?: string;
  onUseSuggestion?: (q: string) => void;
  topResults: Artifact[];
  onSelect: (id: string) => void;
}) {
  // Overview (nothing selected): confidence + best matches.
  if (!artifact) {
    return (
      <div className="flex h-full flex-col gap-5 px-1">
        <div>
          <div className="mb-1.5 flex items-center justify-between text-xs text-[var(--muted)]">
            <span>match confidence</span>
            <span style={{ color: confColor(confidence) }}>{confidence}%</span>
          </div>
          <Bar value={confidence} />
          {advice && <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">{advice}</p>}
        </div>

        {suggestedQuery && onUseSuggestion && (
          <div className="rounded-xl border border-[#e0af68]/30 bg-[#e0af68]/[0.06] p-3">
            <div className="mb-1.5 text-[11px] uppercase tracking-wider text-[#e0af68]/90">
              try a sharper query
            </div>
            <p className="mb-2.5 text-sm leading-snug text-[var(--ink)]/90">{suggestedQuery}</p>
            <button
              type="button"
              onClick={() => onUseSuggestion(suggestedQuery)}
              className="rounded-lg border border-[#e0af68]/40 px-3 py-1.5 text-[13px] text-[#e0af68] transition-colors hover:bg-[#e0af68]/10"
            >
              search this →
            </button>
          </div>
        )}

        <div>
          <div className="mb-2 text-[11px] uppercase tracking-wider text-[var(--muted)]">best matches</div>
          <div className="space-y-1.5">
            {topResults.map((r, i) => (
              <button
                key={r.id}
                type="button"
                onClick={() => onSelect(r.id)}
                className="flex w-full items-center gap-3 rounded-lg border border-[var(--line)] px-3 py-2 text-left transition-colors hover:border-white/25"
              >
                <span className="text-xs tabular-nums text-[var(--muted)]">{i + 1}</span>
                <span className="flex-1 truncate text-sm text-[var(--ink)]">
                  {r.headline || r.title}
                </span>
                <span className="text-xs" style={{ color: confColor(r.relevance_pct ?? 0) }}>
                  {r.relevance_pct ?? 0}%
                </span>
              </button>
            ))}
          </div>
        </div>

        <p className="mt-auto text-xs leading-relaxed text-[var(--muted)]">
          {summary} Closer to the center means a stronger match. Tap any node to see how to start.
        </p>
      </div>
    );
  }

  const stack = Array.from(
    new Set([
      ...(artifact.frameworks || []),
      ...(artifact.tools || []),
      ...(artifact.languages || []),
    ]),
  ).slice(0, 8);
  const steps = artifact.start_steps && artifact.start_steps.length > 0
    ? artifact.start_steps
    : artifact.simple_implementation
      ? [artifact.simple_implementation]
      : [];

  return (
    <div key={artifact.id} className="br-fade-up flex h-full flex-col gap-4 px-1">
      <button
        type="button"
        onClick={() => onSelect("")}
        className="self-start text-xs text-[var(--muted)] transition-colors hover:text-[var(--ink)]"
      >
        ← all matches
      </button>

      <div>
        <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wider text-[var(--muted)]">
          <span>{artifact.source_type}</span>
          <span>·</span>
          <span>{(artifact.cluster_label || artifact.artifact_type || "").replace(/_/g, " ")}</span>
        </div>
        <h2 className="text-lg font-medium leading-snug tracking-tight text-[var(--ink)]">
          {artifact.headline || artifact.title}
        </h2>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs text-[var(--muted)]">
          <span>relevance to your query</span>
          <span style={{ color: confColor(artifact.relevance_pct ?? 0) }}>
            {artifact.relevance_pct ?? 0}% · {artifact.confidence || "match"}
          </span>
        </div>
        <Bar value={artifact.relevance_pct ?? 0} />
      </div>

      {artifact.why_relevant && (
        <p className="text-sm leading-relaxed text-[var(--ink)]/90">{artifact.why_relevant}</p>
      )}

      {artifact.about && (
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--muted)]">about</div>
          <p className="text-sm leading-relaxed text-[var(--muted)]">{artifact.about}</p>
        </div>
      )}

      {artifact.how_it_helps && (
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wider text-[var(--muted)]">
            how it helps
          </div>
          <p className="text-sm leading-relaxed text-[var(--muted)]">{artifact.how_it_helps}</p>
        </div>
      )}

      {artifact.stands_out && artifact.stands_out.length > 0 && (
        <div>
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-[var(--muted)]">
            why it stands out
          </div>
          <div className="flex flex-wrap gap-1.5">
            {artifact.stands_out.map((s, i) => (
              <span
                key={i}
                className="rounded-md border border-[var(--line)] bg-white/[0.03] px-2 py-1 text-[12px] text-[var(--ink)]/85"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {artifact.key_points && artifact.key_points.length > 0 && (
        <ul className="space-y-1.5">
          {artifact.key_points.map((p, i) => (
            <li key={i} className="flex gap-2 text-sm text-[var(--muted)]">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[var(--muted)]" />
              <span>{p}</span>
            </li>
          ))}
        </ul>
      )}

      {steps.length > 0 && (
        <div>
          <div className="mb-1.5 text-[11px] uppercase tracking-wider text-[var(--muted)]">
            how to start
          </div>
          <ol className="space-y-1 rounded-lg border border-[var(--line)] bg-black/30 px-3 py-2.5">
            {steps.map((s, i) => (
              <li key={i} className="flex gap-2 text-[12.5px] text-[var(--ink)]/90">
                <span className="select-none text-[var(--muted)]">{i + 1}.</span>
                <code className="break-all">{s}</code>
              </li>
            ))}
          </ol>
        </div>
      )}

      {artifact.use_case && (
        <p className="text-sm leading-relaxed text-[var(--muted)]">
          <span className="text-[var(--ink)]/80">For: </span>
          {artifact.use_case}
        </p>
      )}

      {stack.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {stack.map((s) => (
            <span
              key={s}
              className="rounded-md border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]"
            >
              {s}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto flex items-center gap-4 pt-2 text-sm">
        <a
          href={artifact.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-[var(--ink)] underline-offset-4 hover:underline"
        >
          open source ↗
        </a>
        <Link
          href={`/artifacts/${artifact.id}`}
          className="text-[var(--muted)] transition-colors hover:text-[var(--ink)]"
        >
          full detail
        </Link>
      </div>
    </div>
  );
}

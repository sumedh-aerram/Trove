import Link from "next/link";
import type { Artifact } from "@/lib/types";
import { ScoreBadge } from "./ScoreBadge";
import { StarButton } from "./StarButton";
import { TagPill } from "./TagPill";

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const pills = [
    ...(artifact.frameworks || []).slice(0, 3),
    ...(artifact.tools || []).slice(0, 2),
    ...(artifact.tags || []).slice(0, 3),
  ];

  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex flex-wrap gap-2 text-xs text-slate-500">
          <span className="uppercase tracking-wide">{artifact.source_type}</span>
          <span>·</span>
          <span>{artifact.artifact_type.replace(/_/g, " ")}</span>
        </div>
        <StarButton artifactId={artifact.id} compact />
      </div>
      <h3 className="text-lg font-semibold text-slate-100">
        <Link href={`/artifacts/${artifact.id}`} className="hover:text-sky-400">
          {artifact.title}
        </Link>
      </h3>
      {artifact.summary && (
        <p className="mt-2 line-clamp-2 text-sm text-slate-400">{artifact.summary}</p>
      )}
      {artifact.why_relevant && (
        <p className="mt-2 text-sm text-sky-300/90">{artifact.why_relevant}</p>
      )}
      <div className="mt-3 flex flex-wrap gap-1">{pills.map((p) => <TagPill key={p} label={p} />)}</div>
      <div className="mt-3 flex flex-wrap gap-3">
        <ScoreBadge label="Quality" value={artifact.quality_score} />
        <ScoreBadge label="Remix" value={artifact.remixability_score} />
        <ScoreBadge label="Underground" value={artifact.underground_score} />
        <ScoreBadge label="Hype risk" value={artifact.hype_risk_score} invert />
      </div>
      <div className="mt-4 flex gap-3 text-sm">
        <a
          href={artifact.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-sky-400 hover:underline"
        >
          Source
        </a>
        <Link href={`/artifacts/${artifact.id}`} className="text-slate-300 hover:text-white">
          Details →
        </Link>
      </div>
    </article>
  );
}

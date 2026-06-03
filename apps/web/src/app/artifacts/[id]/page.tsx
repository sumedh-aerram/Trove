import Link from "next/link";
import { notFound } from "next/navigation";
import { ScoreBadge } from "@/components/ScoreBadge";
import { StarButton } from "@/components/StarButton";
import { TagPill } from "@/components/TagPill";
import { getArtifact } from "@/lib/api";

export default async function ArtifactDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let artifact;
  try {
    artifact = await getArtifact(id);
  } catch {
    notFound();
  }

  const list = (label: string, items?: string[]) =>
    items && items.length > 0 ? (
      <div>
        <h3 className="text-sm font-medium text-slate-500">{label}</h3>
        <div className="mt-1 flex flex-wrap gap-1">
          {items.map((x) => (
            <TagPill key={x} label={x} />
          ))}
        </div>
      </div>
    ) : null;

  return (
    <article className="space-y-6">
      <Link href="/search" className="text-sm text-sky-400 hover:underline">
        ← Back to search
      </Link>
      <header className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">
          {artifact.source_type} · {artifact.artifact_type.replace(/_/g, " ")}
        </p>
        <h1 className="text-3xl font-bold">{artifact.title}</h1>
        <a
          href={artifact.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-sky-400 hover:underline"
        >
          Open source →
        </a>
        <StarButton artifactId={artifact.id} />
      </header>

      <div className="flex flex-wrap gap-4">
        <ScoreBadge label="Quality" value={artifact.quality_score} />
        <ScoreBadge label="Remixability" value={artifact.remixability_score} />
        <ScoreBadge label="Underground" value={artifact.underground_score} />
        <ScoreBadge label="Hype risk" value={artifact.hype_risk_score} invert />
      </div>

      {artifact.summary && (
        <section>
          <h2 className="font-semibold text-slate-200">Summary</h2>
          <p className="mt-1 text-slate-400">{artifact.summary}</p>
        </section>
      )}
      {artifact.what_it_helps_build && (
        <section>
          <h2 className="font-semibold text-slate-200">What you can build</h2>
          <p className="mt-1 text-slate-400">{artifact.what_it_helps_build}</p>
        </section>
      )}
      {artifact.technical_core && (
        <section>
          <h2 className="font-semibold text-slate-200">Technical core</h2>
          <p className="mt-1 text-slate-400">{artifact.technical_core}</p>
        </section>
      )}
      {artifact.practical_use_case && (
        <section>
          <h2 className="font-semibold text-slate-200">Who it&apos;s for</h2>
          <p className="mt-1 text-slate-400">{artifact.practical_use_case}</p>
        </section>
      )}
      {artifact.how_to_remix && (
        <section>
          <h2 className="font-semibold text-slate-200">How to remix</h2>
          <p className="mt-1 text-slate-400">{artifact.how_to_remix}</p>
        </section>
      )}

      {artifact.implementation_steps && artifact.implementation_steps.length > 0 && (
        <section>
          <h2 className="font-semibold text-slate-200">Implementation steps</h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-slate-400">
            {artifact.implementation_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </section>
      )}

      {artifact.setup_commands && artifact.setup_commands.length > 0 && (
        <section>
          <h2 className="font-semibold text-slate-200">Setup commands</h2>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-4 text-sm text-emerald-300">
            {artifact.setup_commands.join("\n")}
          </pre>
        </section>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {list("Tags", artifact.tags)}
        {list("Frameworks", artifact.frameworks)}
        {list("Tools", artifact.tools)}
        {list("Languages", artifact.languages)}
        {list("APIs", artifact.apis)}
        {list("Models", artifact.models)}
      </div>
    </article>
  );
}

import Link from "next/link";
import { notFound } from "next/navigation";
import { StarButton } from "@/components/StarButton";
import { getArtifact } from "@/lib/api";

function Pills({ label, items }: { label: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <h3 className="text-[11px] uppercase tracking-wider text-[var(--muted)]">{label}</h3>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.map((x) => (
          <span
            key={x}
            className="rounded-md border border-[var(--line)] px-2 py-0.5 text-[12px] text-[var(--muted)]"
          >
            {x}
          </span>
        ))}
      </div>
    </div>
  );
}

function Section({ title, body }: { title: string; body?: string }) {
  if (!body) return null;
  return (
    <section>
      <h2 className="text-sm font-medium text-[var(--ink)]">{title}</h2>
      <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">{body}</p>
    </section>
  );
}

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

  return (
    <main className="mx-auto max-w-2xl px-5 py-16">
      <Link href="/" className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--ink)]">
        ← back
      </Link>

      <header className="mt-6 space-y-3">
        <p className="text-[11px] uppercase tracking-wider text-[var(--muted)]">
          {artifact.source_type} · {artifact.artifact_type.replace(/_/g, " ")}
        </p>
        <h1 className="text-2xl font-medium tracking-tight text-[var(--ink)]">{artifact.title}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <a
            href={artifact.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-[var(--ink)] underline-offset-4 hover:underline"
          >
            open source ↗
          </a>
          <StarButton artifactId={artifact.id} />
        </div>
      </header>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["quality", artifact.quality_score],
          ["remix", artifact.remixability_score],
          ["underground", artifact.underground_score],
          ["hype risk", artifact.hype_risk_score],
        ].map(([label, val]) => (
          <div key={label as string} className="rounded-lg border border-[var(--line)] p-3">
            <div className="text-[11px] uppercase tracking-wider text-[var(--muted)]">{label}</div>
            <div className="mt-1 text-lg font-medium text-[var(--ink)]">{Math.round((val as number) || 0)}</div>
          </div>
        ))}
      </div>

      <div className="mt-8 space-y-6">
        <Section title="Summary" body={artifact.summary} />
        <Section title="What you can build" body={artifact.what_it_helps_build} />
        <Section title="Technical core" body={artifact.technical_core} />
        <Section title="Who it's for" body={artifact.practical_use_case} />
        <Section title="How to remix" body={artifact.how_to_remix} />

        {artifact.implementation_steps && artifact.implementation_steps.length > 0 && (
          <section>
            <h2 className="text-sm font-medium text-[var(--ink)]">Implementation steps</h2>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-[var(--muted)]">
              {artifact.implementation_steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </section>
        )}

        {artifact.setup_commands && artifact.setup_commands.length > 0 && (
          <section>
            <h2 className="text-sm font-medium text-[var(--ink)]">Setup</h2>
            <pre className="mt-2 overflow-x-auto rounded-lg border border-[var(--line)] bg-black/30 p-4 text-[12.5px] text-[var(--ink)]/90">
              {artifact.setup_commands.join("\n")}
            </pre>
          </section>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Pills label="Tags" items={artifact.tags} />
          <Pills label="Frameworks" items={artifact.frameworks} />
          <Pills label="Tools" items={artifact.tools} />
          <Pills label="Languages" items={artifact.languages} />
          <Pills label="APIs" items={artifact.apis} />
          <Pills label="Models" items={artifact.models} />
        </div>
      </div>
    </main>
  );
}

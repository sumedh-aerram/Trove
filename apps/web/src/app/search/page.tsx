import { ArtifactCard } from "@/components/ArtifactCard";
import { SearchBar } from "@/components/SearchBar";
import { searchArtifacts } from "@/lib/api";

const ARTIFACT_TYPES = [
  "open_source_project",
  "hackathon_project",
  "starter_template",
  "mcp_server",
  "coding_agent_workflow",
  "research_paper",
  "technical_technique",
];

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const q = sp.q || "";
  const artifact_type = sp.artifact_type;
  const framework = sp.framework;
  const language = sp.language;
  const tool = sp.tool;
  const source_type = sp.source_type;
  const min_quality_score = sp.min_quality_score;
  const max_hype_risk = sp.max_hype_risk;

  let results: Awaited<ReturnType<typeof searchArtifacts>>["results"] = [];
  let error: string | null = null;

  if (q) {
    try {
      const params = {
        q,
        limit: 20,
        ...(artifact_type && { artifact_type }),
        ...(framework && { framework }),
        ...(language && { language }),
        ...(tool && { tool }),
        ...(source_type && { source_type }),
        ...(min_quality_score && { min_quality_score: Number(min_quality_score) }),
        ...(max_hype_risk && { max_hype_risk: Number(max_hype_risk) }),
      };
      const data = await searchArtifacts(params);
      results = data.results;
    } catch (e) {
      error = e instanceof Error ? e.message : "Search failed";
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Search</h1>
      <SearchBar defaultValue={q} />

      <form
        method="get"
        action="/search"
        className="grid gap-3 rounded-lg border border-slate-800 bg-slate-900/40 p-4 md:grid-cols-3"
      >
        <input type="hidden" name="q" value={q} />
        <label className="text-sm">
          <span className="text-slate-500">Artifact type</span>
          <select
            name="artifact_type"
            defaultValue={artifact_type || ""}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
          >
            <option value="">Any</option>
            {ARTIFACT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-slate-500">Framework</span>
          <input
            name="framework"
            defaultValue={framework || ""}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          <span className="text-slate-500">Language</span>
          <input
            name="language"
            defaultValue={language || ""}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          <span className="text-slate-500">Tool</span>
          <input
            name="tool"
            defaultValue={tool || ""}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          <span className="text-slate-500">Source type</span>
          <select
            name="source_type"
            defaultValue={source_type || ""}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
          >
            <option value="">Any</option>
            <option value="github">github</option>
            <option value="hackernews">hackernews</option>
            <option value="arxiv">arxiv</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="text-slate-500">Min quality</span>
          <input
            name="min_quality_score"
            type="number"
            defaultValue={min_quality_score || ""}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
          />
        </label>
        <label className="text-sm">
          <span className="text-slate-500">Max hype risk</span>
          <input
            name="max_hype_risk"
            type="number"
            defaultValue={max_hype_risk || ""}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1"
          />
        </label>
        <button type="submit" className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600 md:col-span-3">
          Apply filters
        </button>
      </form>

      {error && <p className="text-red-400">{error}</p>}
      {q && !error && (
        <p className="text-sm text-slate-500">
          {results.length} result{results.length !== 1 ? "s" : ""} for &ldquo;{q}&rdquo;
        </p>
      )}
      <div className="grid gap-4">
        {results.map((a) => (
          <ArtifactCard key={a.id} artifact={a} />
        ))}
      </div>
    </div>
  );
}

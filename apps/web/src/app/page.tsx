import Link from "next/link";
import { FeaturedArtifacts } from "@/components/FeaturedArtifacts";
import { SearchBar } from "@/components/SearchBar";

const EXAMPLES = [
  "I'm building an AI lecture summarizer with quiz generation",
  "I need open-source repos for a RAG Chrome extension",
  "Find hackathon projects using Whisper and Next.js",
  "Show me MCP servers for coding agents",
];

export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="space-y-4 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-white">Build Radar</h1>
        <p className="text-lg text-slate-400">
          Find open-source projects, techniques, and workflows to remix into what you&apos;re
          building.
        </p>
        <div className="mx-auto max-w-2xl pt-2">
          <SearchBar large />
        </div>
        <div className="flex flex-wrap justify-center gap-2 pt-2">
          {EXAMPLES.map((ex) => (
            <Link
              key={ex}
              href={`/search?q=${encodeURIComponent(ex)}`}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-600 hover:text-sky-300"
            >
              {ex}
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold">Featured from index</h2>
        <FeaturedArtifacts />
      </section>
    </div>
  );
}

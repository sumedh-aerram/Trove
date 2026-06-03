"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function SearchBar({
  defaultValue = "",
  large = false,
}: {
  defaultValue?: string;
  large?: boolean;
}) {
  const router = useRouter();
  const [q, setQ] = useState(defaultValue);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <form onSubmit={onSubmit} className="flex gap-2">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Describe what you're building..."
        className={`flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none ${
          large ? "py-4 text-lg" : "py-2 text-sm"
        }`}
      />
      <button
        type="submit"
        className={`rounded-lg bg-sky-600 font-medium text-white hover:bg-sky-500 ${
          large ? "px-6 py-4" : "px-4 py-2 text-sm"
        }`}
      >
        Search
      </button>
    </form>
  );
}

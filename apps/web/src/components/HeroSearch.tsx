"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

const SUGGESTIONS = [
  "a RAG chrome extension that explains research papers",
  "an AI lecture summarizer with auto-generated quizzes",
  "an MCP server my coding agent can call for repo search",
  "a realtime computer vision app for posture detection",
  "a full-stack SaaS starter with auth, billing, and chat",
  "voice agents with low-latency speech in and out",
];

const TYPE_MS = 38;
const DELETE_MS = 18;
const HOLD_MS = 1500;

export function HeroSearch() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [typed, setTyped] = useState("");
  const [focused, setFocused] = useState(false);
  const idx = useRef(0);
  const char = useRef(0);
  const deleting = useRef(false);

  const active = focused || value.length > 0;

  useEffect(() => {
    if (active) return;
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      const phrase = SUGGESTIONS[idx.current % SUGGESTIONS.length];
      if (!deleting.current) {
        char.current += 1;
        setTyped(phrase.slice(0, char.current));
        if (char.current >= phrase.length) {
          deleting.current = true;
          timer = setTimeout(tick, HOLD_MS);
          return;
        }
        timer = setTimeout(tick, TYPE_MS);
      } else {
        char.current -= 1;
        setTyped(phrase.slice(0, char.current));
        if (char.current <= 0) {
          deleting.current = false;
          idx.current += 1;
          timer = setTimeout(tick, 280);
          return;
        }
        timer = setTimeout(tick, DELETE_MS);
      }
    };

    timer = setTimeout(tick, 400);
    return () => clearTimeout(timer);
  }, [active]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
  }

  return (
    <form onSubmit={submit} className="w-full">
      <div className="group relative flex items-center rounded-2xl border border-[var(--line)] bg-[var(--panel)] px-5 transition-colors focus-within:border-white/25">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          className="mr-3 shrink-0 text-[var(--muted)]"
          aria-hidden
        >
          <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6" />
          <path d="m20 20-3.2-3.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>

        <div className="relative flex-1 py-4">
          {!active && (
            <span className="br-caret pointer-events-none absolute inset-0 flex items-center text-[15px] text-[var(--muted)] sm:text-base">
              {typed || "what are you building?"}
            </span>
          )}
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            className="w-full bg-transparent text-[15px] text-[var(--ink)] outline-none placeholder:text-transparent sm:text-base"
            placeholder=" "
            aria-label="Describe what you're building"
          />
        </div>

        <button
          type="submit"
          className="ml-2 shrink-0 rounded-lg border border-[var(--line)] px-3 py-1.5 text-[13px] text-[var(--muted)] transition-colors hover:border-white/25 hover:text-[var(--ink)]"
        >
          map it
        </button>
      </div>
    </form>
  );
}

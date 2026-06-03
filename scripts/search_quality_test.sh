#!/usr/bin/env bash
# Assert search quality for canonical vibe-coder queries (API on :8000, seeded DB).
set -euo pipefail

API="${API_BASE_URL:-http://localhost:8000}"

python3 << 'PY'
import json
import sys
import urllib.parse
import urllib.request

API = __import__("os").environ.get("API_BASE_URL", "http://localhost:8000")

CASES = [
    {
        "name": "AI lecture summarizer",
        "q": "AI lecture summarizer",
        "must_match": ("lecture", "quiz", "summarizer", "whisper", "flashcard", "video"),
        "top_slug": None,
    },
    {
        "name": "RAG Chrome extension",
        "q": "RAG Chrome extension",
        "must_match": ("rag", "chrome", "extension", "pdf", "browser"),
        "top_slug": "paperpal",
    },
    {
        "name": "RAG Chrome full context",
        "q": (
            "I'm building a RAG Chrome extension that explains research papers. "
            "I need open-source repos, architecture ideas, and useful libraries."
        ),
        "must_match": ("rag", "extension", "paper", "chrome", "pdf", "browser"),
        "top_slug": "paperpal",
        "check_why": True,
    },
    {
        "name": "MCP server for coding agents",
        "q": "MCP server for coding agents",
        "must_match": ("mcp", "coding", "agent", "cursor", "claude"),
        "top_slug": "mcphub",
    },
    {
        "name": "computer vision posture app",
        "q": "computer vision posture app",
        "must_match": ("vision", "posture", "pose", "mediapipe", "hack-health"),
        "top_slug": "posture",
    },
]


def search(q: str, **params) -> dict:
    qs = urllib.parse.urlencode({"q": q, "limit": 8, **params})
    url = f"{API}/search?{qs}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def blob(results: list) -> str:
    parts = []
    for r in results:
        parts.extend([
            r.get("title", ""),
            r.get("summary", ""),
            r.get("why_relevant", ""),
            " ".join(r.get("tags") or []),
            " ".join(r.get("tools") or []),
        ])
    return " ".join(parts).lower()


failed = 0
for case in CASES:
    print(f"\n== {case['name']} ==")
    data = search(case["q"])
    results = data.get("results") or []
    if not results:
        print("FAIL: no results")
        failed += 1
        continue
    b = blob(results)
    if not any(m in b for m in case["must_match"]):
        print(f"FAIL: none of {case['must_match']} in results")
        print("  top:", [r.get("title") for r in results[:3]])
        failed += 1
    else:
        print("OK: matched expected themes")
        print("  top:", [r.get("title") for r in results[:3]])
        if results[0].get("why_relevant"):
            print("  why:", results[0]["why_relevant"][:120], "...")

    if case.get("top_slug"):
        tops = " ".join(r.get("title", "").lower() for r in results[:3])
        if case["top_slug"] not in tops:
            print(f"WARN: expected '{case['top_slug']}' in top 3 (got {results[:3]})")

    if case.get("check_why"):
        why = (results[0].get("why_relevant") or "").lower()
        if "extension" not in why and "rag" not in why:
            print("WARN: why_relevant may be weak:", results[0].get("why_relevant"))

print(f"\n{'=' * 40}")
if failed:
    print(f"FAILED: {failed} case(s)")
    sys.exit(1)
print("All search quality checks passed.")
PY

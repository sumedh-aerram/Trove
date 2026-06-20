"""Turn ranked search results into an explainable 'landscape' for the UI.

Groups results into themed clusters, attaches a normalized relevance, and
extracts concise, skimmable key points + a one-line use case per result.
No LLM calls: pure derivation from already-indexed fields.
"""
from __future__ import annotations

import re
from typing import Any

from .extraction_service import LANGUAGES

# Artifact types collapsed into a small set of human themes (keeps the graph readable).
_THEME_BY_TYPE: dict[str, tuple[str, str]] = {
    "starter_template": ("templates", "Starter Templates"),
    "open_source_project": ("projects", "Open-Source Projects"),
    "hackathon_project": ("projects", "Open-Source Projects"),
    "mcp_server": ("agents", "Agent & MCP Tooling"),
    "coding_agent_workflow": ("agents", "Agent & MCP Tooling"),
    "research_paper": ("research", "Techniques & Research"),
    "technical_technique": ("research", "Techniques & Research"),
    "architecture_pattern": ("research", "Techniques & Research"),
    "deployment_recipe": ("templates", "Starter Templates"),
    "api_tool": ("libraries", "Libraries & APIs"),
    "model": ("libraries", "Libraries & APIs"),
    "dataset": ("libraries", "Libraries & APIs"),
}

_THEME_ORDER = ["templates", "projects", "agents", "research", "libraries"]
_DEFAULT_THEME = ("projects", "Open-Source Projects")


def _theme_for(artifact: dict[str, Any]) -> tuple[str, str]:
    return _THEME_BY_TYPE.get(artifact.get("artifact_type", ""), _DEFAULT_THEME)


def _strip_md(text: str) -> str:
    """Remove README badge/markdown/URL cruft so prose reads cleanly."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)  # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> their text
    text = re.sub(r"https?://\S+", " ", text)  # bare URLs
    text = re.sub(r"[#>`*_~|]+", " ", text)  # md symbols
    return text


def _clip(text: str | None, limit: int, *, strip_md: bool = False) -> str:
    if not text:
        return ""
    s = str(text)
    if strip_md:
        s = _strip_md(s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^Helps you build:\s*", "", s)
    if len(s) <= limit:
        return s
    return s[: limit - 1].rsplit(" ", 1)[0] + "\u2026"


def _stack(artifact: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("frameworks", "tools", "languages"):
        for v in artifact.get(key) or []:
            if v not in out:
                out.append(v)
    return out[:6]


def _headline(artifact: dict[str, Any]) -> str:
    title = artifact.get("title") or "Untitled"
    # GitHub repos arrive as "owner/name" — show the repo name as the headline.
    if artifact.get("source_type") == "github" and "/" in title:
        return title.split("/", 1)[1]
    return _clip(title, 70)


def _simple_implementation(artifact: dict[str, Any]) -> str:
    cmds = artifact.get("setup_commands") or []
    if cmds:
        return cmds[0]
    steps = artifact.get("implementation_steps") or []
    if steps:
        return _clip(steps[0], 90)
    if artifact.get("source_type") == "github":
        return f"git clone {artifact.get('source_url', '')}"
    return ""


def _start_steps(artifact: dict[str, Any]) -> list[str]:
    """A short, concrete 'how to actually start' list (not just one line)."""
    steps: list[str] = []
    cmds = artifact.get("setup_commands") or []
    src = artifact.get("source_url") or ""

    if artifact.get("source_type") == "github" and src:
        repo = src.rstrip("/").split("/")[-1]
        steps.append(f"git clone {src}")
        if repo:
            steps.append(f"cd {repo}")

    for c in cmds[:3]:
        if c not in steps:
            steps.append(c)

    if len(steps) < 2:
        for s in (artifact.get("implementation_steps") or [])[:3]:
            steps.append(_clip(s, 90))

    if not steps:
        if artifact.get("source_type") == "arxiv":
            steps = ["Read the abstract + method section", "Check for a linked code repo", "Port the technique into your stack"]
        else:
            steps = ["Open the source", "Skim the README / usage", "Copy the part you need"]

    return steps[:4]


def _query_confidence(query: str, intent: dict[str, Any], results: list[dict[str, Any]]) -> tuple[int, str]:
    """How well-specified is the query? Low score => tell the user to refine.

    Blends: query specificity (word + signal count) with retrieval evidence
    (mean relevance of the top results). A vague 1-word query scores low even
    if something matches, so the user knows to add context.
    """
    words = [w for w in re.findall(r"[a-zA-Z0-9+.#-]+", query) if len(w) > 2]
    word_score = max(0.0, min(1.0, (len(words) - 2) / 7.0))

    signals = (
        len(intent.get("frameworks") or [])
        + len(intent.get("tools") or [])
        + len(intent.get("tags") or [])
        + (1 if intent.get("project_type") not in (None, "", "general") else 0)
    )
    signal_score = max(0.0, min(1.0, signals / 5.0))

    top = sorted((float(r.get("final_score") or 0) for r in results), reverse=True)[:5]
    evidence = sum(top) / len(top) if top else 0.0

    confidence = 0.32 * word_score + 0.30 * signal_score + 0.38 * evidence
    pct = round(confidence * 100)

    if not results:
        advice = "No matches yet. Try broader wording or a different angle."
    elif pct < 45:
        advice = (
            "Broad query. Add your stack, goal, or constraints "
            "(e.g. \u201cin Next.js\u201d, \u201cfor RAG over PDFs\u201d) to sharpen the map."
        )
    elif pct < 70:
        advice = "Decent match. Add one tool or goal to tighten the results."
    else:
        advice = "Specific query \u2014 the top matches should fit well."
    return pct, advice


def _key_points(artifact: dict[str, Any]) -> list[str]:
    points: list[str] = []
    what = _clip(artifact.get("what_it_helps_build") or artifact.get("summary"), 110, strip_md=True)
    if what:
        points.append(what)
    stack = _stack(artifact)
    if stack:
        points.append("Stack: " + ", ".join(stack))
    impl = _simple_implementation(artifact)
    if impl:
        points.append("Start: " + _clip(impl, 80))
    return points[:3]


def _confidence_label(relevance: float) -> str:
    if relevance >= 0.66:
        return "strong match"
    if relevance >= 0.4:
        return "related"
    return "adjacent"


def _about(artifact: dict[str, Any]) -> str:
    """A fuller 'what this is' paragraph."""
    for key in ("summary", "technical_core", "what_it_helps_build"):
        v = _clip(artifact.get(key), 260, strip_md=True)
        if v and len(v) > 40:
            return v
    return _clip(artifact.get("summary"), 260, strip_md=True)


def _how_it_helps(artifact: dict[str, Any]) -> str:
    """One line on the value it gives you."""
    helps = _clip(artifact.get("what_it_helps_build"), 170, strip_md=True)
    use = _clip(artifact.get("practical_use_case"), 170, strip_md=True)
    if helps and use and helps.lower() not in use.lower():
        return f"{helps} Useful for {use[0].lower()}{use[1:]}" if use else helps
    return helps or use or "A strong example you can learn from and adapt into your own build."


def _stands_out(artifact: dict[str, Any]) -> list[str]:
    """Why this one is worth your attention vs the rest."""
    out: list[str] = []
    q = float(artifact.get("quality_score") or 0)
    remix = float(artifact.get("remixability_score") or 0)
    under = float(artifact.get("underground_score") or 0)
    hype = float(artifact.get("hype_risk_score") or 0)
    atype = artifact.get("artifact_type") or ""

    if under >= 68 and hype <= 38:
        out.append("Underground pick \u2014 high signal before it trends")
    if remix >= 74:
        out.append("Highly remixable into your own stack")
    if artifact.get("has_code") and (artifact.get("setup_commands") or artifact.get("implementation_steps")):
        out.append("Ships runnable code with setup steps")
    if artifact.get("has_demo"):
        out.append("Has a live demo to try first")
    if artifact.get("has_paper") or atype == "research_paper":
        out.append("Research-backed technique")
    if atype == "mcp_server":
        out.append("Plugs straight into your coding agent")
    if q >= 80 and not out:
        out.append("High-quality, well-documented build")
    if not out:
        out.append("Solid, on-topic match for what you described")
    return out[:3]


def build_landscape(query: str, intent: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Enrich results in place and return cluster metadata for the graph."""
    cluster_counts: dict[str, int] = {}
    cluster_labels: dict[str, str] = {}

    for r in results:
        relevance = float(r.get("final_score") or 0.0)
        theme_id, theme_label = _theme_for(r)

        cluster_counts[theme_id] = cluster_counts.get(theme_id, 0) + 1
        cluster_labels[theme_id] = theme_label

        r["relevance"] = round(relevance, 4)
        r["relevance_pct"] = round(relevance * 100)
        r["confidence"] = _confidence_label(relevance)
        r["cluster_id"] = theme_id
        r["cluster_label"] = theme_label
        r["headline"] = _headline(r)
        r["key_points"] = _key_points(r)
        r["use_case"] = _clip(r.get("practical_use_case"), 140)
        r["simple_implementation"] = _simple_implementation(r)
        r["start_steps"] = _start_steps(r)
        r["about"] = _about(r)
        r["how_it_helps"] = _how_it_helps(r)
        r["stands_out"] = _stands_out(r)

    # Mark the strongest few so the UI can spotlight them.
    for rank, r in enumerate(sorted(results, key=lambda x: float(x.get("final_score") or 0), reverse=True)):
        r["top_rank"] = rank  # 0 = best

    clusters = [
        {"id": tid, "label": cluster_labels[tid], "count": cluster_counts[tid]}
        for tid in _THEME_ORDER
        if tid in cluster_counts
    ]

    confidence, advice = _query_confidence(query, intent, results)
    suggested = _suggest_query(query, intent, results, confidence)

    return {
        "clusters": clusters,
        "summary": _landscape_summary(query, intent, results, clusters),
        "query_confidence": confidence,
        "query_advice": advice,
        "suggested_query": suggested,
    }


def _suggest_query(
    query: str,
    intent: dict[str, Any],
    results: list[dict[str, Any]],
    confidence: int,
) -> str:
    """For weak queries, propose a sharper version grounded in the closest matches.

    Only adds refinements the user did not already state, never appends random
    languages from top hits, and requires agreement across multiple results.
    """
    from collections import Counter

    if confidence >= 62 or len(results) < 2:
        return ""

    q = query.strip()
    q_lower = q.lower()
    tokens = set(re.findall(r"[a-z0-9+#.-]{2,}", q_lower))
    word_count = len([w for w in re.findall(r"[a-zA-Z0-9+.#-]+", query) if len(w) > 2])

    # Already fairly specific — skip unless we have a high-signal refinement.
    if word_count >= 7 and confidence >= 50:
        return ""

    lang_names = {k.lower() for k in LANGUAGES} | {v.lower() for v in LANGUAGES.values()}
    user_stack = {
        x.lower()
        for x in (
            (intent.get("frameworks") or [])
            + (intent.get("tools") or [])
            + (intent.get("languages") or [])
        )
    }
    skip_tags = {
        "hackernews",
        "arxiv",
        "research",
        "github",
        "ai",
        "open-source",
        "open source",
        "machine-learning",
        "ml",
        "llm",
        "api",
        "tool",
        "library",
        "repo",
        "project",
    } | lang_names

    goal_hints = {
        "edge",
        "mobile",
        "browser",
        "real-time",
        "realtime",
        "offline",
        "self-hosted",
        "self hosted",
        "production",
        "streaming",
        "on-device",
        "on device",
        "inference",
        "quantization",
        "gpu",
        "cpu",
        "latency",
        "throughput",
        "batch",
        "serverless",
        "local",
        "embedded",
        "video",
        "image",
        "audio",
        "pdf",
        "rag",
        "agent",
        "mcp",
    }

    stack: Counter[str] = Counter()
    goals: Counter[str] = Counter()

    for r in results[:5]:
        for x in (r.get("frameworks") or [])[:3] + (r.get("tools") or [])[:3]:
            xl = x.lower()
            if xl in lang_names or xl in skip_tags:
                continue
            stack[x] += 1
        for x in (r.get("tags") or [])[:8]:
            xl = x.lower().replace("_", " ")
            if xl in skip_tags or xl in lang_names:
                continue
            goals[x] += 1

    def overlaps_query(term: str) -> bool:
        tl = term.lower()
        if tl in q_lower:
            return True
        for part in re.split(r"[\s/_-]+", tl):
            if len(part) >= 3 and part in tokens:
                return True
        return False

    def pick_stack() -> str | None:
        if user_stack:
            return None
        for name, count in stack.most_common(4):
            if count < 2 or overlaps_query(name):
                continue
            if name.lower() in user_stack:
                continue
            return name
        return None

    def pick_goal() -> str | None:
        # Prefer constraint-like tags that sharpen the build context.
        ranked = sorted(
            goals.items(),
            key=lambda kv: (kv[0].lower().replace("_", " ") in goal_hints, kv[1]),
            reverse=True,
        )
        for name, count in ranked:
            if count < 2 or overlaps_query(name):
                continue
            return name
        return None

    stack_pick = pick_stack()
    goal_pick = pick_goal()

    if not stack_pick and not goal_pick:
        return ""

    if stack_pick and goal_pick:
        return f"{q} with {stack_pick}, focused on {goal_pick}"

    if stack_pick:
        return f"{q} with {stack_pick}"

    if goal_pick:
        if re.search(r"\bfor\b", q_lower):
            return f"{q}, {goal_pick}"
        return f"{q} for {goal_pick}"

    return ""


def _landscape_summary(
    query: str,
    intent: dict[str, Any],
    results: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
) -> str:
    """One calm sentence describing the shape of the result space."""
    if not results:
        return "No indexed artifacts match this yet."
    n = len(results)
    top_clusters = ", ".join(c["label"].lower() for c in clusters[:2]) or "results"
    strong = sum(1 for r in results if float(r.get("final_score") or 0) >= 0.66)
    lead = f"{n} indexed builds across {top_clusters}"
    if strong:
        lead += f", {strong} a strong match"
    return lead + "."

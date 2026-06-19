"""Turn ranked search results into an explainable 'landscape' for the UI.

Groups results into themed clusters, attaches a normalized relevance, and
extracts concise, skimmable key points + a one-line use case per result.
No LLM calls: pure derivation from already-indexed fields.
"""
from __future__ import annotations

import re
from typing import Any

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
    return helps or use or "A reusable starting point you can fork into your own build."


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
    suggested = _suggest_query(query, results, confidence)

    return {
        "clusters": clusters,
        "summary": _landscape_summary(query, intent, results, clusters),
        "query_confidence": confidence,
        "query_advice": advice,
        "suggested_query": suggested,
    }


def _suggest_query(query: str, results: list[dict[str, Any]], confidence: int) -> str:
    """For weak queries, propose a sharper version grounded in the closest matches.

    Pure derivation: counts the most common stack + topics among the top results
    and appends the informative bits the user didn't already mention.
    """
    from collections import Counter

    if confidence >= 62 or len(results) < 2:
        return ""

    q = query.strip()
    q_lower = q.lower()
    stack: Counter = Counter()
    topics: Counter = Counter()
    _skip_tags = {"hackernews", "arxiv", "research", "github", "ai", "open-source"}

    for r in results[:6]:
        for x in (r.get("frameworks") or [])[:4]:
            stack[x] += 1
        for x in (r.get("tools") or [])[:4]:
            stack[x] += 1
        for x in (r.get("tags") or [])[:6]:
            if x.lower() not in _skip_tags:
                topics[x] += 1

    add_stack = [x for x, _ in stack.most_common(5) if x.lower() not in q_lower][:2]
    # Topics must add NEW information: skip anything already in the query or stack.
    chosen = {x.lower() for x in add_stack} | set(q_lower.split())
    add_topic: list[str] = []
    for x, _ in topics.most_common(8):
        if x.lower() in chosen or x.lower() in q_lower:
            continue
        add_topic.append(x)
        chosen.add(x.lower())
        if len(add_topic) == 2:
            break

    parts = [q]
    if add_stack:
        parts.append("using " + " and ".join(add_stack))
    if add_topic:
        parts.append("for " + ", ".join(add_topic))

    suggestion = " ".join(parts)
    if suggestion.strip().lower() == q_lower or len(parts) == 1:
        return ""
    return suggestion


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

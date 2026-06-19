"use client";

import { useMemo, useRef, useState } from "react";
import type { Artifact, LandscapeCluster } from "@/lib/types";

const W = 1120;
const H = 760;
const CX = W / 2;
const CY = H / 2;
const R_MIN = 132;
const R_MAX = 300;
const PER_CLUSTER = 7;

const CLUSTER_COLOR: Record<string, string> = {
  templates: "#7aa2f7",
  projects: "#9ece6a",
  agents: "#bb9af7",
  research: "#e0af68",
  libraries: "#7dcfff",
};
const colorFor = (id?: string) => (id && CLUSTER_COLOR[id]) || "#8a8a93";

type GNode = {
  id: string;
  x: number;
  y: number;
  r: number;
  rel: number;
  color: string;
  label: string;
  top: boolean;
  labelAbove: boolean;
};

export function LandscapeGraph({
  query,
  results,
  clusters,
  selectedId,
  onSelect,
}: {
  query: string;
  results: Artifact[];
  clusters: LandscapeCluster[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const raf = useRef<number | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [par, setPar] = useState({ x: 0, y: 0 });

  const { nodes, labels, overflow } = useMemo(() => {
    const ids = clusters.length
      ? clusters.map((c) => c.id)
      : Array.from(new Set(results.map((r) => r.cluster_id || "projects")));

    const out: GNode[] = [];
    const labelPts: { id: string; label: string; x: number; y: number }[] = [];
    const over: { id: string; n: number; x: number; y: number }[] = [];

    // Allocate angular arc proportional to each cluster's size, so a busy
    // cluster gets more room and nodes/labels never crowd.
    const grouped = ids.map((cid) => ({
      cid,
      all: results
        .filter((r) => (r.cluster_id || "projects") === cid)
        .sort((a, b) => (b.relevance ?? 0) - (a.relevance ?? 0)),
    }));
    const total = grouped.reduce((s, g) => s + Math.min(PER_CLUSTER, g.all.length), 0) || 1;

    let acc = -Math.PI / 2;
    grouped.forEach(({ cid, all }) => {
      const items = all.slice(0, PER_CLUSTER);
      const share = (items.length / total) * Math.PI * 2;
      const center = acc + share / 2;
      acc += share;
      const span = share * 0.8;

      items.forEach((item, ii) => {
        const rel = Math.max(0.05, Math.min(1, item.relevance ?? item.final_score ?? 0));
        const t = items.length > 1 ? ii / (items.length - 1) - 0.5 : 0;
        const angle = center + t * span;
        const depth = items.length > 1 ? ii / (items.length - 1) : 0.4;
        const radius = R_MIN + depth * (R_MAX - R_MIN);
        const top = (item.top_rank ?? 999) < 4;
        out.push({
          id: item.id,
          x: CX + Math.cos(angle) * radius,
          y: CY + Math.sin(angle) * radius,
          r: top ? 17 : 7 + rel * 8,
          rel,
          color: colorFor(cid),
          label: item.headline || item.title,
          top,
          labelAbove: ii % 2 === 1,
        });
      });

      const lr = R_MAX + 64;
      labelPts.push({
        id: cid,
        label: clusters.find((c) => c.id === cid)?.label || cid,
        x: CX + Math.cos(center) * lr,
        y: CY + Math.sin(center) * lr,
      });
      if (all.length > items.length) {
        over.push({
          id: cid,
          n: all.length - items.length,
          x: CX + Math.cos(center) * (R_MAX + 36),
          y: CY + Math.sin(center) * (R_MAX + 36),
        });
      }
    });

    return { nodes: out, labels: labelPts, overflow: over };
  }, [results, clusters]);

  function onMove(e: React.MouseEvent) {
    const el = wrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const nx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
    const ny = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
    if (raf.current) cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => setPar({ x: nx, y: ny }));
  }

  const nodeShift = { x: par.x * 16, y: par.y * 16 };
  const edgeShift = { x: par.x * 7, y: par.y * 7 };
  const active = hover || selectedId;

  return (
    <div
      ref={wrapRef}
      className="relative h-full w-full"
      onMouseMove={onMove}
      onMouseLeave={() => {
        setHover(null);
        setPar({ x: 0, y: 0 });
      }}
    >
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full select-none"
        onClick={() => onSelect(null)}
      >
        <defs>
          <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="6" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <radialGradient id="core" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#1c1c20" />
            <stop offset="100%" stopColor="#0c0c0e" />
          </radialGradient>
        </defs>

        {/* faint concentric relevance rings */}
        <g opacity={0.5}>
          {[R_MIN, (R_MIN + R_MAX) / 2, R_MAX].map((r) => (
            <circle key={r} cx={CX} cy={CY} r={r} fill="none" stroke="rgba(255,255,255,0.05)" />
          ))}
        </g>

        {/* curved edges */}
        <g transform={`translate(${edgeShift.x} ${edgeShift.y})`}>
          {nodes.map((n) => {
            const isActive = active === n.id;
            const dim = active && !isActive;
            const mx = (CX + n.x) / 2 + (n.y - CY) * 0.12;
            const my = (CY + n.y) / 2 - (n.x - CX) * 0.12;
            return (
              <path
                key={`e-${n.id}`}
                d={`M${CX},${CY} Q${mx},${my} ${n.x},${n.y}`}
                fill="none"
                stroke={n.color}
                strokeWidth={isActive ? 2.4 : 0.6 + n.rel * 1.8}
                strokeOpacity={dim ? 0.05 : isActive ? 0.7 : 0.12 + n.rel * 0.3}
                style={{ transition: "stroke-opacity .25s, stroke-width .2s" }}
              />
            );
          })}
        </g>

        {/* cluster labels */}
        <g opacity={0.85}>
          {labels.map((l) => (
            <text
              key={`l-${l.id}`}
              x={l.x}
              y={l.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-[var(--muted)]"
              style={{
                fontSize: 12.5,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                paintOrder: "stroke",
                stroke: "#0a0a0b",
                strokeWidth: 4,
                strokeLinejoin: "round",
              }}
            >
              {l.label}
            </text>
          ))}
          {overflow.map((o) => (
            <text
              key={`o-${o.id}`}
              x={o.x}
              y={o.y}
              textAnchor="middle"
              className="fill-[var(--muted)]"
              style={{ fontSize: 11, opacity: 0.7 }}
            >
              +{o.n} more
            </text>
          ))}
        </g>

        {/* nodes */}
        <g transform={`translate(${nodeShift.x} ${nodeShift.y})`}>
          {nodes.map((n, i) => {
            const isSel = selectedId === n.id;
            const isHov = hover === n.id;
            const isActive = isSel || isHov;
            const dim = active && !isActive;
            const showLabel = n.top || isActive;
            const rr = isActive ? n.r + 4 : n.r;
            return (
              <g
                key={n.id}
                className="br-fade-up"
                style={{ animationDelay: `${Math.min(i * 26, 700)}ms`, cursor: "pointer" }}
                opacity={dim ? 0.28 : 1}
                onMouseEnter={() => setHover(n.id)}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(n.id);
                }}
              >
                {/* soft halo */}
                <circle cx={n.x} cy={n.y} r={rr + 10} fill={n.color} opacity={isActive ? 0.18 : n.top ? 0.1 : 0} />
                {n.top && (
                  <circle cx={n.x} cy={n.y} r={rr + 6} fill="none" stroke={n.color} strokeWidth={1} strokeOpacity={0.45} />
                )}
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={rr}
                  fill={n.color}
                  fillOpacity={isActive ? 1 : 0.82}
                  stroke="#0a0a0b"
                  strokeWidth={2}
                  filter={isActive || n.top ? "url(#glow)" : undefined}
                  style={{ transition: "r .15s" }}
                />
                {showLabel && (
                  <text
                    x={n.x}
                    y={n.labelAbove ? n.y - rr - 9 : n.y + rr + 15}
                    textAnchor="middle"
                    className="fill-[var(--ink)]"
                    style={{
                      fontSize: 12,
                      fontWeight: isActive ? 600 : 500,
                      paintOrder: "stroke",
                      stroke: "#0a0a0b",
                      strokeWidth: 3.5,
                      strokeLinejoin: "round",
                    }}
                  >
                    {n.label.length > 24 ? n.label.slice(0, 23) + "\u2026" : n.label}
                  </text>
                )}
              </g>
            );
          })}
        </g>

        {/* center query node */}
        <g transform={`translate(${nodeShift.x * 0.3} ${nodeShift.y * 0.3})`}>
          <circle cx={CX} cy={CY} r={34} fill="url(#core)" stroke="rgba(255,255,255,0.2)" strokeWidth={1.5} />
          <circle cx={CX} cy={CY} r={4} fill="var(--ink)" />
          <text
            x={CX}
            y={CY + 56}
            textAnchor="middle"
            className="fill-[var(--ink)]"
            style={{
              fontSize: 14,
              fontWeight: 600,
              paintOrder: "stroke",
              stroke: "#0a0a0b",
              strokeWidth: 4,
              strokeLinejoin: "round",
            }}
          >
            {query.length > 50 ? query.slice(0, 49) + "\u2026" : query}
          </text>
        </g>
      </svg>
    </div>
  );
}

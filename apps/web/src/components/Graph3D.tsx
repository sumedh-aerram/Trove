"use client";

import { Canvas } from "@react-three/fiber";
import { Html, Line, OrbitControls } from "@react-three/drei";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useMemo, useState } from "react";
import * as THREE from "three";
import type { Artifact, LandscapeCluster } from "@/lib/types";

const R_MIN = 2.6;
const R_MAX = 6.8;
const PER_CLUSTER = 8;

const CLUSTER_COLOR: Record<string, string> = {
  templates: "#7aa2f7",
  projects: "#9ece6a",
  agents: "#bb9af7",
  research: "#e0af68",
  libraries: "#7dcfff",
};
const colorFor = (id?: string) => (id && CLUSTER_COLOR[id]) || "#8a8a93";

type Vec = [number, number, number];
type N3 = {
  id: string;
  cluster: string;
  pos: Vec;
  r: number;
  color: string;
  label: string;
  top: boolean;
  rel: number;
};
type Edge = { a: Vec; b: Vec; color: string; weight: number; ids: [string, string] };

const norm = (v: Vec): Vec => {
  const l = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / l, v[1] / l, v[2] / l];
};
const cross = (a: Vec, b: Vec): Vec => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
// deterministic pseudo-random in [-1,1]
const rnd = (i: number) => {
  const n = Math.sin(i * 78.233 + 12.9898) * 43758.5453;
  return (n - Math.floor(n)) * 2 - 1;
};
// evenly spread cluster directions on a sphere (organic, not a flat ring)
const fib = (i: number, n: number): Vec => {
  const phi = Math.acos(1 - (2 * (i + 0.5)) / n);
  const theta = Math.PI * (1 + Math.sqrt(5)) * i;
  return [Math.sin(phi) * Math.cos(theta), Math.cos(phi), Math.sin(phi) * Math.sin(theta)];
};

function Node({
  n,
  active,
  dim,
  showLabel,
  onSelect,
  onHover,
}: {
  n: N3;
  active: boolean;
  dim: boolean;
  showLabel: boolean;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const r = active ? n.r * 1.25 : n.r;
  return (
    <group position={n.pos}>
      <mesh>
        <sphereGeometry args={[r + (active ? 0.22 : 0.12), 20, 20]} />
        <meshBasicMaterial
          color={n.color}
          transparent
          opacity={dim ? 0.04 : active ? 0.3 : 0.12}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <mesh
        onClick={(e) => {
          e.stopPropagation();
          onSelect(n.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(n.id);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          onHover(null);
          document.body.style.cursor = "auto";
        }}
      >
        <sphereGeometry args={[r, 28, 28]} />
        <meshStandardMaterial
          color={n.color}
          emissive={n.color}
          emissiveIntensity={active ? 1.5 : 0.55}
          roughness={0.35}
          metalness={0.2}
          transparent
          opacity={dim ? 0.45 : 1}
        />
      </mesh>
      {showLabel && (
        <Html center position={[0, -r - 0.3, 0]} zIndexRange={[100, 0]} style={{ pointerEvents: "none" }}>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "#f4f4f6",
              background: "rgba(8,8,9,0.86)",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 7,
              padding: "3px 9px",
              whiteSpace: "nowrap",
              boxShadow: "0 2px 10px rgba(0,0,0,0.6)",
            }}
          >
            {n.label.length > 34 ? n.label.slice(0, 33) + "\u2026" : n.label}
          </div>
        </Html>
      )}
    </group>
  );
}

function Scene({
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
  onSelect: (id: string) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);

  const { nodes, edges } = useMemo(() => {
    const ids = clusters.length
      ? clusters.map((c) => c.id)
      : Array.from(new Set(results.map((r) => r.cluster_id || "projects")));
    const nc = ids.length || 1;
    const out: N3[] = [];
    let seed = 1;

    ids.forEach((cid, ci) => {
      const items = results
        .filter((r) => (r.cluster_id || "projects") === cid)
        .sort((a, b) => (b.relevance ?? 0) - (a.relevance ?? 0))
        .slice(0, PER_CLUSTER);

      const dir = norm(fib(ci, nc));
      const up: Vec = Math.abs(dir[1]) < 0.95 ? [0, 1, 0] : [1, 0, 0];
      const t1 = norm(cross(up, dir));
      const t2 = norm(cross(dir, t1));

      items.forEach((item) => {
        const rel = Math.max(0.05, Math.min(1, item.relevance ?? item.final_score ?? 0));
        const radius = R_MIN + (1 - rel) * (R_MAX - R_MIN);
        const a = rnd(seed++) * 0.5;
        const b = rnd(seed++) * 0.5;
        const d = norm([
          dir[0] + t1[0] * a + t2[0] * b,
          dir[1] + t1[1] * a + t2[1] * b,
          dir[2] + t1[2] * a + t2[2] * b,
        ]);
        out.push({
          id: item.id,
          cluster: cid,
          pos: [d[0] * radius, d[1] * radius, d[2] * radius],
          r: (item.top_rank ?? 999) < 4 ? 0.2 : 0.11 + rel * 0.08,
          color: colorFor(cid),
          label: item.headline || item.title,
          top: (item.top_rank ?? 999) < 4,
          rel,
        });
      });
    });

    // build a web: center -> node, plus chains within each cluster
    const e: Edge[] = [];
    const origin: Vec = [0, 0, 0];
    out.forEach((n) =>
      e.push({ a: origin, b: n.pos, color: "#5a5a66", weight: 0.06 + n.rel * 0.16, ids: ["", n.id] }),
    );
    ids.forEach((cid) => {
      const members = out.filter((n) => n.cluster === cid);
      for (let i = 0; i < members.length - 1; i++) {
        e.push({
          a: members[i].pos,
          b: members[i + 1].pos,
          color: colorFor(cid),
          weight: 0.16,
          ids: [members[i].id, members[i + 1].id],
        });
      }
    });
    return { nodes: out, edges: e };
  }, [results, clusters]);

  const active = hovered || selectedId;

  return (
    <>
      <fog attach="fog" args={["#0a0a0b", 10, 22]} />
      <ambientLight intensity={0.6} />
      <pointLight position={[0, 0, 0]} intensity={0.9} distance={24} />

      {edges.map((ed, i) => {
        const touches = active && (ed.ids[0] === active || ed.ids[1] === active);
        const dim = active && !touches;
        return (
          <Line
            key={i}
            points={[ed.a, ed.b]}
            color={touches ? ed.color : ed.color}
            lineWidth={touches ? 1.8 : ed.weight * 6}
            transparent
            opacity={dim ? 0.04 : touches ? 0.6 : ed.weight + 0.06}
          />
        );
      })}

      <mesh>
        <sphereGeometry args={[0.34, 28, 28]} />
        <meshStandardMaterial color="#1c1c20" emissive="#888" emissiveIntensity={0.3} roughness={0.5} />
      </mesh>
      <Html center position={[0, -0.7, 0]} zIndexRange={[100, 0]} style={{ pointerEvents: "none" }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#f4f4f6",
            background: "rgba(8,8,9,0.86)",
            border: "1px solid rgba(255,255,255,0.14)",
            borderRadius: 8,
            padding: "4px 11px",
            whiteSpace: "nowrap",
            boxShadow: "0 2px 12px rgba(0,0,0,0.6)",
          }}
        >
          {query.length > 40 ? query.slice(0, 39) + "\u2026" : query}
        </div>
      </Html>

      {nodes.map((n) => {
        const isActive = active === n.id;
        return (
          <Node
            key={n.id}
            n={n}
            active={isActive}
            dim={!!active && !isActive}
            showLabel={isActive}
            onSelect={onSelect}
            onHover={setHovered}
          />
        );
      })}

      <OrbitControls
        enablePan={false}
        enableZoom
        minDistance={7}
        maxDistance={18}
        rotateSpeed={0.7}
        zoomSpeed={0.6}
        autoRotate={!hovered}
        autoRotateSpeed={0.25}
        makeDefault
      />

      <EffectComposer>
        <Bloom intensity={0.7} luminanceThreshold={0.22} luminanceSmoothing={0.5} mipmapBlur />
      </EffectComposer>
    </>
  );
}

export function Graph3D({
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
  return (
    <div className="h-full w-full">
      <Canvas camera={{ position: [0, 1, 14], fov: 45 }} gl={{ alpha: true, antialias: true }}>
        <Scene
          query={query}
          results={results}
          clusters={clusters}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      </Canvas>
    </div>
  );
}

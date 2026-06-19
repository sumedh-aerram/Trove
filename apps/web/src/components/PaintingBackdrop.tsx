/**
 * Painterly Van Gogh backdrop with a subtle animated layer on top.
 *  - "home": darkened painting + slow Ken Burns drift, twinkling stars,
 *    drifting golden glow motes, and a slow light sweep. Reads as a living sky.
 *  - "results": the painting reduced to a dark blurred haze with one barely-there
 *    drifting glow, so it has life without competing with the graph.
 * Deterministic positions (no hydration mismatch). Honors reduced-motion.
 */

// Fixed star positions over the sky (upper portion). [top%, left%, sizePx, durS, delayS]
const STARS: [number, number, number, number, number][] = [
  [12, 10, 4, 4.5, 0], [8, 24, 3, 5.5, 1.2], [18, 38, 5, 6, 0.6], [10, 52, 3, 4.8, 2],
  [16, 67, 4, 5.2, 0.4], [9, 80, 5, 6.4, 1.6], [22, 88, 3, 5, 0.9], [26, 16, 4, 5.8, 2.4],
  [30, 46, 3, 4.6, 1.1], [24, 60, 4, 6.1, 0.2], [34, 74, 3, 5.4, 1.8], [14, 5, 3, 5, 3],
  [20, 94, 4, 5.6, 0.7], [38, 30, 3, 6.2, 2.1], [6, 44, 4, 4.9, 1.4],
];

// Drifting glow motes. [top%, left%, sizePx, color, durS, dx, dy, opacity]
const MOTES: [number, number, number, string, number, string, string, number][] = [
  [18, 18, 220, "201,162,74", 64, "4%", "-3%", 0.18],
  [12, 70, 260, "120,150,210", 78, "-3%", "4%", 0.16],
  [40, 50, 300, "58,90,90", 88, "3%", "3%", 0.14],
  [30, 88, 200, "201,162,74", 70, "-4%", "-2%", 0.14],
];

function Shimmer() {
  return (
    <div className="absolute inset-0" aria-hidden>
      {MOTES.map(([top, left, size, rgb, dur, dx, dy, op], i) => (
        <div
          key={`m-${i}`}
          className="br-mote"
          style={
            {
              top: `${top}%`,
              left: `${left}%`,
              width: size,
              height: size,
              opacity: op,
              background: `radial-gradient(circle, rgba(${rgb},0.85), transparent 70%)`,
              "--dur": `${dur}s`,
              "--dx": dx,
              "--dy": dy,
            } as React.CSSProperties
          }
        />
      ))}
      {STARS.map(([top, left, size, dur, delay], i) => (
        <div
          key={`s-${i}`}
          className="br-star"
          style={
            {
              top: `${top}%`,
              left: `${left}%`,
              width: size,
              height: size,
              "--dur": `${dur}s`,
              animationDelay: `${delay}s`,
            } as React.CSSProperties
          }
        />
      ))}
      {/* slow moonlight sweep */}
      <div
        className="absolute inset-y-0 w-1/3"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(232,224,180,0.05), transparent)",
          animation: "br-sweep 26s ease-in-out infinite",
        }}
      />
    </div>
  );
}

export function PaintingBackdrop({ variant }: { variant: "home" | "results" }) {
  if (variant === "results") {
    return (
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[var(--bg)]" aria-hidden>
        <div
          className="br-kenburns-slow absolute inset-[-8%] bg-cover bg-center"
          style={{
            backgroundImage: "url(/vangogh-night.png)",
            filter: "blur(34px) brightness(0.32) saturate(0.9)",
            opacity: 0.38,
          }}
        />
        {/* one whisper-subtle drifting glow */}
        <div
          className="br-mote"
          style={
            {
              top: "30%",
              left: "55%",
              width: 360,
              height: 360,
              opacity: 0.05,
              background: "radial-gradient(circle, rgba(201,162,74,0.8), transparent 70%)",
              "--dur": "96s",
              "--dx": "-4%",
              "--dy": "3%",
            } as React.CSSProperties
          }
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 90% at 50% 45%, transparent 40%, rgba(10,10,11,0.85) 100%)",
          }}
        />
      </div>
    );
  }

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[var(--bg)]" aria-hidden>
      <div
        className="br-kenburns absolute inset-[-6%] bg-cover bg-center"
        style={{
          backgroundImage: "url(/vangogh-night.png)",
          filter: "brightness(0.52) saturate(1.05) contrast(1.02)",
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(110% 80% at 50% 42%, rgba(10,10,11,0.15) 0%, rgba(10,10,11,0.55) 55%, rgba(10,10,11,0.82) 100%)",
        }}
      />
      <Shimmer />
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(10,10,11,0.4) 0%, transparent 30%, transparent 60%, rgba(10,10,11,0.6) 100%)",
        }}
      />
      <div className="br-grain absolute inset-0" />
    </div>
  );
}

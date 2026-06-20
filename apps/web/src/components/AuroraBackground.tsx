/**
 * Subtle aurora borealis background for the results page: soft color bands in
 * the cluster palette (teal, green, blue, violet, gold) that slowly drift and
 * breathe over black. Distinct from the home painting-reveal. Very low opacity
 * so it never competes with the 3D graph. Pure CSS, honors reduced-motion.
 */
const BANDS: { color: string; cls: string; style: React.CSSProperties }[] = [
  {
    color: "rgba(122,162,247,0.9)",
    cls: "br-aurora",
    style: {
      top: "-20%",
      left: "5%",
      width: "55%",
      height: "90%",
      animation: "br-aurora-a 26s ease-in-out infinite, br-breathe 14s ease-in-out infinite",
    },
  },
  {
    color: "rgba(158,206,106,0.9)",
    cls: "br-aurora",
    style: {
      top: "-10%",
      left: "35%",
      width: "55%",
      height: "100%",
      animation: "br-aurora-b 32s ease-in-out infinite, br-breathe-soft 18s ease-in-out infinite",
    },
  },
  {
    color: "rgba(187,154,247,0.9)",
    cls: "br-aurora",
    style: {
      top: "0%",
      left: "55%",
      width: "50%",
      height: "95%",
      animation: "br-aurora-c 38s ease-in-out infinite, br-breathe 22s ease-in-out infinite",
    },
  },
  {
    color: "rgba(125,207,255,0.85)",
    cls: "br-aurora",
    style: {
      top: "-15%",
      left: "20%",
      width: "45%",
      height: "85%",
      animation: "br-aurora-c 30s ease-in-out infinite, br-breathe-soft 16s ease-in-out infinite",
    },
  },
];

export function AuroraBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[var(--bg)]" aria-hidden>
      {BANDS.map((b, i) => (
        <div
          key={i}
          className={b.cls}
          style={{
            position: "absolute",
            borderRadius: "50%",
            filter: "blur(90px)",
            mixBlendMode: "screen",
            background: `radial-gradient(closest-side, ${b.color}, transparent 75%)`,
            ...b.style,
          }}
        />
      ))}
      {/* keep the center calm so the graph reads cleanly */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(80% 70% at 50% 50%, rgba(10,10,11,0.55) 0%, transparent 60%)",
        }}
      />
    </div>
  );
}

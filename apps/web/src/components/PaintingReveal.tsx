"use client";

import { useEffect, useRef } from "react";

/**
 * Black canvas with a Van Gogh painting hidden underneath, revealed only along
 * broad animated brush strokes that drift across the screen (a flow field used
 * as a mask, not as visible strokes). Reveals slowly fade back to black.
 *
 * variant: "home" (a touch more reveal) | "results" (barely there behind the graph)
 */
const PAINTING = "/vangogh-night.png";

function fade(t: number) {
  return t * t * t * (t * (t * 6 - 15) + 10);
}
function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
function rnd(ix: number, iy: number) {
  const n = Math.sin(ix * 127.1 + iy * 311.7) * 43758.5453;
  return (n - Math.floor(n)) * 2 - 1;
}
function vnoise(x: number, y: number) {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = x - ix;
  const fy = y - iy;
  const ux = fade(fx);
  const uy = fade(fy);
  return lerp(
    lerp(rnd(ix, iy), rnd(ix + 1, iy), ux),
    lerp(rnd(ix, iy + 1), rnd(ix + 1, iy + 1), ux),
    uy,
  );
}

type Cfg = {
  tracers: number;
  fade: number;
  line: number;
  brightness: number;
  scale: number;
  speed: number;
  strokeAlpha: number;
  stepsPerStroke: number;
  blur: number;
};

export function PaintingReveal({ variant }: { variant: "home" | "results" }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const cfg: Cfg =
      variant === "results"
        ? {
            tracers: 18,
            fade: 0.024,
            line: 2.4,
            brightness: 0.5,
            scale: 0.00095,
            speed: 1.1,
            strokeAlpha: 0.26,
            stepsPerStroke: 5,
            blur: 2,
          }
        : {
            tracers: 12,
            fade: 0.018,
            line: 5.5,
            brightness: 0.58,
            scale: 0.0009,
            speed: 1.35,
            strokeAlpha: 0.3,
            stepsPerStroke: 7,
            blur: 3,
          };

    const mask = document.createElement("canvas");
    const mctx = mask.getContext("2d")!;

    const painting = new Image();
    let ready = false;
    let iw = 819;
    let ih = 546;
    painting.onload = () => {
      ready = true;
      iw = painting.naturalWidth;
      ih = painting.naturalHeight;
    };
    painting.src = PAINTING;

    let w = 0;
    let h = 0;
    let dpr = 1;
    type P = { x: number; y: number; life: number };
    let tracers: P[] = [];
    let t = 0;
    let raf = 0;

    const spawnAt = (x: number, y: number): P => ({
      x,
      y,
      life: 140 + Math.random() * 160,
    });

    const spawnGrid = (count: number): P[] => {
      const cols = Math.ceil(Math.sqrt(count));
      const rows = Math.ceil(count / cols);
      return Array.from({ length: count }, (_, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const x = (col + 0.5 + (Math.random() - 0.5) * 0.25) * (w / cols);
        const y = (row + 0.5 + (Math.random() - 0.5) * 0.25) * (h / rows);
        return spawnAt(x, y);
      });
    };

    const spawnRandom = (): P => spawnAt(Math.random() * w, Math.random() * h);

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = mask.width = Math.floor(w * dpr);
      canvas.height = mask.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      mctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(cfg.tracers, Math.max(8, Math.floor((w * h) / 50000)));
      tracers = spawnGrid(count);
    };

    const drawCover = (c: CanvasRenderingContext2D) => {
      const ca = w / h;
      const ia = iw / ih;
      let dw = w;
      let dh = h;
      if (ca > ia) {
        dw = w;
        dh = w / ia;
      } else {
        dh = h;
        dw = h * ia;
      }
      c.drawImage(painting, (w - dw) / 2, (h - dh) / 2, dw, dh);
    };

    // Single-octave field → wider, calmer arcs instead of tight scribbles.
    const angleAt = (x: number, y: number) =>
      vnoise(x * cfg.scale + t * 0.015, y * cfg.scale + t * 0.01) * Math.PI * 2;

    const drawSmoothStroke = (p: P) => {
      mctx.beginPath();
      mctx.moveTo(p.x, p.y);

      let px = p.x;
      let py = p.y;
      for (let i = 0; i < cfg.stepsPerStroke; i++) {
        const a = angleAt(p.x, p.y);
        px = p.x;
        py = p.y;
        p.x += Math.cos(a) * cfg.speed;
        p.y += Math.sin(a) * cfg.speed;
        const mx = (px + p.x) / 2;
        const my = (py + p.y) / 2;
        mctx.quadraticCurveTo(px, py, mx, my);
      }
      mctx.lineTo(p.x, p.y);
      mctx.stroke();
      p.life -= cfg.stepsPerStroke;
    };

    const step = () => {
      if (ready) {
        mctx.globalCompositeOperation = "destination-out";
        mctx.fillStyle = `rgba(0,0,0,${cfg.fade})`;
        mctx.fillRect(0, 0, w, h);

        mctx.globalCompositeOperation = "source-over";
        mctx.strokeStyle = `rgba(255,255,255,${cfg.strokeAlpha})`;
        mctx.lineWidth = cfg.line;
        mctx.lineCap = "round";
        mctx.lineJoin = "round";

        for (const p of tracers) {
          drawSmoothStroke(p);
          if (p.life <= 0 || p.x < -40 || p.x > w + 40 || p.y < -40 || p.y > h + 40) {
            Object.assign(p, spawnRandom());
          }
        }

        ctx.clearRect(0, 0, w, h);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = cfg.brightness;
        drawCover(ctx);
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "destination-in";
        ctx.filter = `blur(${cfg.blur}px)`;
        ctx.drawImage(mask, 0, 0, w, h);
        ctx.filter = "none";
        ctx.globalCompositeOperation = "source-over";
      }
      t += 0.00075;
      raf = requestAnimationFrame(step);
    };

    resize();
    window.addEventListener("resize", resize);

    if (reduce) {
      const settle = setInterval(() => {
        if (ready) {
          for (let i = 0; i < 900; i++) step();
          cancelAnimationFrame(raf);
          clearInterval(settle);
        }
      }, 100);
      return () => {
        clearInterval(settle);
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", resize);
      };
    }

    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [variant]);

  const overlay =
    variant === "results"
      ? "radial-gradient(120% 90% at 50% 45%, transparent 45%, rgba(10,10,11,0.7) 100%)"
      : "radial-gradient(120% 85% at 50% 42%, transparent 35%, rgba(10,10,11,0.45) 70%, rgba(10,10,11,0.75) 100%)";

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[var(--bg)]" aria-hidden>
      <canvas ref={ref} className="absolute inset-0 h-full w-full" />
      <div className="absolute inset-0" style={{ background: overlay }} />
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";

/**
 * Black canvas with a Van Gogh painting hidden underneath, revealed only along
 * thin animated lines that drift across the screen (a flow field used as a mask,
 * not as visible strokes). Reveals slowly fade back to black, so the painting
 * shimmers through in shifting traces. Subtle, clean, text-friendly.
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

    const cfg =
      variant === "results"
        ? { tracers: 70, fade: 0.018, line: 1.4, brightness: 0.5, scale: 0.0016 }
        : { tracers: 110, fade: 0.015, line: 1.6, brightness: 0.72, scale: 0.0018 };

    // offscreen mask: white where the painting is revealed, decays over time
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
    type P = { x: number; y: number; px: number; py: number; life: number };
    let tracers: P[] = [];
    let t = 0;
    let raf = 0;

    const spawn = (): P => {
      const x = Math.random() * w;
      const y = Math.random() * h;
      return { x, y, px: x, py: y, life: 60 + Math.random() * 200 };
    };

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = mask.width = Math.floor(w * dpr);
      canvas.height = mask.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      mctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(cfg.tracers, Math.floor((w * h) / 12000));
      tracers = Array.from({ length: count }, spawn);
    };

    // cover-fit the painting into the canvas
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

    const angleAt = (x: number, y: number) =>
      vnoise(x * cfg.scale + t * 0.12, y * cfg.scale) * Math.PI * 3 +
      vnoise(x * cfg.scale * 2.0, y * cfg.scale * 2.0 + t * 0.1) * Math.PI;

    const step = () => {
      if (ready) {
        // 1) decay the mask slightly
        mctx.globalCompositeOperation = "destination-out";
        mctx.fillStyle = `rgba(0,0,0,${cfg.fade})`;
        mctx.fillRect(0, 0, w, h);

        // 2) draw new reveal lines onto the mask
        mctx.globalCompositeOperation = "source-over";
        mctx.strokeStyle = "rgba(255,255,255,0.9)";
        mctx.lineWidth = cfg.line;
        mctx.lineCap = "round";
        for (const p of tracers) {
          const a = angleAt(p.x, p.y);
          p.px = p.x;
          p.py = p.y;
          p.x += Math.cos(a) * 1.3;
          p.y += Math.sin(a) * 1.3;
          p.life -= 1;
          mctx.beginPath();
          mctx.moveTo(p.px, p.py);
          mctx.lineTo(p.x, p.y);
          mctx.stroke();
          if (p.life <= 0 || p.x < -20 || p.x > w + 20 || p.y < -20 || p.y > h + 20) {
            Object.assign(p, spawn());
          }
        }

        // 3) composite painting through the mask onto the (black) canvas
        ctx.clearRect(0, 0, w, h);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = cfg.brightness;
        drawCover(ctx);
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "destination-in";
        ctx.drawImage(mask, 0, 0, w, h);
        ctx.globalCompositeOperation = "source-over";
      }
      t += 0.0025;
      raf = requestAnimationFrame(step);
    };

    resize();
    window.addEventListener("resize", resize);

    if (reduce) {
      // one settled frame: paint many reveal lines, then composite once
      const settle = setInterval(() => {
        if (ready) {
          for (let i = 0; i < 1500; i++) step();
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

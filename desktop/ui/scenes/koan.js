// koan.js — KOAN theme scene: a raked sand garden with a brushed enso ring.
//
// Ported value-for-value from helloim-v4's src/scenes/koan.ts — see
// renderer/lib/scene.js's header for the port rationale.
//
// Warm paper, almost no colour, extremely slow. The calm one: idle is a
// barely-perceptible drift in the rake lines, speech ripples them outward.

import { createScene, fillFrame } from './lib/faceScene.js';

export function mount(canvas) {
  return createScene(canvas, (s) => {
    let stones = [];

    const layout = () => {
      stones = [
        { x: s.w * 0.28, y: s.h * 0.62, r: Math.min(s.w, s.h) * 0.045 },
        { x: s.w * 0.72, y: s.h * 0.38, r: Math.min(s.w, s.h) * 0.03 },
        { x: s.w * 0.6, y: s.h * 0.74, r: Math.min(s.w, s.h) * 0.022 },
      ];
    };

    return {
      layout,
      draw: (st) => {
        const ctx = st.ctx;
        fillFrame(st, '#171512');

        // paper wash
        const g = ctx.createRadialGradient(st.w * 0.5, st.h * 0.45, 0, st.w * 0.5, st.h * 0.5, Math.max(st.w, st.h) * 0.75);
        g.addColorStop(0, '#26221c');
        g.addColorStop(1, '#100f0d');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, st.w, st.h);

        // raked sand: concentric lines around each stone, drifting slowly
        ctx.save();
        ctx.lineWidth = 1.1;
        for (const stone of stones) {
          for (let i = 1; i < 16; i++) {
            const base = stone.r + i * Math.min(st.w, st.h) * 0.028;
            const ripple = Math.sin(st.t * 0.7 - i * 0.55) * (1.2 + st.level * 9);
            ctx.strokeStyle = `rgba(214,203,180,${0.11 - i * 0.005 + st.level * 0.05})`;
            ctx.beginPath();
            ctx.arc(stone.x, stone.y, base + ripple, 0, Math.PI * 2);
            ctx.stroke();
          }
        }
        // long straight rake lines across the open sand
        for (let y = 0; y < st.h; y += Math.max(16, st.h / 26)) {
          ctx.strokeStyle = `rgba(214,203,180,${0.05 + st.level * 0.03})`;
          ctx.beginPath();
          for (let x = 0; x <= st.w; x += 12) {
            const yy = y + Math.sin(x * 0.006 + st.t * 0.25) * (2 + st.level * 5);
            if (x === 0) ctx.moveTo(x, yy);
            else ctx.lineTo(x, yy);
          }
          ctx.stroke();
        }
        ctx.restore();

        // stones
        for (const stone of stones) {
          const sg = ctx.createRadialGradient(
            stone.x - stone.r * 0.3,
            stone.y - stone.r * 0.4,
            stone.r * 0.1,
            stone.x,
            stone.y,
            stone.r
          );
          sg.addColorStop(0, '#4a463f');
          sg.addColorStop(1, '#1c1a17');
          ctx.fillStyle = sg;
          ctx.beginPath();
          ctx.ellipse(stone.x, stone.y, stone.r, stone.r * 0.82, 0.3, 0, Math.PI * 2);
          ctx.fill();
        }

        // the enso — one brushed circle, opening slightly as it speaks
        const cx = st.w / 2;
        const cy = st.h * 0.44;
        const R = Math.min(st.w, st.h) * 0.2;
        const gap = 0.5 - st.level * 0.3;
        ctx.save();
        ctx.lineCap = 'round';
        for (let pass = 0; pass < 3; pass++) {
          ctx.strokeStyle = `rgba(245,238,224,${(0.1 + st.level * 0.28) / (pass + 1)})`;
          ctx.lineWidth = (10 - pass * 3) * (1 + st.level * 0.35);
          ctx.beginPath();
          ctx.arc(cx, cy, R + pass * 1.4, -0.4 + gap, Math.PI * 2 - 0.4, false);
          ctx.stroke();
        }
        ctx.restore();

        // breath dot at the centre — never stops moving, even at idle
        const breath = 0.5 + Math.sin(st.t * 0.5) * 0.5;
        ctx.fillStyle = `rgba(245,238,224,${0.18 + breath * 0.2 + st.level * 0.3})`;
        ctx.beginPath();
        ctx.arc(cx, cy, 3 + breath * 3 + st.level * 8, 0, Math.PI * 2);
        ctx.fill();

        if (st.listening) {
          const p = (st.t % 3) / 3;
          ctx.strokeStyle = `rgba(245,238,224,${(1 - p) * 0.2})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(cx, cy, R * (0.3 + p * 1.6), 0, Math.PI * 2);
          ctx.stroke();
        }

        if (st.ping > 0.01) {
          ctx.strokeStyle = st.flareSign < 0 ? `rgba(190,80,60,${st.ping * 0.4})` : `rgba(245,238,224,${st.ping * 0.3})`;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(cx, cy, R * (1 + (1 - st.ping) * 2), 0, Math.PI * 2);
          ctx.stroke();
        }
      },
    };
  });
}


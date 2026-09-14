// noir.js — NOIR theme scene: rain on an office window, venetian blind light.
//
// Ported value-for-value from helloim-v4's src/scenes/noir.ts — see
// renderer/lib/scene.js's header for the port rationale.
//
// Vertical, monochrome-with-amber, grainy. Idle is heavy rain and a slow
// curl of cigarette smoke; speech brightens the slats like a passing car.

import { createScene, fillFrame, rnd } from './lib/faceScene.js';

export function mount(canvas) {
  return createScene(canvas, (s) => {
    let drops = [];
    let flash = 0;
    let nextFlash = 5;

    const layout = () => {
      const n = Math.round((s.w * s.h) / 2600);
      drops = new Array(n);
      for (let i = 0; i < n; i++) {
        drops[i] = {
          x: Math.random() * s.w,
          y: Math.random() * s.h,
          len: rnd(10, 34),
          sp: rnd(420, 980),
          a: rnd(0.05, 0.2),
        };
      }
    };

    return {
      layout,
      onFlare: () => {
        flash = 1;
      },
      draw: (st) => {
        const ctx = st.ctx;
        fillFrame(st, '#07070a');

        // window light pooling in from the left
        const g = ctx.createLinearGradient(0, 0, st.w, st.h);
        g.addColorStop(0, `rgba(226,190,120,${0.10 + st.level * 0.14})`);
        g.addColorStop(0.45, 'rgba(60,55,60,0.05)');
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, st.w, st.h);

        if (st.t > nextFlash) {
          flash = 1;
          nextFlash = st.t + 7 + Math.random() * 11;
        }
        flash = Math.max(0, flash - st.dt * 2.2);

        // venetian blind slats — the structure of the scene
        const slat = Math.max(18, st.h / 22);
        const skew = st.w * 0.12;
        ctx.save();
        for (let y = -slat; y < st.h + slat; y += slat) {
          const lit =
            0.06 +
            Math.max(0, Math.sin(y * 0.02 + st.t * 0.5)) * 0.05 +
            st.level * 0.18 +
            flash * 0.35;
          ctx.fillStyle = `rgba(232,198,132,${lit})`;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(st.w, y - skew * 0.2);
          ctx.lineTo(st.w, y - skew * 0.2 + slat * 0.46);
          ctx.lineTo(0, y + slat * 0.46);
          ctx.closePath();
          ctx.fill();
        }
        ctx.restore();

        // rain
        ctx.save();
        ctx.strokeStyle = 'rgba(210,220,235,1)';
        ctx.lineWidth = 1;
        for (const d of drops) {
          d.y += d.sp * st.dt;
          d.x += 40 * st.dt;
          if (d.y > st.h) {
            d.y = -d.len;
            d.x = Math.random() * st.w;
          }
          if (d.x > st.w) d.x = 0;
          ctx.globalAlpha = d.a + st.level * 0.12;
          ctx.beginPath();
          ctx.moveTo(d.x, d.y);
          ctx.lineTo(d.x - 3, d.y + d.len);
          ctx.stroke();
        }
        ctx.restore();

        // cigarette smoke — one slow curl, always moving even at idle
        ctx.save();
        ctx.globalCompositeOperation = 'lighter';
        ctx.strokeStyle = `rgba(220,215,205,${0.05 + st.level * 0.06})`;
        ctx.lineWidth = 26;
        ctx.lineCap = 'round';
        for (let k = 0; k < 2; k++) {
          ctx.beginPath();
          const bx = st.w * (0.72 + k * 0.1);
          ctx.moveTo(bx, st.h);
          for (let i = 1; i <= 10; i++) {
            const p = i / 10;
            ctx.lineTo(
              bx + Math.sin(st.t * 0.5 + p * 4 + k) * 40 * p,
              st.h - p * st.h * 0.85
            );
          }
          ctx.stroke();
        }
        ctx.restore();

        // film grain
        ctx.save();
        ctx.globalAlpha = 0.05;
        for (let i = 0; i < 320; i++) {
          ctx.fillStyle = Math.random() > 0.5 ? '#ffffff' : '#000000';
          ctx.fillRect(Math.random() * st.w, Math.random() * st.h, 1.5, 1.5);
        }
        ctx.restore();

        // vignette
        const v = ctx.createRadialGradient(st.w / 2, st.h / 2, Math.min(st.w, st.h) * 0.2, st.w / 2, st.h / 2, Math.max(st.w, st.h) * 0.75);
        v.addColorStop(0, 'rgba(0,0,0,0)');
        v.addColorStop(1, 'rgba(0,0,0,0.8)');
        ctx.fillStyle = v;
        ctx.fillRect(0, 0, st.w, st.h);

        if (st.ping > 0.01) {
          ctx.fillStyle = st.flareSign < 0 ? `rgba(180,30,30,${st.ping * 0.25})` : `rgba(232,198,132,${st.ping * 0.2})`;
          ctx.fillRect(0, 0, st.w, st.h);
        }
      },
    };
  });
}


// capcom.js — CAPCOM theme scene: a mission control telemetry wall.
//
// Ported value-for-value from helloim-v4's src/scenes/capcom.ts — see
// renderer/lib/scene.js's header for the port rationale.
//
// Fine graph paper, three scrolling traces, an orbit plot and a countdown.
// Idle is a steady heartbeat on the plots; thinking widens the noise band;
// speech drives the primary trace.

import { createScene, fillFrame } from './lib/faceScene.js';

export function mount(canvas) {
  return createScene(canvas, (s) => {
    let hist = [[], [], []];
    let cap = 240;
    let acc = 0;

    const layout = () => {
      cap = Math.max(120, Math.round(s.w / 2));
      hist = [[], [], []];
    };

    return {
      layout,
      draw: (st) => {
        const ctx = st.ctx;
        fillFrame(st, '#03080e');

        // graph paper
        ctx.save();
        ctx.strokeStyle = 'rgba(90,180,220,0.06)';
        ctx.lineWidth = 1;
        const g = 22;
        ctx.beginPath();
        for (let x = 0; x < st.w; x += g) {
          ctx.moveTo(x, 0);
          ctx.lineTo(x, st.h);
        }
        for (let y = 0; y < st.h; y += g) {
          ctx.moveTo(0, y);
          ctx.lineTo(st.w, y);
        }
        ctx.stroke();
        ctx.restore();

        // sample the telemetry at a fixed rate
        acc += st.dt;
        while (acc > 1 / 60) {
          acc -= 1 / 60;
          const noise = st.mode === 'thinking' ? 0.28 : 0.08;
          hist[0].push(st.level * 0.9 + (Math.random() - 0.5) * noise);
          hist[1].push(Math.sin(st.t * 1.7) * 0.35 + (Math.random() - 0.5) * noise * 0.6);
          hist[2].push(Math.sin(st.t * 0.6 + 1.2) * 0.22 + st.level * 0.25);
          for (const h of hist) if (h.length > cap) h.shift();
        }

        const colors = ['rgba(255,190,90,0.95)', 'rgba(90,220,255,0.8)', 'rgba(140,255,180,0.7)'];
        const laneH = st.h / 3.4;
        for (let k = 0; k < 3; k++) {
          const baseY = laneH * (k + 0.6);
          // lane baseline
          ctx.strokeStyle = 'rgba(120,200,240,0.14)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(0, baseY);
          ctx.lineTo(st.w, baseY);
          ctx.stroke();

          ctx.strokeStyle = colors[k];
          ctx.lineWidth = k === 0 ? 1.8 : 1.2;
          ctx.beginPath();
          const h = hist[k];
          for (let i = 0; i < h.length; i++) {
            const x = (i / cap) * st.w;
            const y = baseY - h[i] * laneH * 0.45;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.stroke();

          // live head marker
          if (h.length) {
            const x = ((h.length - 1) / cap) * st.w;
            const y = baseY - h[h.length - 1] * laneH * 0.45;
            ctx.fillStyle = colors[k];
            ctx.beginPath();
            ctx.arc(x, y, 2.5, 0, Math.PI * 2);
            ctx.fill();
          }

          ctx.fillStyle = 'rgba(150,200,225,0.5)';
          ctx.font = '10px ui-monospace, Menlo, monospace';
          ctx.textAlign = 'left';
          ctx.fillText(['VOX', 'ATT', 'PWR'][k], 10, baseY - laneH * 0.42);
        }

        // orbit plot, bottom right
        const ox = st.w - Math.min(140, st.w * 0.22);
        const oy = st.h - Math.min(120, st.h * 0.24);
        const orad = Math.min(70, st.w * 0.09);
        ctx.strokeStyle = 'rgba(120,200,240,0.25)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.ellipse(ox, oy, orad, orad * 0.55, -0.3, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = 'rgba(90,150,190,0.35)';
        ctx.beginPath();
        ctx.arc(ox, oy, orad * 0.22, 0, Math.PI * 2);
        ctx.fill();
        const ang = st.t * (0.5 + st.level * 1.5);
        const px = ox + Math.cos(ang) * orad * Math.cos(-0.3) - Math.sin(ang) * orad * 0.55 * Math.sin(-0.3);
        const py = oy + Math.cos(ang) * orad * Math.sin(-0.3) + Math.sin(ang) * orad * 0.55 * Math.cos(-0.3);
        ctx.fillStyle = 'rgba(255,200,110,1)';
        ctx.beginPath();
        ctx.arc(px, py, 3.5, 0, Math.PI * 2);
        ctx.fill();

        // status strip
        ctx.fillStyle = 'rgba(3,8,14,0.85)';
        ctx.fillRect(0, 0, st.w, 22);
        ctx.fillStyle = 'rgba(255,190,90,0.9)';
        ctx.font = '11px ui-monospace, Menlo, monospace';
        ctx.textAlign = 'left';
        const state =
          st.mode === 'thinking' ? 'COMPUTING' : st.mode === 'talking' ? 'DOWNLINK ACTIVE' : st.listening ? 'UPLINK OPEN' : 'NOMINAL';
        const mins = String(Math.floor(st.t / 60)).padStart(2, '0');
        const secs = String(Math.floor(st.t % 60)).padStart(2, '0');
        ctx.fillText(`MET 00:${mins}:${secs}   ·   ${state}`, 10, 15);
        ctx.textAlign = 'right';
        ctx.fillStyle = st.flareSign < 0 ? 'rgba(255,80,70,0.95)' : 'rgba(120,220,255,0.7)';
        ctx.fillText(st.flareSign < 0 ? 'CAUTION & WARNING' : 'ALL SYSTEMS GO', st.w - 10, 15);

        if (st.ping > 0.01) {
          ctx.fillStyle = st.flareSign < 0 ? `rgba(255,50,40,${st.ping * 0.18})` : `rgba(120,220,255,${st.ping * 0.12})`;
          ctx.fillRect(0, 0, st.w, st.h);
        }
      },
    };
  });
}


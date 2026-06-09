"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { GraphData } from "@/lib/api";

// Force-directed (gravity + spring + repulsion) graph. Drag a node to feel the network react.
// Deliberately hand-rolled — keeps the bundle dep-free; for the doc-keyword graph (N≤~50)
// the O(N²) repulsion pass is well under one frame.

interface Sim {
  id: string;
  label: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  /** When set (drag), the node is pinned to (x, y) and excluded from integration. */
  fixed: boolean;
}

const W = 360;
const H = 360;
const CENTER = { x: W / 2, y: H / 2 };

// Tuned for legible motion on N≈10–50 keyword graphs at 60fps.
const REPULSION = 1800; // node-node Coulomb-ish constant
const SPRING_K = 0.04; // edge spring stiffness
const SPRING_L = 70; // edge rest length (px)
const GRAVITY = 0.012; // pull toward center
const DAMPING = 0.86; // velocity friction per tick
const DT = 1; // we run at rAF rate; energies tuned for unitless dt=1
const KE_REST = 0.08; // kinetic-energy floor below which we pause the loop

export function ForceGraph({ graph }: { graph: GraphData }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const simRef = useRef<Sim[]>([]);
  const edgesRef = useRef(graph.edges);
  const maxWRef = useRef(1);
  const rafRef = useRef<number | null>(null);
  const dragRef = useRef<{ id: string; ox: number; oy: number } | null>(null);
  const [, force] = useState(0); // re-render trigger after each tick

  // (Re)initialise the simulation when the graph data changes.
  useMemo(() => {
    edgesRef.current = graph.edges;
    maxWRef.current = Math.max(1, ...graph.edges.map((e) => e.weight));
    // Seed positions on a jittered ring so the layout converges deterministically.
    const N = graph.nodes.length;
    simRef.current = graph.nodes.map((n, i) => {
      const a = (2 * Math.PI * i) / Math.max(1, N) - Math.PI / 2;
      const r = 110 + (i % 3) * 15;
      return {
        id: n.id,
        label: n.label,
        x: CENTER.x + r * Math.cos(a) + (Math.random() - 0.5) * 14,
        y: CENTER.y + r * Math.sin(a) + (Math.random() - 0.5) * 14,
        vx: 0,
        vy: 0,
        fixed: false,
      };
    });
  }, [graph]);

  useEffect(() => {
    function tick() {
      const sim = simRef.current;
      const edges = edgesRef.current;
      const maxW = maxWRef.current;
      const N = sim.length;

      // Reset accumulator forces by stepping velocities directly (no separate ax/ay needed).
      // Pairwise repulsion (O(N²); N is small).
      for (let i = 0; i < N; i++) {
        for (let j = i + 1; j < N; j++) {
          const a = sim[i];
          const b = sim[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) {
            // Coincident jitter — nudge apart deterministically.
            dx = 0.5;
            dy = 0.5;
            d2 = 0.5;
          }
          const inv = REPULSION / (d2 * Math.sqrt(d2));
          const fx = dx * inv;
          const fy = dy * inv;
          if (!a.fixed) {
            a.vx -= fx * DT;
            a.vy -= fy * DT;
          }
          if (!b.fixed) {
            b.vx += fx * DT;
            b.vy += fy * DT;
          }
        }
      }

      // Edge springs.
      const indexById = new Map<string, number>();
      sim.forEach((s, i) => indexById.set(s.id, i));
      for (const e of edges) {
        const i = indexById.get(e.source);
        const j = indexById.get(e.target);
        if (i == null || j == null) continue;
        const a = sim[i];
        const b = sim[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const stiffness = SPRING_K * (0.5 + 0.5 * (e.weight / maxW));
        const displacement = dist - SPRING_L;
        const fx = (dx / dist) * displacement * stiffness;
        const fy = (dy / dist) * displacement * stiffness;
        if (!a.fixed) {
          a.vx += fx * DT;
          a.vy += fy * DT;
        }
        if (!b.fixed) {
          b.vx -= fx * DT;
          b.vy -= fy * DT;
        }
      }

      // Center gravity + damping + integration + bounds.
      let ke = 0;
      for (const s of sim) {
        if (s.fixed) {
          s.vx = 0;
          s.vy = 0;
          continue;
        }
        s.vx += (CENTER.x - s.x) * GRAVITY * DT;
        s.vy += (CENTER.y - s.y) * GRAVITY * DT;
        s.vx *= DAMPING;
        s.vy *= DAMPING;
        s.x += s.vx * DT;
        s.y += s.vy * DT;
        if (s.x < 18) {
          s.x = 18;
          s.vx *= -0.5;
        }
        if (s.x > W - 18) {
          s.x = W - 18;
          s.vx *= -0.5;
        }
        if (s.y < 18) {
          s.y = 18;
          s.vy *= -0.5;
        }
        if (s.y > H - 18) {
          s.y = H - 18;
          s.vy *= -0.5;
        }
        ke += s.vx * s.vx + s.vy * s.vy;
      }

      force((n) => (n + 1) & 0xffff);
      // Keep looping while moving, OR while a drag is active (so the user always sees response).
      if (ke > KE_REST || dragRef.current) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        rafRef.current = null;
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [graph]);

  function svgPoint(e: React.PointerEvent<SVGElement>): { x: number; y: number } {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }

  function onPointerDown(e: React.PointerEvent<SVGElement>, id: string) {
    const node = simRef.current.find((s) => s.id === id);
    if (!node) return;
    const { x, y } = svgPoint(e);
    node.fixed = true;
    dragRef.current = { id, ox: x - node.x, oy: y - node.y };
    (e.target as Element).setPointerCapture?.(e.pointerId);
    if (rafRef.current == null) {
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
      });
      // Re-arm the simulation loop.
      const loop = () => {
        // Trigger a re-render which re-enters the useEffect tick? No — useEffect's tick is
        // already self-arming via rAF when motion exists; we just need to nudge it.
        force((n) => (n + 1) & 0xffff);
      };
      loop();
    }
  }

  function onPointerMove(e: React.PointerEvent<SVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const node = simRef.current.find((s) => s.id === drag.id);
    if (!node) return;
    const { x, y } = svgPoint(e);
    node.x = x - drag.ox;
    node.y = y - drag.oy;
    node.vx = 0;
    node.vy = 0;
  }

  function onPointerUp(e: React.PointerEvent<SVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const node = simRef.current.find((s) => s.id === drag.id);
    if (node) node.fixed = false;
    dragRef.current = null;
    (e.target as Element).releasePointerCapture?.(e.pointerId);
  }

  if (graph.nodes.length === 0) {
    return <p className="pane-placeholder">그래프 없음 / no graph</p>;
  }

  const sim = simRef.current;
  const indexById = new Map<string, Sim>();
  sim.forEach((s) => indexById.set(s.id, s));

  return (
    <svg
      ref={svgRef}
      className="kw-graph force-graph"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="force-directed keyword graph"
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
    >
      {graph.edges.map((e, i) => {
        const a = indexById.get(e.source);
        const b = indexById.get(e.target);
        if (!a || !b) return null;
        const op = 0.2 + 0.6 * (e.weight / maxWRef.current);
        const w = 1 + 2 * (e.weight / maxWRef.current);
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="#9bbcf5"
            strokeOpacity={op}
            strokeWidth={w}
          />
        );
      })}
      {sim.map((s) => (
        <g
          key={s.id}
          onPointerDown={(e) => onPointerDown(e, s.id)}
          style={{ cursor: dragRef.current?.id === s.id ? "grabbing" : "grab" }}
        >
          <circle cx={s.x} cy={s.y} r={6} fill="#007bff" stroke="#ffffff" strokeWidth={1.5} />
          <text
            x={s.x}
            y={s.y - 10}
            textAnchor="middle"
            fontSize="10"
            fontWeight="500"
            fill="#3d5170"
            style={{ pointerEvents: "none", userSelect: "none" }}
          >
            {s.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

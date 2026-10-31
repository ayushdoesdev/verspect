"use client";

import { useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  FadeIn,
  Section,
  WindowChrome,
} from "@/components/marketing/landing/primitives";

type Node = {
  id: string;
  label: string;
  x: number;
  y: number;
  kind: "root" | "direct" | "transitive" | "vuln";
};

const nodes: Node[] = [
  { id: "app", label: "payments-api", x: 280, y: 160, kind: "root" },
  { id: "django", label: "django", x: 120, y: 70, kind: "direct" },
  { id: "celery", label: "celery", x: 440, y: 70, kind: "direct" },
  { id: "pydantic", label: "pydantic", x: 90, y: 220, kind: "vuln" },
  { id: "requests", label: "requests", x: 470, y: 220, kind: "direct" },
  { id: "urllib3", label: "urllib3", x: 520, y: 300, kind: "transitive" },
  { id: "sqlalchemy", label: "sqlalchemy", x: 280, y: 300, kind: "direct" },
  { id: "greenlet", label: "greenlet", x: 200, y: 360, kind: "transitive" },
];

const edges: Array<[string, string]> = [
  ["app", "django"],
  ["app", "celery"],
  ["app", "pydantic"],
  ["app", "requests"],
  ["app", "sqlalchemy"],
  ["requests", "urllib3"],
  ["sqlalchemy", "greenlet"],
  ["celery", "requests"],
];

const kindStyle: Record<Node["kind"], { fill: string; ring: string; text: string }> = {
  root: { fill: "#3dd6c6", ring: "rgba(61,214,198,0.45)", text: "#04201c" },
  direct: { fill: "#1a2433", ring: "rgba(255,255,255,0.16)", text: "#e8eef6" },
  transitive: { fill: "#121a24", ring: "rgba(255,255,255,0.10)", text: "#8b9bb0" },
  vuln: { fill: "#3a1a1d", ring: "rgba(240,113,120,0.45)", text: "#f07178" },
};

export function DependencyGraphSection() {
  const reduce = useReducedMotion();
  const [active, setActive] = useState<string | null>("pydantic");
  const byId = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), []);

  const connected = useMemo(() => {
    if (!active) return new Set<string>();
    const set = new Set<string>([active]);
    edges.forEach(([a, b]) => {
      if (a === active || b === active) {
        set.add(a);
        set.add(b);
      }
    });
    return set;
  }, [active]);

  return (
    <Section
      id="graph"
      eyebrow="Dependency Graph"
      title="See how risk travels through your tree."
      description="Explore this illustrative dependency graph: select a package to highlight its immediate relationships and inspect an example risk signal."
    >
      <FadeIn>
        <WindowChrome
          title="dependency graph · interactive"
          trailing={
            <div className="hidden gap-3 text-[10px] text-slate-500 sm:flex">
              <Legend color="#3dd6c6" label="root" />
              <Legend color="#8b9bb0" label="direct" />
              <Legend color="#f07178" label="vulnerable" />
            </div>
          }
        >
          <div className="relative overflow-hidden bg-[#070b12]">
            <svg
              viewBox="0 0 560 420"
              className="h-auto w-full max-h-[420px]"
              role="img"
              aria-label="Interactive dependency graph"
            >
              {edges.map(([a, b], i) => {
                const na = byId[a];
                const nb = byId[b];
                const lit =
                  !active || (connected.has(a) && connected.has(b));
                return (
                  <motion.line
                    key={`${a}-${b}`}
                    x1={na.x}
                    y1={na.y}
                    x2={nb.x}
                    y2={nb.y}
                    stroke={lit ? "rgba(61,214,198,0.35)" : "rgba(255,255,255,0.06)"}
                    strokeWidth={lit ? 1.6 : 1}
                    initial={reduce ? false : { opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6, delay: i * 0.04 }}
                  />
                );
              })}
              {nodes.map((n, i) => {
                const style = kindStyle[n.kind];
                const lit = !active || connected.has(n.id);
                return (
                  <g
                    key={n.id}
                    className="cursor-pointer"
                    onMouseEnter={() => setActive(n.id)}
                    onMouseLeave={() => setActive("pydantic")}
                    onFocus={() => setActive(n.id)}
                    onBlur={() => setActive("pydantic")}
                    tabIndex={0}
                    role="button"
                    aria-label={n.label}
                  >
                    <motion.circle
                      cx={n.x}
                      cy={n.y}
                      r={n.kind === "root" ? 28 : 22}
                      fill={style.fill}
                      stroke={style.ring}
                      strokeWidth={2}
                      initial={reduce ? false : { scale: 0, opacity: 0 }}
                      whileInView={{ scale: 1, opacity: lit ? 1 : 0.28 }}
                      viewport={{ once: true }}
                      animate={{ opacity: lit ? 1 : 0.28, scale: active === n.id ? 1.08 : 1 }}
                      transition={{ duration: 0.35, delay: i * 0.04 }}
                    />
                    <text
                      x={n.x}
                      y={n.y + 4}
                      textAnchor="middle"
                      fill={style.text}
                      fontSize="10"
                      fontFamily="IBM Plex Mono, monospace"
                      style={{ pointerEvents: "none" }}
                    >
                      {n.label}
                    </text>
                  </g>
                );
              })}
            </svg>
            {active && (
              <div className="pointer-events-none absolute bottom-4 left-4 rounded-xl border border-white/10 bg-[#0a1018]/90 px-3 py-2 backdrop-blur">
                <div className="font-mono text-xs text-white">{byId[active].label}</div>
                <div className="mt-0.5 text-[11px] text-slate-500">
                  {byId[active].kind === "vuln"
                    ? "CVE-linked · upgrade recommended"
                    : byId[active].kind === "root"
                      ? "Repository root"
                      : `${byId[active].kind} dependency`}
                </div>
              </div>
            )}
          </div>
        </WindowChrome>
      </FadeIn>
    </Section>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Sparkles } from "lucide-react";
import {
  FadeIn,
  ProgressBar,
  Section,
  WindowChrome,
} from "@/components/marketing/landing/primitives";

const beforeCode = `from django.conf.urls import url
from django.utils.translation import ugettext_lazy as _

urlpatterns = [
    url(r'^health/$', views.health),
]`;

const afterCode = `from django.urls import re_path
from django.utils.translation import gettext_lazy as _

urlpatterns = [
    re_path(r'^health/$', views.health),
]`;

const analysisSteps = [
  "Parsing AST usages…",
  "Matching migration rules…",
  "Generating exact patches…",
  "Scoring confidence…",
];

export function MigrationDemoSection() {
  const reduce = useReducedMotion();
  const [step, setStep] = useState(0);
  const [showDiff, setShowDiff] = useState(!!reduce);
  const [confidence, setConfidence] = useState(reduce ? 94 : 0);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => {
      setStep((s) => {
        const next = (s + 1) % (analysisSteps.length + 2);
        if (next >= analysisSteps.length) {
          setShowDiff(true);
          setConfidence(94);
        } else {
          setShowDiff(false);
          setConfidence(20 + next * 22);
        }
        return next;
      });
    }, 1600);
    return () => window.clearInterval(id);
  }, [reduce]);

  return (
    <Section
      id="migration"
      eyebrow="AI Migration Assistant"
      title="Reviewable migration diffs. Evidence you can inspect."
      description="Explore an illustrative before-and-after migration diff. Verspect combines structured migration knowledge with optional AI-assisted suggestions; review and test every proposed change."
    >
      <FadeIn>
        <WindowChrome
          title="ai migration assistant · django urls"
          trailing={
            <span className="inline-flex items-center gap-1 rounded-full bg-teal-400/10 px-2 py-0.5 font-mono text-[10px] text-teal-300 ring-1 ring-teal-400/25">
              <Sparkles className="h-3 w-3" /> Example
            </span>
          }
        >
          <div className="grid gap-0 lg:grid-cols-2">
            <div className="border-b border-white/[0.06] p-4 lg:border-b-0 lg:border-r">
              <div className="mb-2 text-[11px] uppercase tracking-wider text-slate-500">
                Before
              </div>
              <CodeBlock code={beforeCode} tone="rose" />
              <div className="mt-4 space-y-2">
                <div className="text-[11px] uppercase tracking-wider text-slate-500">
                  AI analysis
                </div>
                <div className="space-y-1.5 font-mono text-[12px] text-slate-400">
                  {analysisSteps.map((line, i) => (
                    <div
                      key={line}
                      className={`flex items-center gap-2 transition ${
                        i <= step ? "text-slate-200" : "text-slate-600"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          i < step
                            ? "bg-emerald-400"
                            : i === step
                              ? "animate-pulse bg-teal-300"
                              : "bg-white/10"
                        }`}
                      />
                      {line}
                    </div>
                  ))}
                </div>
                <div className="pt-2">
                  <div className="mb-1 flex justify-between text-[11px] text-slate-500">
                    <span>Confidence</span>
                    <span className="font-mono text-teal-300">{confidence}%</span>
                  </div>
                  <ProgressBar value={confidence} />
                </div>
              </div>
            </div>

            <div className="p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-[11px] uppercase tracking-wider text-slate-500">
                  Example patch
                </div>
                <div className="font-mono text-[10px] text-slate-500">
                  side-by-side diff
                </div>
              </div>
              <AnimatePresence mode="wait">
                {showDiff ? (
                  <motion.div
                    key="diff"
                    initial={reduce ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-3"
                  >
                    <DiffLines />
                    <CodeBlock code={afterCode} tone="teal" />
                  </motion.div>
                ) : (
                  <motion.div
                    key="waiting"
                    initial={reduce ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex h-[280px] items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.02]"
                  >
                    <div className="text-center">
                      <Sparkles className="mx-auto h-5 w-5 animate-pulse text-teal-300/70" />
                      <p className="mt-2 text-sm text-slate-500">
                        Generating patch from AST match…
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </WindowChrome>
      </FadeIn>
    </Section>
  );
}

function CodeBlock({ code, tone }: { code: string; tone: "rose" | "teal" }) {
  const border =
    tone === "teal" ? "border-teal-400/20 bg-teal-400/[0.04]" : "border-white/10 bg-secondary/40";
  return (
    <pre
      className={`overflow-x-auto rounded-xl border p-3 font-mono text-[11px] leading-5 text-slate-300 ${border}`}
    >
      {code}
    </pre>
  );
}

function DiffLines() {
  const rows = [
    { type: "del", text: "- from django.conf.urls import url" },
    { type: "add", text: "+ from django.urls import re_path" },
    { type: "del", text: "- from django.utils.translation import ugettext_lazy as _" },
    { type: "add", text: "+ from django.utils.translation import gettext_lazy as _" },
    { type: "del", text: "-     url(r'^health/$', views.health)," },
    { type: "add", text: "+     re_path(r'^health/$', views.health)," },
  ];
  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-[#080d14] font-mono text-[11px] leading-5">
      {rows.map((r, i) => (
        <motion.div
          key={`${r.type}-${i}`}
          initial={{ opacity: 0, x: r.type === "add" ? 8 : -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
          className={`px-3 py-0.5 ${
            r.type === "add"
              ? "bg-emerald-400/[0.08] text-emerald-200"
              : "bg-rose-400/[0.08] text-rose-200"
          }`}
        >
          {r.text}
        </motion.div>
      ))}
    </div>
  );
}

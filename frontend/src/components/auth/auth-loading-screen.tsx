"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Activity } from "lucide-react";

const DEFAULT_MESSAGES = [
  "Signing you in…",
  "Loading workspace…",
  "Loading organization…",
  "Preparing dashboard…",
  "Almost ready…",
];

export function AuthLoadingScreen({
  message,
  messages = DEFAULT_MESSAGES,
}: {
  message?: string | null;
  messages?: string[];
}) {
  const [idx, setIdx] = useState(0);
  const display = message?.trim() || messages[idx % messages.length];

  useEffect(() => {
    if (message) return;
    const id = window.setInterval(() => {
      setIdx((v) => (v + 1) % messages.length);
    }, 1600);
    return () => window.clearInterval(id);
  }, [message, messages.length]);

  return (
    <div className="fixed inset-0 z-[100] flex min-h-screen flex-col items-center justify-center overflow-hidden bg-[#070b12] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(61,214,198,0.16),transparent_55%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(108,158,255,0.1),transparent_50%)]" />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative flex flex-col items-center px-6"
      >
        <motion.div
          className="relative mb-8 flex h-16 w-16 items-center justify-center rounded-2xl border border-teal-400/30 bg-teal-400/10 text-teal-300 shadow-[0_0_40px_rgba(61,214,198,0.2)]"
          animate={{ scale: [1, 1.04, 1] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        >
          <motion.div
            className="absolute inset-0 rounded-2xl border border-teal-400/40"
            animate={{ opacity: [0.35, 0.9, 0.35], scale: [1, 1.12, 1] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
          />
          <Activity className="relative h-7 w-7" />
        </motion.div>

        <div className="text-center">
          <div className="font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight text-white">
            Dependency Intelligence
          </div>
          <div className="mt-1 text-xs text-slate-500">Workspace boot</div>
        </div>

        <div className="mt-8 h-5 min-w-[220px] text-center">
          <AnimatePresence mode="wait">
            <motion.p
              key={display}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.28 }}
              className="text-sm text-slate-300"
            >
              {display}
            </motion.p>
          </AnimatePresence>
        </div>

        <div className="mt-6 h-1 w-48 overflow-hidden rounded-full bg-white/10">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-teal-400 via-teal-300 to-sky-400"
            initial={{ x: "-100%" }}
            animate={{ x: ["-100%", "100%"] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
            style={{ width: "55%" }}
          />
        </div>
      </motion.div>
    </div>
  );
}

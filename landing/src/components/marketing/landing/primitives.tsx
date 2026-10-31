"use client";

import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  motion,
  useInView,
  useReducedMotion,
  animate,
  type HTMLMotionProps,
} from "framer-motion";
import { cn } from "@/lib/utils";

export const sectionViewport = { once: true, margin: "-10% 0px" as const };

export function FadeIn({
  children,
  className,
  delay = 0,
  y = 20,
  ...props
}: HTMLMotionProps<"div"> & { delay?: number; y?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={sectionViewport}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function Section({
  id,
  children,
  className,
  eyebrow,
  title,
  description,
}: {
  id?: string;
  children: ReactNode;
  className?: string;
  eyebrow?: string;
  title?: string;
  description?: string;
}) {
  return (
    <section id={id} className={cn("relative border-t border-white/[0.06] py-20 sm:py-28", className)}>
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        {(eyebrow || title) && (
          <FadeIn className="mb-12 max-w-2xl">
            {eyebrow && (
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-teal-300/80">
                {eyebrow}
              </p>
            )}
            {title && (
              <h2 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-4 text-base leading-relaxed text-slate-400 sm:text-lg">
                {description}
              </p>
            )}
          </FadeIn>
        )}
        {children}
      </div>
    </section>
  );
}

export function WindowChrome({
  title,
  children,
  className,
  trailing,
}: {
  title: string;
  children: ReactNode;
  className?: string;
  trailing?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border border-white/10 bg-[#0a1018] shadow-[0_24px_80px_-32px_rgba(0,0,0,0.85)]",
        className,
      )}
    >
      <div className="flex items-center gap-3 border-b border-white/[0.06] bg-white/[0.02] px-4 py-3">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#f07178]/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#e6b450]/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#7fd962]/80" />
        </div>
        <div className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-500">
          {title}
        </div>
        {trailing}
      </div>
      {children}
    </div>
  );
}

export function CountUp({
  value,
  duration = 1.4,
  suffix = "",
  prefix = "",
  className,
}: {
  value: number;
  duration?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(reduce ? value : 0);

  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setDisplay(value);
      return;
    }
    const controls = animate(0, value, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return () => controls.stop();
  }, [inView, value, duration, reduce]);

  return (
    <span ref={ref} className={className}>
      {prefix}
      {display.toLocaleString()}
      {suffix}
    </span>
  );
}

export function ProgressBar({
  value,
  className,
  tone = "teal",
}: {
  value: number;
  className?: string;
  tone?: "teal" | "amber" | "rose" | "sky";
}) {
  const colors = {
    teal: "bg-teal-400",
    amber: "bg-amber-400",
    rose: "bg-rose-400",
    sky: "bg-sky-400",
  };
  return (
    <div className={cn("h-1.5 overflow-hidden rounded-full bg-white/5", className)}>
      <motion.div
        className={cn("h-full rounded-full", colors[tone])}
        initial={{ width: 0 }}
        whileInView={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        viewport={{ once: true }}
        transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  );
}

export function TypewriterLines({
  lines,
  className,
  lineDelay = 700,
  active = true,
  onComplete,
}: {
  lines: string[];
  className?: string;
  lineDelay?: number;
  active?: boolean;
  onComplete?: () => void;
}) {
  const reduce = useReducedMotion();
  const [visible, setVisible] = useState(reduce ? lines.length : 0);

  useEffect(() => {
    if (!active) return;
    if (reduce) {
      setVisible(lines.length);
      onComplete?.();
      return;
    }
    setVisible(0);
    let i = 0;
    const id = window.setInterval(() => {
      i += 1;
      setVisible(i);
      if (i >= lines.length) {
        window.clearInterval(id);
        onComplete?.();
      }
    }, lineDelay);
    return () => window.clearInterval(id);
  }, [active, lines, lineDelay, onComplete, reduce]);

  return (
    <div className={cn("font-mono text-[12px] leading-6 text-slate-300", className)}>
      {lines.slice(0, visible).map((line, idx) => (
        <motion.div
          key={`${idx}-${line}`}
          initial={reduce ? false : { opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.25 }}
          className="whitespace-pre-wrap"
        >
          <span className="select-none text-teal-400/70">› </span>
          {line}
        </motion.div>
      ))}
      {visible < lines.length && active && !reduce && (
        <span className="ml-1 inline-block h-4 w-1.5 animate-pulse bg-teal-300/80 align-middle" />
      )}
    </div>
  );
}

export function SkeletonPulse({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "rounded-md bg-white/[0.06] skeleton-shimmer",
        className,
      )}
    />
  );
}

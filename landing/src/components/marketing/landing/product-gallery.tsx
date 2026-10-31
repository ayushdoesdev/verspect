"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, ZoomIn } from "lucide-react";
import { Section } from "@/components/marketing/landing/primitives";

const screenshots = [
  {
    src: "/screenshots/app/dashboard-overview.png",
    title: "Dashboard overview",
    description: "A high-level view of repository and dependency health.",
    alt: "Verspect application dashboard overview.",
  },
  {
    src: "/screenshots/app/repository-inventory.png",
    title: "Repository inventory",
    description: "Browse detected packages and their repository context.",
    alt: "Verspect repository dependency inventory screen.",
  },
  {
    src: "/screenshots/app/dependency-analysis-detail.png",
    title: "Dependency analysis",
    description: "Inspect package-level details and analysis signals.",
    alt: "Verspect dependency analysis detail screen.",
  },
  {
    src: "/screenshots/app/dependency-graph.png",
    title: "Dependency graph",
    description: "Explore relationships across the dependency tree.",
    alt: "Verspect interactive dependency graph screen.",
  },
  {
    src: "/screenshots/app/security-findings.png",
    title: "Security findings",
    description: "Review vulnerability findings and affected packages.",
    alt: "Verspect security findings screen.",
  },
  {
    src: "/screenshots/app/migration-assistant.png",
    title: "Migration assistant",
    description: "Review migration guidance and proposed code changes.",
    alt: "Verspect migration assistant screen.",
  },
  {
    src: "/screenshots/app/upgrade-simulation-babel-in-progress.png",
    title: "Upgrade simulation",
    description: "Follow an upgrade analysis while it is running.",
    alt: "Verspect Babel upgrade simulation in progress.",
  },
  {
    src: "/screenshots/app/upgrade-simulation-babel-results.png",
    title: "Simulation results",
    description: "Inspect the impact summary after an upgrade analysis.",
    alt: "Verspect Babel upgrade simulation results.",
  },
  {
    src: "/screenshots/app/upgrade-simulation-pydantic-in-progress.png",
    title: "Python package upgrade",
    description: "Review high-confidence patches and proposed changes for a Python package upgrade.",
    alt: "Verspect Python package upgrade patch preview with proposed repository code changes.",
  },
] as const;

type Screenshot = (typeof screenshots)[number];

export function ProductGallerySection() {
  const [activeScreenshot, setActiveScreenshot] = useState<Screenshot | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const originButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!activeScreenshot) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActiveScreenshot(null);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      originButtonRef.current?.focus();
    };
  }, [activeScreenshot]);

  return (
    <>
      <Section
        id="screenshots"
        eyebrow="Inside the app"
        title="A closer look at Verspect."
        description="Explore the application across dependency inventory, package analysis, security, migrations, and upgrade simulations."
      >
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {screenshots.map((screenshot, index) => (
            <motion.button
              key={screenshot.src}
              type="button"
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.45, delay: (index % 3) * 0.06 }}
              onClick={(event) => {
                originButtonRef.current = event.currentTarget;
                setActiveScreenshot(screenshot);
              }}
              aria-label={"Open " + screenshot.title + " screenshot"}
              className="group overflow-hidden rounded-2xl border border-white/10 bg-[#0a1018] text-left shadow-[0_18px_55px_-35px_rgba(0,0,0,0.9)] transition duration-300 hover:-translate-y-1 hover:border-teal-300/30 hover:shadow-[0_24px_60px_-32px_rgba(45,212,191,0.2)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-300"
            >
              <span className="relative block aspect-[16/10] overflow-hidden bg-[#080d14]">
                <Image
                  src={screenshot.src}
                  alt={screenshot.alt}
                  fill
                  sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                  className="object-contain transition-transform duration-500 group-hover:scale-[1.025]"
                />
                <span className="absolute inset-0 bg-gradient-to-t from-[#05080d]/65 via-transparent to-transparent opacity-70 transition-opacity group-hover:opacity-100" />
                <span className="absolute bottom-3 right-3 inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-[#080d14]/85 px-3 py-1.5 text-xs font-medium text-white opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                  <ZoomIn aria-hidden="true" className="h-3.5 w-3.5" />
                  Expand
                </span>
              </span>
              <span className="block p-4">
                <span className="block text-sm font-semibold text-white">{screenshot.title}</span>
                <span className="mt-1 block text-xs leading-relaxed text-slate-400">{screenshot.description}</span>
              </span>
            </motion.button>
          ))}
        </div>
      </Section>

      <AnimatePresence>
        {activeScreenshot && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-3 backdrop-blur-md sm:p-6"
            role="presentation"
          >
            <button
              type="button"
              aria-label="Close screenshot viewer"
              className="absolute inset-0 cursor-default bg-black/90"
              onClick={() => setActiveScreenshot(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.97, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: 8 }}
              transition={{ duration: 0.2 }}
              role="dialog"
              aria-modal="true"
              aria-labelledby="verspect-screenshot-title"
              className="relative z-10 w-full max-w-7xl"
            >
              <div className="mb-3 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <h3 id="verspect-screenshot-title" className="truncate text-sm font-semibold text-white sm:text-base">
                    {activeScreenshot.title}
                  </h3>
                  <p className="mt-0.5 text-xs text-slate-400">{activeScreenshot.description}</p>
                </div>
                <button
                  ref={closeButtonRef}
                  type="button"
                  onClick={() => setActiveScreenshot(null)}
                  aria-label="Close screenshot viewer"
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/[0.06] text-white transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300"
                >
                  <X aria-hidden="true" className="h-5 w-5" />
                </button>
              </div>
              <div className="relative mx-auto aspect-[16/10] max-h-[calc(100dvh-7rem)] w-full overflow-hidden rounded-xl border border-white/15 bg-[#080d14] shadow-2xl">
                <Image
                  src={activeScreenshot.src}
                  alt={activeScreenshot.alt}
                  fill
                  priority
                  sizes="96vw"
                  className="object-contain"
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

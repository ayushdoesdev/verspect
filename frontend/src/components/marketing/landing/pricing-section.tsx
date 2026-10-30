"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Check, Sparkles } from "lucide-react";
import { FadeIn, Section } from "@/components/marketing/landing/primitives";
import { cn } from "@/lib/utils";

const plans = [
  {
    id: "free",
    name: "Evaluation",
    price: "Eval",
    note: "7 days · for evaluation",
    cta: "Start evaluation",
    href: "/signup",
    highlights: [
      "Evaluate on your repositories",
      "1 repository · Upgrade Simulator",
      "AI features on paid plans",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    price: "$19",
    note: "per month",
    cta: "Choose Starter",
    href: "/signup?plan=starter",
    badge: "Most Popular",
    highlighted: "starter" as const,
    highlights: [
      "Up to 10 repositories",
      "Dependency graph",
      "Upgrade Simulator",
      "Export reports",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: "$39",
    note: "per month",
    cta: "Choose Pro",
    href: "/signup?plan=pro",
    highlights: [
      "Unlimited repos & scans",
      "API · Webhooks",
      "Scheduled scans",
      "AI Upgrade Advisor",
    ],
  },
  {
    id: "team",
    name: "Team",
    price: "$59",
    note: "per user / month",
    cta: "Choose Team",
    href: "/signup?plan=team",
    badge: "Best for Teams",
    highlighted: "team" as const,
    highlights: [
      "Organizations · RBAC",
      "AI Migration Assistant",
      "Exact code patches",
      "Audit logs",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    note: "SSO · private AI",
    cta: "Contact sales",
    href: "/contact",
    highlights: ["SSO & SCIM", "Dedicated infra", "SLA support"],
  },
];

export function PricingSection() {
  return (
    <Section
      id="pricing"
      eyebrow="Pricing"
      title="Evaluate first. Scale when the team does."
      description="Evaluation Plan — perfect for evaluating Verspect on your repositories before upgrading to a paid plan. AI-powered capabilities are available on eligible paid plans."
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {plans.map((plan, i) => (
          <FadeIn key={plan.id} delay={i * 0.04}>
            <motion.div
              whileHover={{ y: -4 }}
              transition={{ duration: 0.2 }}
              className={cn(
                "relative flex h-full flex-col rounded-2xl border p-5 transition",
                plan.highlighted === "starter" &&
                  "border-teal-400/40 bg-teal-400/[0.06] shadow-[0_0_0_1px_rgba(61,214,198,0.12)]",
                plan.highlighted === "team" &&
                  "border-sky-400/35 bg-sky-400/[0.05] shadow-[0_0_0_1px_rgba(108,158,255,0.12)]",
                !plan.highlighted && "border-white/10 bg-white/[0.02] hover:border-white/20",
              )}
            >
              {plan.badge && (
                <span
                  className={cn(
                    "absolute -top-2.5 left-4 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold",
                    plan.highlighted === "team"
                      ? "bg-sky-400 text-[#081018]"
                      : "bg-teal-400 text-[#04201c]",
                  )}
                >
                  {plan.highlighted === "team" && <Sparkles className="h-3 w-3" />}
                  {plan.badge}
                </span>
              )}
              <div className="text-sm font-semibold text-white">{plan.name}</div>
              <div className="mt-3 font-[family-name:var(--font-display)] text-3xl font-semibold text-white">
                {plan.price}
              </div>
              <div className="mt-1 text-xs text-slate-500">{plan.note}</div>
              <ul className="mt-5 flex-1 space-y-2">
                {plan.highlights.map((h) => (
                  <li key={h} className="flex items-start gap-2 text-sm text-slate-300">
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-300" />
                    {h}
                  </li>
                ))}
              </ul>
              <Link
                href={plan.href}
                className={cn(
                  "mt-6 block rounded-full px-4 py-2.5 text-center text-sm font-semibold transition",
                  plan.highlighted === "starter" &&
                    "bg-teal-400 text-[#04201c] hover:bg-teal-300",
                  plan.highlighted === "team" &&
                    "bg-sky-400 text-[#081018] hover:bg-sky-300",
                  !plan.highlighted &&
                    "border border-white/15 bg-white/[0.03] text-white hover:bg-white/[0.07]",
                )}
              >
                {plan.cta}
              </Link>
            </motion.div>
          </FadeIn>
        ))}
      </div>
      <FadeIn className="mt-8 text-center">
        <Link href="/pricing" className="text-sm text-slate-400 underline-offset-4 hover:text-white hover:underline">
          Compare all features →
        </Link>
      </FadeIn>
    </Section>
  );
}

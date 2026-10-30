"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import { Check, Minus, Sparkles, Zap, Users, Building2 } from "lucide-react";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { PRICING_COPY } from "@/lib/evaluation-copy";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

const PLAN_RANK: Record<string, number> = {
  free: 0,
  starter: 1,
  pro: 2,
  team: 3,
  enterprise: 4,
};

type PlanCard = {
  id: string;
  name: string;
  tagline: string;
  monthly_price: number | null;
  yearly_price: number | null;
  cta: string;
  highlights: string[];
  not_included?: string[];
  badge?: string | null;
  highlighted?: boolean;
  billing_note?: string;
  price_label?: string;
  per_seat?: boolean;
};

type ComparisonRow = {
  feature: string;
  free: boolean;
  starter?: boolean;
  pro: boolean;
  team: boolean;
  enterprise: boolean;
  premium?: boolean;
  exclusive?: string;
};

const fallbackPlans: PlanCard[] = [
  {
    id: "free",
    name: "Evaluation",
    tagline:
      "Perfect for evaluating Verspect on your repositories before choosing a paid plan.",
    monthly_price: 0,
    yearly_price: 0,
    cta: "Start Evaluation",
    billing_note: "7 days · no credit card · intended for evaluation",
    price_label: "Evaluation",
    highlights: [
      "Evaluate Verspect on your repositories",
      "1 repository · 1 user",
      "Limited monthly scans",
      "Repository Scan & Sync",
      "Dependency Graph & Analysis",
      "Version & Security Analysis",
      "Upgrade Simulator (analysis)",
      "AI-powered features available on paid plans",
    ],
    not_included: [
      "AI Upgrade Advisor (paid plans)",
      "AI Migration Assistant",
      "GitHub inbound webhooks · Scheduled Scans",
      "Organizations",
    ],
  },
  {
    id: "starter",
    name: "Starter",
    tagline: "For individual developers",
    monthly_price: 19,
    yearly_price: 190,
    cta: "Upgrade to Starter",
    badge: "Most Popular",
    highlighted: true,
    billing_note: "per month · billed monthly",
    highlights: [
      "Up to 10 repositories · 1 user",
      "Repository Scan & Sync",
      "Dependency Graph",
      "Version & Security Analysis",
      "Upgrade Simulator",
      "Background Jobs · Export Reports",
      "Email Support",
    ],
    not_included: ["GitHub inbound webhooks", "Scheduled Scans", "AI Migration Assistant", "Teams · RBAC"],
  },
  {
    id: "pro",
    name: "Pro",
    tagline: "Scale your dependency ops",
    monthly_price: 39,
    yearly_price: 390,
    cta: "Upgrade to Pro",
    billing_note: "per month · billed monthly",
    highlights: [
      "Everything in Starter",
      "Unlimited repositories & scans",
      "GitHub inbound webhooks · Scheduled Scans",
      "Priority processing",
      "Advanced Reports",
      "AI Upgrade Advisor",
    ],
    not_included: ["AI Migration Assistant", "Organizations · RBAC · Audit Logs"],
  },
  {
    id: "team",
    name: "Team",
    tagline: "Best for Teams",
    monthly_price: 59,
    yearly_price: 590,
    cta: "Upgrade to Team",
    badge: "Best for Teams",
    highlighted: true,
    per_seat: true,
    billing_note: "per user / month · billed monthly",
    highlights: [
      "Everything in Pro",
      "Organizations · Sharing · RBAC",
      "Audit Logs · Team Dashboard",
      "✨ AI Migration Assistant",
      "Exact code replacements",
      "Line-by-line guidance · AI patches",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    tagline: "Global scale & control",
    monthly_price: null,
    yearly_price: null,
    cta: "Contact Sales",
    billing_note: "SSO · SCIM · private deployment",
    highlights: [
      "Everything in Team",
      "SSO & SCIM",
      "Self-hosted / dedicated infra",
      "Private AI",
      "SLA & dedicated support",
    ],
  },
];

const fallbackComparison: ComparisonRow[] = [
  { feature: "Repository Scanning", free: true, starter: true, pro: true, team: true, enterprise: true },
  { feature: "Repository Sync", free: true, starter: true, pro: true, team: true, enterprise: true },
  { feature: "Dependency Graph", free: true, starter: true, pro: true, team: true, enterprise: true },
  { feature: "Upgrade Simulator (analysis)", free: true, starter: true, pro: true, team: true, enterprise: true },
  { feature: "Unlimited repositories", free: false, starter: false, pro: true, team: true, enterprise: true },
  { feature: "GitHub inbound webhooks", free: false, starter: false, pro: true, team: true, enterprise: true },
  { feature: "Scheduled Scans", free: false, starter: false, pro: true, team: true, enterprise: true },
  { feature: "AI Upgrade Advisor", free: false, starter: false, pro: true, team: true, enterprise: true },
  {
    feature: "AI Migration Assistant",
    free: false,
    starter: false,
    pro: false,
    team: true,
    enterprise: true,
    premium: true,
    exclusive: "team",
  },
  { feature: "Organizations & RBAC", free: false, starter: false, pro: false, team: true, enterprise: true },
  { feature: "Audit Logs", free: false, starter: false, pro: false, team: true, enterprise: true },
  { feature: "SSO / SCIM", free: false, starter: false, pro: false, team: false, enterprise: true },
];

const faqs = [
  {
    q: "What happens when my 7-day evaluation ends?",
    a: "You can still sign in and view repositories, scans, and reports. New imports, scans, sync, Upgrade Simulator runs, and background jobs pause until you upgrade. Nothing is deleted.",
  },
  {
    q: "Do I need a credit card for Evaluation?",
    a: "No. Evaluation starts at signup with no credit card. Upgrade to Starter, Pro, or Team when you’re ready.",
  },
  {
    q: "What’s the difference between Upgrade Simulator and AI Migration Assistant?",
    a: "Upgrade Simulator performs deterministic analysis — risk, breaking changes, readiness. AI Migration Assistant generates exact code replacements and patches, and is available only on Team and Enterprise.",
  },
  {
    q: "Can I upgrade, downgrade, or cancel later?",
    a: "Upgrades apply immediately with prorated billing when supported. Downgrades and cancellations take effect at the end of your billing period — you keep current access until then, and nothing is deleted. Reactivate anytime before the period ends.",
  },
  {
    q: "Is annual billing available?",
    a: "Monthly billing is available today. Annual billing is supported in our billing architecture and will be offered as we expand commercial options.",
  },
];

function Cell({ ok }: { ok: boolean }) {
  return ok ? (
    <Check className="mx-auto h-4 w-4 text-teal-300" />
  ) : (
    <Minus className="mx-auto h-4 w-4 text-slate-600" />
  );
}

export default function PricingPage() {
  const auth = useAuth();
  const router = useRouter();
  const qc = useQueryClient();
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["pricing"],
    queryFn: () => api.pricing(),
    retry: false,
  });
  const sub = useQuery({
    queryKey: ["subscription"],
    queryFn: api.subscription,
    enabled: auth.isAuthenticated,
    retry: false,
  });
  const plans = (data?.plans?.length ? data.plans : fallbackPlans) as PlanCard[];
  const comparison = (data?.feature_comparison?.length
    ? data.feature_comparison
    : fallbackComparison) as ComparisonRow[];
  const currentPlan = (sub.data?.plan || (auth.isAuthenticated ? "free" : "")).toLowerCase();

  function ctaFor(planId: string): { label: string; href?: string; action?: "upgrade" | "downgrade" } {
    if (planId === "enterprise") return { label: "Contact Sales", href: "/contact" };
    if (!auth.isAuthenticated) {
      if (planId === "free") return { label: "Start Evaluation", href: "/signup" };
      return { label: planId === "starter" ? "Upgrade to Starter" : `Upgrade to ${planId[0].toUpperCase()}${planId.slice(1)}`, href: `/signup?plan=${planId}` };
    }
    if (planId === currentPlan) return { label: "Current Plan", href: "/billing" };
    if (planId === "free") return { label: "Start Evaluation", href: "/billing" };
    const rank = PLAN_RANK[planId] ?? 0;
    const cur = PLAN_RANK[currentPlan] ?? 0;
    if (rank > cur) return { label: "Upgrade", action: "upgrade" };
    return { label: "Downgrade", action: "downgrade" };
  }

  async function handlePlanAction(planId: string, action?: "upgrade" | "downgrade") {
    if (!action || planId === "enterprise" || planId === "free") {
      return;
    }
    setBusyPlan(planId);
    try {
      if (currentPlan === "free" && action === "upgrade") {
        const res = await api.checkout({ plan: planId, interval: "month" });
        window.location.href = res.url;
        return;
      }
      const res = await api.changePlan({ plan: planId, interval: "month" });
      if (res.checkout_url && res.action === "checkout_required") {
        window.location.href = res.checkout_url;
        return;
      }
      await qc.invalidateQueries({ queryKey: ["subscription"] });
      router.push("/billing");
    } catch {
      router.push(`/billing?plan=${planId}`);
    } finally {
      setBusyPlan(null);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#060910] text-slate-100">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(45,212,191,0.18),transparent),radial-gradient(ellipse_40%_30%_at_90%_10%,rgba(99,102,241,0.12),transparent)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.5) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <MarketingNav />

      <section className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          className="text-center"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
            className="mx-auto mb-5 flex flex-wrap items-center justify-center gap-2"
          >
            <PrivateBetaBadge variant="marketing" />
            <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
              <Zap className="h-3.5 w-3.5 text-teal-300" />
              Commercial launch pricing
            </span>
          </motion.div>
          <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-white sm:text-6xl">
            Pricing that scales with
            <span className="block bg-gradient-to-r from-teal-300 via-cyan-200 to-indigo-300 bg-clip-text text-transparent">
              how you ship
            </span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-slate-400 sm:text-lg">
            {PRICING_COPY.tagline} {PRICING_COPY.aiNote}
          </p>
          <p className="mx-auto mt-3 max-w-xl text-xs text-slate-500">{PRICING_COPY.notice}</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="mx-auto mt-10 grid max-w-3xl gap-3 sm:grid-cols-2"
        >
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-left">
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <Building2 className="h-4 w-4 text-slate-300" />
              Upgrade Simulator
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
              Analysis only — risk, breaking changes, readiness. Available on Evaluation through Enterprise.
            </p>
          </div>
          <div className="rounded-2xl border border-teal-400/25 bg-teal-400/[0.07] p-4 text-left">
            <div className="flex items-center gap-2 text-sm font-medium text-teal-200">
              <Sparkles className="h-4 w-4" />
              AI Migration Assistant
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-300">
              Code generation — exact replacements, patches, line-by-line guidance. Team & Enterprise only.
            </p>
          </div>
        </motion.div>

        <div className="mt-14 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {plans.map((plan, i) => {
            const isStarter = plan.id === "starter" || plan.badge === "Most Popular";
            const isTeam = plan.id === "team" || plan.badge === "Best for Teams";
            const featured = Boolean(plan.highlighted || isStarter || isTeam);

            return (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 28 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 + i * 0.06, duration: 0.45 }}
                whileHover={{ y: -4, transition: { duration: 0.2 } }}
                className={cn(
                  "relative flex flex-col rounded-2xl border p-5 backdrop-blur-sm",
                  isStarter &&
                    "border-teal-400/45 bg-gradient-to-b from-teal-400/20 via-teal-400/[0.06] to-white/[0.02] shadow-[0_0_50px_rgba(45,212,191,0.14)] xl:scale-[1.02]",
                  isTeam &&
                    !isStarter &&
                    "border-indigo-400/40 bg-gradient-to-b from-indigo-400/15 via-indigo-400/[0.05] to-white/[0.02] shadow-[0_0_40px_rgba(129,140,248,0.12)]",
                  !featured && "border-white/10 bg-white/[0.03]",
                )}
              >
                {plan.badge || isStarter || isTeam ? (
                  <div
                    className={cn(
                      "absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-wider",
                      isStarter && "bg-teal-400 text-[#04201c]",
                      isTeam && !isStarter && "bg-indigo-400 text-[#0b1020]",
                      !isStarter && !isTeam && "border border-white/20 bg-[#0b1020] text-slate-200",
                    )}
                  >
                    {plan.badge || (isStarter ? "Most Popular" : "Best for Teams")}
                  </div>
                ) : null}

                <div className="mt-1 flex items-center gap-2">
                  {isTeam ? <Users className="h-4 w-4 text-indigo-300" /> : null}
                  <div className="text-sm font-semibold text-white">{plan.name}</div>
                </div>
                <div className="mt-1 text-xs text-slate-500">{plan.tagline}</div>

                <div className="mt-5">
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-semibold tracking-tight text-white">
                      {plan.monthly_price == null
                        ? "Custom"
                        : plan.monthly_price === 0
                          ? "$0"
                          : `$${plan.monthly_price}`}
                    </span>
                    {plan.monthly_price != null && plan.monthly_price > 0 ? (
                      <span className="text-sm text-slate-500">
                        {plan.per_seat ? "/user/mo" : "/mo"}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 min-h-[1rem] text-[11px] text-slate-500">
                    {plan.billing_note ||
                      (plan.yearly_price
                        ? `$${plan.yearly_price}/yr billed annually`
                        : "\u00a0")}
                  </div>
                </div>

                <ul className="mt-5 flex-1 space-y-2 text-[13px] text-slate-300">
                  {plan.highlights.map((h) => (
                    <li key={h} className="flex gap-2">
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-300" />
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>

                {(plan.not_included || []).length ? (
                  <ul className="mt-4 space-y-1.5 border-t border-white/5 pt-3 text-[11px] text-slate-500">
                    {plan.not_included!.slice(0, 3).map((item) => (
                      <li key={item} className="flex gap-2">
                        <Minus className="mt-0.5 h-3 w-3 shrink-0" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mt-4 border-t border-transparent pt-3" />
                )}

                {(() => {
                  const cta = ctaFor(plan.id);
                  const isCurrent = cta.label === "Current Plan";
                  const className = cn(
                    "mt-6 block w-full rounded-full py-2.5 text-center text-sm font-semibold transition disabled:opacity-60",
                    isCurrent && "border border-teal-400/40 bg-teal-400/10 text-teal-200",
                    !isCurrent && isStarter && "bg-teal-400 text-[#04201c] hover:bg-teal-300",
                    !isCurrent &&
                      isTeam &&
                      !isStarter &&
                      "bg-indigo-400 text-[#0b1020] hover:bg-indigo-300",
                    !isCurrent &&
                      !isStarter &&
                      !isTeam &&
                      "border border-white/15 text-white hover:bg-white/5",
                  );
                  if (cta.action) {
                    return (
                      <button
                        type="button"
                        disabled={busyPlan === plan.id}
                        onClick={() => handlePlanAction(plan.id, cta.action)}
                        className={className}
                      >
                        {busyPlan === plan.id ? "Working…" : cta.label}
                      </button>
                    );
                  }
                  return (
                    <Link href={cta.href || "/billing"} className={className}>
                      {cta.label}
                    </Link>
                  );
                })()}
              </motion.div>
            );
          })}
        </div>

        <div className="mt-24">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center font-[family-name:var(--font-display)] text-3xl font-semibold text-white"
          >
            Compare plans
          </motion.h2>
          <p className="mx-auto mt-3 max-w-xl text-center text-sm text-slate-400">
            Simulator analyzes. Migration Assistant writes code. Kept as separate products on every
            plan.
          </p>
          <div className="mt-8 overflow-x-auto rounded-2xl border border-white/10 bg-white/[0.02]">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-white/[0.04] text-slate-400">
                <tr>
                  <th className="px-4 py-3 font-medium">Feature</th>
                  <th className="px-3 py-3 text-center font-medium">Evaluation</th>
                  <th className="px-3 py-3 text-center font-medium text-teal-300">Starter</th>
                  <th className="px-3 py-3 text-center font-medium">Pro</th>
                  <th className="px-3 py-3 text-center font-medium text-indigo-300">Team</th>
                  <th className="px-3 py-3 text-center font-medium">Enterprise</th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((row) => (
                  <tr
                    key={row.feature}
                    className={cn(
                      "border-t border-white/5",
                      row.premium && "bg-indigo-400/[0.06]",
                    )}
                  >
                    <td className="px-4 py-3">
                      <span className="text-slate-200">{row.feature}</span>
                      {row.premium ? (
                        <span className="ml-2 inline-flex items-center gap-1 rounded-full border border-indigo-400/30 bg-indigo-400/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-indigo-300">
                          <Sparkles className="h-3 w-3" />
                          Team+
                        </span>
                      ) : null}
                    </td>
                    <td className="px-3 py-3">
                      <Cell ok={!!row.free} />
                    </td>
                    <td className="px-3 py-3">
                      <Cell ok={!!(row.starter ?? row.pro)} />
                    </td>
                    <td className="px-3 py-3">
                      <Cell ok={!!row.pro} />
                    </td>
                    <td className="px-3 py-3">
                      <Cell ok={!!row.team} />
                    </td>
                    <td className="px-3 py-3">
                      <Cell ok={!!row.enterprise} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-24">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center font-[family-name:var(--font-display)] text-3xl font-semibold text-white"
          >
            Frequently asked questions
          </motion.h2>
          <div className="mx-auto mt-10 max-w-3xl space-y-3">
            {faqs.map((item, i) => (
              <motion.details
                key={item.q}
                initial={{ opacity: 0, y: 8 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.04 }}
                className="group rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-4 open:bg-white/[0.05]"
              >
                <summary className="cursor-pointer list-none text-sm font-medium text-white marker:content-none">
                  {item.q}
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{item.a}</p>
              </motion.details>
            ))}
          </div>
          <div className="mt-12 text-center">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-full bg-teal-400 px-6 py-3 text-sm font-semibold text-[#04201c] hover:bg-teal-300"
            >
              Start 7-day evaluation
            </Link>
            <p className="mt-3 text-xs text-slate-500">No credit card · Upgrade anytime</p>
          </div>
        </div>
      </section>
      <MarketingFooter />
    </div>
  );
}

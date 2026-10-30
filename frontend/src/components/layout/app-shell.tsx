"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  Boxes,
  CreditCard,
  FlaskConical,
  Gauge,
  GitBranch,
  LayoutDashboard,
  Lock,
  LogOut,
  Moon,
  Search,
  Settings,
  Shield,
  Sparkles,
  Sun,
  User,
  Users,
} from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";
import { useNavRouter } from "@/lib/nav-router";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EvaluationBanner } from "@/components/billing/evaluation-banner";
import { BetaNotice } from "@/components/beta/beta-notice";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { NavLink } from "@/components/navigation/nav-link";

/** Customer product navigation only — no marketing / admin / feedback. */
const nav = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/repositories", label: "Repositories", icon: GitBranch },
  { href: "/dependencies", label: "Dependencies", icon: Boxes },
  { href: "/security", label: "Security", icon: Shield },
  { href: "/upgrade-simulator", label: "Upgrade Simulator", icon: FlaskConical },
  {
    href: "/migration-assistant",
    label: "AI Migration Assistant",
    icon: Sparkles,
    teamOnly: true,
  },
  { href: "/search", label: "Search", icon: Search },
  { href: "/team", label: "Team", icon: Users, teamOnly: true },
  { href: "/billing", label: "Billing", icon: CreditCard },
  { href: "/usage", label: "Usage", icon: Gauge },
  { href: "/settings/ai", label: "AI Settings", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings },
];

/** Warm high-traffic app routes so the first click feels instant. */
function PrefetchWarmRoutes() {
  const router = useRouter();
  useEffect(() => {
    const routes = [
      "/dashboard",
      "/repositories",
      "/dependencies",
      "/security",
      "/upgrade-simulator",
      "/migration-assistant",
      "/search",
    ];
    const handle = window.setTimeout(() => {
      for (const href of routes) router.prefetch(href);
    }, 150);
    return () => window.clearTimeout(handle);
  }, [router]);
  return null;
}

export function AppShell({
  children,
  userLogin,
}: {
  children: React.ReactNode;
  userLogin?: string;
}) {
  const pathname = usePathname();
  const router = useNavRouter();
  const { theme, setTheme } = useTheme();
  const auth = useAuth();
  const entitlements = useEntitlements();
  const displayLogin = userLogin || auth.user?.github_login || auth.user?.email || undefined;
  const migrationUnlocked = entitlements.canGenerateAiMigration;
  const teamsUnlocked = entitlements.teamsEnabled;

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <PrefetchWarmRoutes />
      <aside className="flex flex-col border-b border-border/70 bg-sidebar/90 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="flex h-16 shrink-0 items-center gap-2 px-5">
          <Activity className="h-5 w-5 text-primary" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <div className="text-sm font-semibold tracking-wide">Verspect</div>
              <PrivateBetaBadge />
            </div>
            <div className="-mt-0.5 text-xs text-muted-foreground">Dependency Intelligence</div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-y-auto lg:overflow-x-visible">
          {nav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            const locked =
              ("teamOnly" in item &&
                item.teamOnly &&
                (item.href === "/migration-assistant"
                  ? !migrationUnlocked
                  : !teamsUnlocked)) ||
              false;
            return (
              <NavLink
                key={item.href}
                href={item.href}
                interactive="nav"
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
                {locked ? (
                  <Lock className="h-3 w-3 shrink-0 opacity-70" aria-label="Team plan" />
                ) : null}
              </NavLink>
            );
          })}
        </nav>
        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border/70 p-3 lg:mt-auto lg:p-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground transition hover:bg-accent hover:text-foreground"
              >
                {displayLogin}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52">
              <DropdownMenuItem onClick={() => router.push("/settings")}>
                <User className="mr-2 h-3.5 w-3.5" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push("/settings")}>
                <Settings className="mr-2 h-3.5 w-3.5" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push("/usage")}>
                <Gauge className="mr-2 h-3.5 w-3.5" />
                Usage
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push("/billing")}>
                <CreditCard className="mr-2 h-3.5 w-3.5" />
                Billing
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => {
                  auth.logout();
                  router.push("/login");
                }}
              >
                <LogOut className="mr-2 h-3.5 w-3.5" />
                Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Toggle theme"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            >
              {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </aside>
      <main className="min-w-0 p-4 md:p-8">
        <BetaNotice />
        <EvaluationBanner />
        {children}
      </main>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between animate-fade-up">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
        {description ? (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/80 bg-gradient-to-b from-secondary/20 to-transparent px-6 py-16 text-center animate-fade-up">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
        {icon || <AlertTriangle className="h-6 w-6" />}
      </div>
      <h3 className="text-lg font-medium tracking-tight">{title}</h3>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

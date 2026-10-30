"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Building2,
  Gauge,
  GitBranch,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  MessageSquarePlus,
  Mail,
  Server,
  Settings,
  Shield,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { PrivateBetaBadge } from "@/components/beta/private-beta-badge";
import { Button } from "@/components/ui/button";

const adminNav = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/organizations", label: "Organizations", icon: Building2 },
  { href: "/admin/repositories", label: "Repositories", icon: GitBranch },
  { href: "/admin/feedback", label: "Feedback", icon: MessageSquarePlus },
  { href: "/admin/contact", label: "Contact Requests", icon: Mail },
  { href: "/admin/analytics", label: "Analytics", icon: Gauge },
  { href: "/admin/workers", label: "Workers", icon: Server },
  { href: "/admin/health", label: "System Health", icon: HeartPulse },
  { href: "/admin/settings", label: "Settings", icon: Settings },
];

/** Independent platform-admin chrome — never reuse the customer AppShell. */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const auth = useAuth();

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[220px_1fr]">
      <aside className="flex flex-col border-b border-border/70 bg-sidebar/95 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="flex h-16 shrink-0 items-center gap-2 px-4">
          <Shield className="h-5 w-5 text-primary" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <div className="text-sm font-semibold tracking-wide">Platform</div>
              <PrivateBetaBadge />
            </div>
            <div className="-mt-0.5 text-[11px] text-muted-foreground">Verspect Admin</div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-3 lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-y-auto">
          {adminNav.map((item) => {
            const active = item.exact
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="shrink-0 space-y-2 border-t border-border/70 p-3">
          <div className="truncate px-1 text-[11px] text-muted-foreground">
            {auth.user?.email || auth.user?.github_login}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            onClick={() => {
              auth.logout();
              router.replace("/admin/login");
            }}
          >
            <LogOut className="mr-2 h-3.5 w-3.5" />
            Logout
          </Button>
          <Link
            href="/"
            className="flex items-center gap-2 px-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            <Activity className="h-3 w-3" />
            Marketing site
          </Link>
        </div>
      </aside>
      <main className="min-w-0 p-4 md:p-8">{children}</main>
    </div>
  );
}

export function AdminPageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
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

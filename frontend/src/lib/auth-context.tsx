"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  api,
  clearTokens,
  hasStoredSession,
  logoutRemote,
  setTokens,
} from "@/lib/api";
import type { User } from "@/types";
import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  user: User | null;
  status: AuthStatus;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** True while signing in / hydrating before first navigation. */
  isTransitioning: boolean;
  loadingMessage: string | null;
  /** Validate stored tokens against /auth/me (with refresh). */
  validateSession: () => Promise<User | null>;
  /** Persist tokens and mark authenticated (no navigation). */
  establishSession: (access: string, refresh: string, user?: User | null) => Promise<User | null>;
  /**
   * Full premium sign-in: tokens → user → workspace hydrate → single navigation.
   * Never leaves the loading screen until the destination is ready.
   */
  completeSignIn: (args: {
    access: string;
    refresh: string;
    user?: User | null;
    redirectTo?: string;
  }) => Promise<User | null>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const PUBLIC_PREFIXES = [
  "/",
  "/pricing",
  "/docs",
  "/blog",
  "/contact",
  "/roadmap",
  "/changelog",
  "/feedback",
  "/legal",
  "/login",
  "/signup",
  "/forgot-password",
  "/admin/login",
];

function isPublicPath(pathname: string): boolean {
  if (pathname === "/") return true;
  return PUBLIC_PREFIXES.some((p) => p !== "/" && (pathname === p || pathname.startsWith(p + "/")));
}

function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

function isAdminLoginPath(pathname: string): boolean {
  return pathname === "/admin/login";
}

function isAuthFormPath(pathname: string): boolean {
  return (
    pathname === "/login" ||
    pathname === "/signup" ||
    pathname.startsWith("/login/") ||
    pathname === "/forgot-password"
  );
}

async function sleep(ms: number) {
  await new Promise((r) => setTimeout(r, ms));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState<string | null>("Restoring session…");
  const bootstrapped = useRef(false);
  const suppressTokenEvents = useRef(false);
  const transitioningRef = useRef(false);

  const setTransitioning = useCallback((v: boolean) => {
    transitioningRef.current = v;
    setIsTransitioning(v);
  }, []);

  const hydrateWorkspace = useCallback(
    async (opts?: { soft?: boolean }) => {
      const soft = !!opts?.soft;
      const run = async () => {
        if (!soft) setLoadingMessage("Loading organization…");
        await Promise.allSettled([
          queryClient.prefetchQuery({
            queryKey: ["me"],
            queryFn: api.me,
          }),
          queryClient.prefetchQuery({
            queryKey: ["organization"],
            queryFn: api.currentOrganization,
          }),
          queryClient.prefetchQuery({
            queryKey: ["organizations"],
            queryFn: api.organizations,
          }),
        ]);

        if (!soft) setLoadingMessage("Loading subscription…");
        await Promise.allSettled([
          queryClient.prefetchQuery({
            queryKey: ["subscription"],
            queryFn: api.subscription,
          }),
          queryClient.prefetchQuery({
            queryKey: ["usage"],
            queryFn: api.usage,
          }),
        ]);

        if (!soft) setLoadingMessage("Preparing dashboard…");
        await Promise.allSettled([
          queryClient.prefetchQuery({
            queryKey: ["repositories"],
            queryFn: () => api.repositories("?page_size=50"),
          }),
          queryClient.prefetchQuery({
            queryKey: ["dashboard"],
            queryFn: api.dashboard,
          }),
        ]);

        if (!soft) {
          setLoadingMessage("Almost ready…");
          await sleep(280);
        }
      };

      if (soft) {
        void run();
        return;
      }
      await run();
    },
    [queryClient],
  );

  const validateSession = useCallback(async (): Promise<User | null> => {
    if (!hasStoredSession()) {
      setUser(null);
      setStatus("unauthenticated");
      setLoadingMessage(null);
      return null;
    }
    try {
      const me = await api.me();
      setUser(me);
      setStatus("authenticated");
      queryClient.setQueryData(["me"], me);
      setLoadingMessage(null);
      return me;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        setStatus("unauthenticated");
        setLoadingMessage(null);
        return null;
      }
      if (hasStoredSession()) {
        setStatus((prev) => (prev === "authenticated" ? prev : "loading"));
      } else {
        setStatus("unauthenticated");
        setLoadingMessage(null);
      }
      return null;
    }
  }, [queryClient]);

  const establishSession = useCallback(
    async (access: string, refresh: string, knownUser?: User | null) => {
      suppressTokenEvents.current = true;
      setTokens(access, refresh, { silent: true });
      suppressTokenEvents.current = false;

      if (knownUser) {
        setUser(knownUser);
        setStatus("authenticated");
        queryClient.setQueryData(["me"], knownUser);
        return knownUser;
      }
      return validateSession();
    },
    [queryClient, validateSession],
  );

  const completeSignIn = useCallback(
    async ({
      access,
      refresh,
      user: knownUser,
      redirectTo,
    }: {
      access: string;
      refresh: string;
      user?: User | null;
      redirectTo?: string;
    }) => {
      setTransitioning(true);
      setLoadingMessage("Signing you in…");
      setStatus("loading");

      try {
        suppressTokenEvents.current = true;
        setTokens(access, refresh, { silent: true });

        let nextUser = knownUser ?? null;
        if (nextUser) {
          queryClient.setQueryData(["me"], nextUser);
        } else {
          setLoadingMessage("Loading workspace…");
          nextUser = await api.me();
        }

        setUser(nextUser);
        setStatus("authenticated");
        queryClient.setQueryData(["me"], nextUser);

        await hydrateWorkspace({ soft: false });

        const dest =
          redirectTo ||
          (nextUser.onboarding_completed === false ? "/onboarding" : "/dashboard");

        router.replace(dest);
        await sleep(160);
        setTransitioning(false);
        setLoadingMessage(null);
        return nextUser;
      } catch (err) {
        setTransitioning(false);
        setLoadingMessage(null);
        setStatus("unauthenticated");
        setUser(null);
        clearTokens();
        throw err;
      } finally {
        suppressTokenEvents.current = false;
      }
    },
    [hydrateWorkspace, queryClient, router, setTransitioning],
  );

  const logout = useCallback(() => {
    void logoutRemote().finally(() => {
      clearTokens();
      setUser(null);
      setStatus("unauthenticated");
      setTransitioning(false);
      setLoadingMessage(null);
      queryClient.clear();
    });
  }, [queryClient, setTransitioning]);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    let cancelled = false;

    async function bootstrap() {
      setLoadingMessage("Restoring session…");
      if (!hasStoredSession()) {
        if (!cancelled) {
          setUser(null);
          setStatus("unauthenticated");
          setLoadingMessage(null);
        }
        return;
      }

      try {
        setLoadingMessage("Loading workspace…");
        const me = await api.me();
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
        queryClient.setQueryData(["me"], me);
        void hydrateWorkspace({ soft: true });
        setLoadingMessage(null);
      } catch (err) {
        if (cancelled) return;
        setLoadingMessage(null);
        if (err instanceof ApiError && err.status === 401) {
          // tokens already cleared by apiFetch on refresh failure
          setUser(null);
          setStatus("unauthenticated");
          return;
        }
        // Transient API/network errors must not force logout.
        if (hasStoredSession()) {
          setStatus("authenticated");
          setLoadingMessage(null);
          return;
        }
        setUser(null);
        setStatus("unauthenticated");
      }
    }

    void bootstrap();

    const onCleared = () => {
      if (suppressTokenEvents.current || transitioningRef.current) return;
      setUser(null);
      setStatus("unauthenticated");
      setLoadingMessage(null);
    };
    const onChanged = () => {
      if (suppressTokenEvents.current || transitioningRef.current) return;
      void validateSession();
    };
    window.addEventListener("depintel:tokens-cleared", onCleared);
    window.addEventListener("depintel:tokens-changed", onChanged);
    return () => {
      cancelled = true;
      window.removeEventListener("depintel:tokens-cleared", onCleared);
      window.removeEventListener("depintel:tokens-changed", onChanged);
    };
  }, [hydrateWorkspace, queryClient, validateSession]);

  const value = useMemo(
    () => ({
      user,
      status,
      isLoading: status === "loading" || isTransitioning,
      isAuthenticated: status === "authenticated",
      isTransitioning,
      loadingMessage,
      validateSession,
      establishSession,
      completeSignIn,
      logout,
    }),
    [
      user,
      status,
      isTransitioning,
      loadingMessage,
      validateSession,
      establishSession,
      completeSignIn,
      logout,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Blocks Login/Dashboard until session bootstrap (or sign-in transition) finishes. */
export function AuthInitializer({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "loading" || auth.isTransitioning) return;

    if (auth.status === "authenticated" && isAuthFormPath(pathname)) {
      const dest = auth.user?.onboarding_completed === false ? "/onboarding" : "/dashboard";
      router.replace(dest);
      return;
    }

    if (auth.status === "authenticated" && isAdminLoginPath(pathname) && auth.user?.is_admin) {
      router.replace("/admin");
      return;
    }

    if (auth.status === "unauthenticated" && isAdminPath(pathname) && !isAdminLoginPath(pathname)) {
      router.replace("/admin/login");
      return;
    }

    if (auth.status === "unauthenticated" && !isPublicPath(pathname)) {
      router.replace("/login");
    }
  }, [auth.status, auth.isTransitioning, auth.user, pathname, router]);

  if (auth.status === "loading" || auth.isTransitioning) {
    return <AuthLoadingScreen message={auth.loadingMessage} />;
  }

  // Authenticated user still on login/signup — keep loading until navigate completes
  if (auth.isAuthenticated && isAuthFormPath(pathname)) {
    return <AuthLoadingScreen message="Preparing dashboard…" />;
  }

  if (auth.isAuthenticated && isAdminLoginPath(pathname) && auth.user?.is_admin) {
    return <AuthLoadingScreen message="Opening platform…" />;
  }

  // Unauthenticated on admin console → admin login (not customer login)
  if (
    auth.status === "unauthenticated" &&
    isAdminPath(pathname) &&
    !isAdminLoginPath(pathname)
  ) {
    return <AuthLoadingScreen message="Redirecting to admin sign in…" />;
  }

  // Unauthenticated on a protected route — hold loading while redirecting to login
  if (auth.status === "unauthenticated" && !isPublicPath(pathname)) {
    return <AuthLoadingScreen message="Redirecting to sign in…" />;
  }

  return <>{children}</>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useAuthOptional() {
  return useContext(AuthContext);
}

/**
 * Gate protected pages: wait for session validation, then redirect only if
 * authentication has actually failed. Never redirect while bootstrapping.
 * Prefer AuthInitializer for route-level redirects; this is a safety net.
 */
export function useRequireAuth() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "loading" || auth.isTransitioning) return;
    if (auth.status === "unauthenticated") {
      router.replace("/login");
    }
  }, [auth.status, auth.isTransitioning, router]);

  return auth;
}

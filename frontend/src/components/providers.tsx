"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { AuthInitializer, AuthProvider } from "@/lib/auth-context";
import { LoadingSystem } from "@/components/loading";
import { FeedbackWidget } from "@/components/feedback/feedback-widget";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <QueryClientProvider client={client}>
        <AuthProvider>
          <AuthInitializer>
            <LoadingSystem>{children}</LoadingSystem>
            {/* Outside LoadingSystem so the jobs panel cannot cover it. */}
            <FeedbackWidget />
          </AuthInitializer>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { startNavigation } from "@/components/navigation/navigation-progress";

/**
 * Router wrapper that kicks the global top progress bar on programmatic navigations.
 */
export function useNavRouter() {
  const router = useRouter();
  return useMemo(
    () => ({
      ...router,
      push: (href: string, options?: Parameters<typeof router.push>[1]) => {
        startNavigation(href);
        return router.push(href, options);
      },
      replace: (href: string, options?: Parameters<typeof router.replace>[1]) => {
        startNavigation(href);
        return router.replace(href, options);
      },
      prefetch: router.prefetch.bind(router),
    }),
    [router],
  );
}

"use client";

import { JobsProvider } from "@/lib/jobs/jobs-context";
import { NavigationProgress } from "@/components/navigation/navigation-progress";
import { ProgressModal } from "./progress-modal";
import { JobsPanel } from "./jobs-panel";
import { ToastViewport } from "./toast-viewport";

export function LoadingSystem({ children }: { children: React.ReactNode }) {
  return (
    <JobsProvider>
      <NavigationProgress />
      {children}
      <ProgressModal />
      <JobsPanel />
      <ToastViewport />
    </JobsProvider>
  );
}

export { LoadingButton } from "./loading-button";
export {
  ActivityTimeline,
  ProgressBar,
  formatElapsed,
  estimateRemaining,
} from "./activity-timeline";
export * from "./skeletons";
export {
  LoadingCopy,
  InlineSpinner,
  RefetchBar,
  ErrorState,
  EmptyStatePanel,
  QueryBoundary,
} from "./states";

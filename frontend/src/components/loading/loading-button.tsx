"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface LoadingButtonProps extends ButtonProps {
  loading?: boolean;
  loadingText?: string;
}

export const LoadingButton = React.forwardRef<HTMLButtonElement, LoadingButtonProps>(
  ({ loading, loadingText, disabled, children, className, ...props }, ref) => (
    <Button
      ref={ref}
      disabled={disabled || loading}
      className={cn(className)}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {loading && loadingText ? loadingText : children}
    </Button>
  ),
);
LoadingButton.displayName = "LoadingButton";

import * as React from "react";
import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "error" | "info";
}

export const Badge = ({ className, variant = "default", ...props }: BadgeProps) => {
  const variants = {
    default: "bg-surface-2 text-parchment",
    success: "bg-verified/20 text-verified border border-verified/30",
    warning: "bg-hazard/20 text-hazard border border-hazard/30",
    error: "bg-red-500/20 text-red-400 border border-red-500/30",
    info: "bg-accent/20 text-accent border border-accent/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
      {...props}
    />
  );
};

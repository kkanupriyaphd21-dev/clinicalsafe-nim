import * as React from "react";
import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number;
  className?: string;
}

export const ProgressBar = ({ value, className }: ProgressBarProps) => {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-surface-2", className)}>
      <div
        className="h-full rounded-full bg-accent transition-all duration-500 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
};

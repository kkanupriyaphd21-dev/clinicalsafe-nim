import * as React from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle, Info } from "lucide-react";

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "error";
}

export const Alert = ({ className, variant = "info", children, ...props }: AlertProps) => {
  const variants = {
    info: "border-accent/30 bg-accent/10 text-accent",
    success: "border-verified/30 bg-verified/10 text-verified",
    warning: "border-hazard/30 bg-hazard/10 text-hazard",
    error: "border-red-500/30 bg-red-500/10 text-red-400",
  };
  const icons = {
    info: Info,
    success: CheckCircle,
    warning: AlertCircle,
    error: AlertCircle,
  };
  const Icon = icons[variant];
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border p-4 text-sm",
        variants[variant],
        className
      )}
      {...props}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div>{children}</div>
    </div>
  );
};

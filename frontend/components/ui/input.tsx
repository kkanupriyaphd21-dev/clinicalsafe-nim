import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-lg border border-surface-2 bg-ink px-3 py-2 text-sm text-parchment placeholder:text-cortex focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[120px] w-full rounded-lg border border-surface-2 bg-ink px-3 py-2 text-sm text-parchment placeholder:text-cortex focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50 resize-y",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";

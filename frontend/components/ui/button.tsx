import { forwardRef } from "react";
import { cn } from "@/lib/cn";

/**
 * primary   lime: the one main forward action on a screen (Start, Build cart)
 * positive  green: accept / confirm / save
 * danger    red: remove / reject
 * secondary, ghost: everything else
 */
type Variant = "primary" | "positive" | "danger" | "secondary" | "ghost";

const styles: Record<Variant, string> = {
  primary: "bg-primary text-primary-fg hover:bg-primary-hover",
  positive: "bg-positive text-positive-fg hover:brightness-110",
  danger: "border border-negative/40 text-negative hover:bg-negative/10",
  secondary: "bg-surface text-fg border border-line hover:bg-surface-2",
  ghost: "text-muted hover:text-fg hover:bg-surface-2",
};

export const Button = forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }
>(function Button({ variant = "primary", className, ...props }, ref) {
  return (
    <button
      ref={ref}
      className={cn(
        "press inline-flex h-8 items-center justify-center gap-1.5 whitespace-nowrap rounded-control px-3 text-[13px] font-medium",
        "transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-ink",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
});

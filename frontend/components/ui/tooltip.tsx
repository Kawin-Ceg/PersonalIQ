import { useId } from "react";
import { cn } from "@/lib/cn";

type Side = "top" | "right" | "bottom";

const POSITION: Record<Side, string> = {
  top: "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-1.5 -translate-x-1/2",
  right: "left-full top-1/2 ml-2 -translate-y-1/2",
};

/**
 * Hover or keyboard-focus hint. CSS only, so it costs nothing to render.
 * Shows after a short delay so it doesn't flicker while the pointer passes over.
 */
export function Tooltip({
  label,
  side = "top",
  children,
  className,
}: {
  label: string;
  side?: Side;
  children: React.ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <span className={cn("group/tt relative inline-flex", className)} aria-describedby={id}>
      {children}
      <span
        role="tooltip"
        id={id}
        className={cn(
          "pointer-events-none absolute z-[var(--z-overlay)] w-max max-w-64 rounded-control border border-line-strong bg-surface-2 px-2 py-1",
          "text-left text-xs font-normal normal-case tracking-normal text-fg shadow-[0_4px_16px_rgb(0_0_0/0.25)]",
          "invisible opacity-0 transition-opacity duration-150 group-hover/tt:visible group-hover/tt:opacity-100 group-hover/tt:delay-300",
          "group-has-[:focus-visible]/tt:visible group-has-[:focus-visible]/tt:opacity-100",
          POSITION[side],
        )}
      >
        {label}
      </span>
    </span>
  );
}

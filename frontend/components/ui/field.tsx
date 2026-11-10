import { cn } from "@/lib/cn";

/** Label above, helper below. Never placeholder-as-label. */
export function Field({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-fg">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-subtle">{hint}</p>}
    </div>
  );
}

export const inputClass = cn(
  "h-8 w-full rounded-control border border-line bg-surface px-2.5 text-[13px] text-fg outline-none",
  "placeholder:text-subtle focus:border-line-strong",
);

/** Toggleable chip for multi-select lists. */
export function Chip({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={cn(
        "h-7 rounded-full border px-3 text-[13px] font-medium",
        selected ? "border-line-strong bg-surface-2 text-fg" : "border-line text-muted hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

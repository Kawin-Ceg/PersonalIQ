import { cn } from "@/lib/cn";

export type TabItem<T extends string> = { value: T; label: string; icon?: React.ReactNode; count?: number };

/** Page-level tabs (underline style). Splits a long page into focused views. */
export function Tabs<T extends string>({ items, value, onChange, label }: { items: TabItem<T>[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="-mb-px flex gap-1 overflow-x-auto border-b border-line">
      {items.map((t) => {
        const active = t.value === value;
        return (
          <button
            key={t.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.value)}
            className={cn(
              "flex h-10 shrink-0 items-center gap-2 border-b-2 px-3 text-[13px] font-medium",
              active ? "border-fg text-fg" : "border-transparent text-muted hover:text-fg",
            )}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && <span className="tabular text-xs text-subtle">{t.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

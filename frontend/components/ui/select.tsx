import { CaretDown } from "@phosphor-icons/react/dist/ssr";
import { cn } from "@/lib/cn";

/** Native select (keyboard and screen-reader friendly), styled to match. */
export function Select<T extends string>({
  label,
  value,
  onChange,
  options,
  className,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
}) {
  return (
    <label className={cn("relative flex h-8 min-w-0 items-center rounded-control border border-line bg-surface text-[13px] focus-within:border-line-strong", className)}>
      <span className="shrink-0 pl-2.5 pr-1 text-subtle">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="h-full min-w-0 flex-1 cursor-pointer appearance-none truncate bg-transparent pl-1 pr-7 font-medium text-fg outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-panel text-fg">
            {o.label}
          </option>
        ))}
      </select>
      <CaretDown size={12} className="pointer-events-none absolute right-2.5 text-subtle" aria-hidden />
    </label>
  );
}

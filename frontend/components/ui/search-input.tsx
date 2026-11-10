"use client";

import { MagnifyingGlass, X } from "@phosphor-icons/react";
import { Tooltip } from "./tooltip";

export function SearchInput({
  value,
  onChange,
  placeholder,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  label: string;
}) {
  return (
    <div className="flex h-10 w-full items-center gap-2.5 rounded-control border border-line bg-surface px-3 focus-within:border-line-strong">
      <MagnifyingGlass size={16} className="shrink-0 text-muted" aria-hidden />
      <input
        type="search"
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && onChange("")}
        placeholder={placeholder}
        className="h-full w-full bg-transparent text-[14px] text-fg outline-none placeholder:text-subtle [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <Tooltip label="Clear search (Esc)">
          <button type="button" aria-label="Clear search" onClick={() => onChange("")} className="grid size-6 place-items-center rounded-control text-subtle hover:bg-surface-2 hover:text-fg">
            <X size={14} />
          </button>
        </Tooltip>
      )}
    </div>
  );
}

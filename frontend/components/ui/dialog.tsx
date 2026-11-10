"use client";

import { useEffect, useRef } from "react";
import { X } from "@phosphor-icons/react";
import { cn } from "@/lib/cn";
import { Tooltip } from "./tooltip";

/**
 * Pop-up detail view. Built on the native <dialog>: focus is trapped, Esc closes, the page behind is inert.
 * Clicking the backdrop also closes it. On phones it becomes a bottom sheet.
 */
export function Dialog({
  open,
  onClose,
  title,
  subtitle,
  icon,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="dialog-title"
      className={cn(
        "dialog m-0 mt-auto w-full max-w-none rounded-t-panel border border-line-strong bg-panel p-0 text-fg",
        "sm:m-auto sm:rounded-panel",
        wide ? "sm:max-w-3xl" : "sm:max-w-xl",
      )}
    >
      {open && (
        <div className="flex max-h-[85dvh] flex-col">
          <header className="flex items-start gap-3 border-b border-line px-5 py-4">
            {icon && <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-control border border-line bg-surface text-muted">{icon}</span>}
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <h2 id="dialog-title" className="text-[15px] font-semibold text-fg">
                {title}
              </h2>
              {subtitle && <p className="text-[13px] text-muted">{subtitle}</p>}
            </div>
            <Tooltip label="Close (Esc)" side="bottom">
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="grid size-8 place-items-center rounded-control text-subtle hover:bg-surface-2 hover:text-fg"
              >
                <X size={16} />
              </button>
            </Tooltip>
          </header>
          {/* autoFocus here so opening the dialog doesn't land focus on the close button */}
          <div autoFocus tabIndex={-1} className="flex-1 overflow-y-auto px-5 py-4 outline-none">
            {children}
          </div>
          {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}

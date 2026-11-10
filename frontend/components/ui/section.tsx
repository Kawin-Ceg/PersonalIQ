/** A titled block on a page. Every section has an icon so pages are easy to scan. */
export function Section({
  title,
  description,
  icon,
  action,
  children,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          {icon && (
            <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-control border border-line bg-surface text-muted">
              {icon}
            </span>
          )}
          <div className="flex flex-col">
            <h3 className="text-[14px] font-semibold text-fg">{title}</h3>
            {description && <p className="text-[13px] text-muted">{description}</p>}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  description,
  icon,
  actions,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="flex items-start gap-3">
        {icon && (
          <span aria-hidden className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-card border border-line bg-surface text-fg">
            {icon}
          </span>
        )}
        <div className="flex flex-col gap-1">
          <h2 className="text-xl font-semibold tracking-[-0.01em] text-fg">{title}</h2>
          {description && <p className="max-w-[64ch] text-[14px] leading-relaxed text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-4 rounded-card border border-dashed border-line-strong px-6 py-8 md:px-8">
      <div className="grid size-9 place-items-center rounded-control border border-line bg-surface text-muted">{icon}</div>
      <div className="flex flex-col gap-1.5">
        <h2 className="text-[14px] font-medium text-fg">{title}</h2>
        <p className="max-w-[56ch] text-[13px] leading-relaxed text-muted">{body}</p>
      </div>
      {action}
    </div>
  );
}

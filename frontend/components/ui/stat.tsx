/** A figure in the Ramp style: small uppercase label, value in a bordered chip. For key money figures only. */
export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <span className="font-mono text-[11px] uppercase tracking-[0.04em] text-subtle">{label}</span>
      <span className="tabular rounded-[4px] border border-line bg-surface px-1.5 py-0.5 font-mono text-xs text-fg">{value}</span>
    </span>
  );
}

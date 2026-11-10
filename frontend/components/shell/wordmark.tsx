import Link from "next/link";

/** Half-disc on a baseline: the PersonalIQ mark. */
export function Wordmark() {
  return (
    <Link href="/" className="flex items-center gap-2.5 rounded-control focus-visible:outline-2 focus-visible:outline-accent-ink">
      <span aria-hidden className="flex h-5 w-5 flex-col items-center justify-end">
        <span className="h-2.5 w-5 rounded-t-full bg-accent" />
        <span className="mt-[2px] h-[2px] w-5 rounded-full bg-fg/80" />
      </span>
      <span className="text-[14px] font-semibold tracking-[-0.01em] text-fg">PersonalIQ</span>
    </Link>
  );
}

"use client";

import { useRef, useState } from "react";
import { UploadSimple } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { apiPost } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { UserContext } from "@/types/api";

type ImportResult = { imported: number; duplicates: number; errors: string[] };

export function SpendingPanel({ spending, onImported }: { spending: UserContext["spending"]; onImported: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await apiPost<ImportResult>("/me/transactions/import", { csv: await file.text() });
      setResult(r);
      if (r.imported) onImported();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-card border border-line p-4">
      {spending ? (
        <>
          <dl className="flex flex-wrap gap-x-10 gap-y-3">
            <div className="flex flex-col gap-0.5">
              <dt className="text-xs text-subtle">Last {spending.window_days} days</dt>
              <dd className="tabular text-lg font-semibold text-fg">{formatMoney(spending.total, spending.currency)}</dd>
            </div>
            <div className="flex flex-col gap-0.5">
              <dt className="text-xs text-subtle">Per month</dt>
              <dd className="tabular text-lg font-semibold text-fg">{formatMoney(spending.monthly_average, spending.currency)}</dd>
            </div>
          </dl>
          <ul className="flex flex-col gap-2">
            {spending.by_category.map((c) => (
              <li key={c.category} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-[13px]">
                  <span className="text-muted">{c.category}</span>
                  <span className="tabular text-fg">
                    {formatMoney(c.total, spending.currency)} <span className="text-subtle">{c.share_pct}%</span>
                  </span>
                </div>
                {/* Share of spend, no background track */}
                <span className="h-1 rounded-full bg-line-strong" style={{ width: `${Math.max(c.share_pct, 2)}%` }} aria-hidden />
              </li>
            ))}
          </ul>
          <p className="text-xs text-subtle">
            {spending.transaction_count} transactions. Most often at {spending.top_merchants.join(", ")}.
          </p>
        </>
      ) : (
        <p className="text-[13px] text-muted">No spending history yet. Upload a CSV so PersonalIQ can compare new purchases to your usual spending.</p>
      )}

      <div className="flex flex-col gap-2 border-t border-line pt-4">
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          id="csv-upload"
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
        <Button variant="secondary" className="w-fit" disabled={busy} onClick={() => fileRef.current?.click()}>
          <UploadSimple size={14} aria-hidden />
          {busy ? "Uploading" : "Upload transactions CSV"}
        </Button>
        <p className="text-xs text-subtle">
          Columns: <span className="font-mono">date, merchant, category, amount</span>. Uploading the same file twice adds nothing.
        </p>
        {result && (
          <p role="status" className="text-xs text-muted">
            Added {result.imported}, skipped {result.duplicates} already uploaded
            {result.errors.length > 0 && `, ${result.errors.length} with problems: ${result.errors.slice(0, 2).join("; ")}`}.
          </p>
        )}
        {error && <p className="text-xs text-negative">{error}</p>}
      </div>
    </div>
  );
}

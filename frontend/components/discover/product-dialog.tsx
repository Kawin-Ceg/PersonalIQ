"use client";

import { Prohibit, Star } from "@phosphor-icons/react";
import { CategoryIcon } from "@/components/ui/category-icon";
import { Dialog } from "@/components/ui/dialog";
import { Tooltip } from "@/components/ui/tooltip";
import { formatCount, formatMoney, needLabel } from "@/lib/format";
import { SCORE_LABEL } from "@/lib/personal";
import type { Product, ScoreComponent } from "@/types/api";

export type ProductView = {
  product: Product;
  score?: number;
  rank?: number;
  components?: ScoreComponent[];
  excluded?: string[];
  note?: string; // extra context, e.g. why the cart picked it
};

const FACTOR_HINT: Record<string, string> = {
  quality: "Curated quality score for the product, 0 to 100.",
  value: "Quality and durability per unit of price, compared with other options for the same need.",
  price: "100 for the cheapest option for this need; pricier options score lower.",
  durability: "Curated durability score, 0 to 100.",
  fit: "Your preferences: stores you like, past ratings, buyer reviews.",
};

/** Full detail for one product: price, why it ranks where it does, and the facts. */
export function ProductDialog({ view, onClose }: { view: ProductView | null; onClose: () => void }) {
  const p = view?.product;
  return (
    <Dialog
      open={!!view}
      onClose={onClose}
      wide
      icon={p ? <CategoryIcon category={p.category} size={16} /> : null}
      title={p?.name ?? ""}
      subtitle={p ? `${p.merchant.name} · ${needLabel(p.attributes.need ?? "general")}` : undefined}
    >
      {view && p && (
        <div className="flex flex-col gap-6 text-[13px]">
          {/* Price and score */}
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-col gap-0.5">
              <span className="tabular text-2xl font-semibold text-fg">{formatMoney(p.price, p.currency)}</span>
              {p.base_price && p.base_currency && p.base_currency !== p.currency && (
                <span className="text-xs text-subtle">
                  Catalog price {formatMoney(p.base_price, p.base_currency)}, converted at a fixed demo rate
                </span>
              )}
            </div>
            {view.score !== undefined && (
              <div className="flex flex-col items-end gap-0.5">
                <span className="tabular text-2xl font-semibold text-fg">{view.score.toFixed(1)}</span>
                <span className="text-xs text-subtle">{view.rank === 1 ? "Best match for you" : `#${view.rank} for this need`}</span>
              </div>
            )}
          </div>

          {view.note && <p className="rounded-card border border-line bg-surface px-3 py-2 text-muted">{view.note}</p>}

          {view.excluded && (
            <div className="flex items-start gap-2.5 rounded-card border border-negative/40 px-3 py-2.5">
              <Prohibit size={16} className="mt-0.5 shrink-0 text-negative" aria-hidden />
              <div className="flex flex-col gap-0.5">
                <p className="font-medium text-fg">Left out of your recommendations</p>
                {view.excluded.map((r) => (
                  <p key={r} className="text-muted">
                    {r}
                  </p>
                ))}
              </div>
            </div>
          )}

          {view.components && (
            <div className="flex flex-col gap-2">
              <p className="font-semibold text-fg">How the score is built</p>
              <ul className="divide-y divide-line overflow-hidden rounded-card border border-line">
                {view.components.map((c) => (
                  <li key={c.key} className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5 px-3 py-2">
                    <Tooltip label={FACTOR_HINT[c.key]} side="right" className="w-36 shrink-0">
                      <span tabIndex={0} className="cursor-help font-medium text-fg underline decoration-line-strong decoration-dotted underline-offset-4">
                        {SCORE_LABEL[c.key]}
                      </span>
                    </Tooltip>
                    <span className="order-3 w-full text-muted sm:order-none sm:w-auto sm:flex-1">{c.reason}</span>
                    <span className="tabular ml-auto text-right text-muted sm:ml-0">
                      {c.value} x {Math.round(c.weight * 100)}% = <span className="font-medium text-fg">{c.contribution.toFixed(1)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <p className="font-semibold text-fg">Details</p>
            <p className="leading-relaxed text-muted">{p.description}</p>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Fact label="Rating">
                <span className="inline-flex items-center gap-1">
                  <Star size={12} weight="fill" className="text-caution" aria-hidden />
                  {p.rating.toFixed(1)} <span className="text-subtle">({formatCount(p.review_count)})</span>
                </span>
              </Fact>
              <Fact label="Warranty">{p.warranty_months ? `${p.warranty_months} months` : "None"}</Fact>
              <Fact label="Returns">{p.merchant.return_window_days} days</Fact>
              <Fact label="SKU">
                <span className="font-mono text-xs">{p.sku}</span>
              </Fact>
              <Fact label="Materials" wide>
                {p.attributes.materials?.length ? p.attributes.materials.join(", ") : "Not listed"}
              </Fact>
            </dl>
          </div>
        </div>
      )}
    </Dialog>
  );
}

function Fact({ label, children, wide }: { label: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className={`flex flex-col gap-0.5 rounded-card border border-line px-3 py-2 ${wide ? "col-span-2 sm:col-span-4" : ""}`}>
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="text-fg">{children}</dd>
    </div>
  );
}

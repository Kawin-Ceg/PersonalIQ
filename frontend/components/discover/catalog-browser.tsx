"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CaretDown, Eye, EyeSlash, Star } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { CategoryIcon } from "@/components/ui/category-icon";
import { SearchInput } from "@/components/ui/search-input";
import { Select } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";
import { apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatMoney, needLabel } from "@/lib/format";
import type { RankingResponse } from "@/types/api";
import { ProductDialog, type ProductView } from "./product-dialog";

type Load = { state: "loading" } | { state: "error" } | { state: "ready"; rows: ProductView[] };
type Sort = "best" | "price_asc" | "price_desc" | "rating";

const PER_GROUP = 5; // keep lists short; the rest is one click away

// Shared by header and rows so columns line up.
const COLS = "grid grid-cols-[minmax(0,1fr)_auto] md:grid-cols-[minmax(0,1fr)_170px_76px_64px_110px] items-center gap-x-4";

export function CatalogBrowser() {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [category, setCategory] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("best");
  const [showExcluded, setShowExcluded] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<ProductView | null>(null);

  const fetchRanking = useCallback(() => {
    setLoad({ state: "loading" });
    apiGet<RankingResponse>("/products/ranked")
      .then((r) =>
        setLoad({
          state: "ready",
          rows: [
            ...r.ranked.map((x) => ({ product: x.product, score: x.score, rank: x.rank, components: x.components })),
            ...r.excluded.map((x) => ({ product: x.product, excluded: x.reasons })),
          ],
        }),
      )
      .catch(() => setLoad({ state: "error" }));
  }, []);
  useEffect(() => {
    fetchRanking();
  }, [fetchRanking]);

  const rows = useMemo(() => (load.state === "ready" ? load.rows : []), [load]);
  const excludedCount = rows.filter((r) => r.excluded).length;

  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows) if (showExcluded || !r.excluded) counts.set(r.product.category, (counts.get(r.product.category) ?? 0) + 1);
    return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [rows, showExcluded]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const visible = rows.filter(
      (r) =>
        (showExcluded || !r.excluded) &&
        (!category || r.product.category === category) &&
        (!q || [r.product.name, r.product.merchant.name, r.product.attributes.need ?? ""].some((s) => s.toLowerCase().includes(q))),
    );
    const price = (r: ProductView) => Number(r.product.price);
    const cmp: Record<Sort, (a: ProductView, b: ProductView) => number> = {
      // Best matches first: rank 1 of every need, then rank 2, ... left-out items last.
      best: (a, b) => Number(!!a.excluded) - Number(!!b.excluded) || (a.rank ?? 99) - (b.rank ?? 99) || (b.score ?? 0) - (a.score ?? 0),
      price_asc: (a, b) => price(a) - price(b),
      price_desc: (a, b) => price(b) - price(a),
      rating: (a, b) => b.product.rating - a.product.rating,
    };
    visible.sort(cmp[sort]);
    const byCat = new Map<string, ProductView[]>();
    for (const r of visible) byCat.set(r.product.category, [...(byCat.get(r.product.category) ?? []), r]);
    return [...byCat.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [rows, category, query, sort, showExcluded]);

  function open(view: ProductView) {
    setSelected(view);
    // Observed behaviour for the Personal Intelligence Engine. Best effort, never blocks the UI.
    apiPost("/me/events", { event_type: "product_view", product_id: view.product.id }).catch(() => {});
  }

  if (load.state === "error") {
    return (
      <div className="flex flex-col items-start gap-3 rounded-card border border-line px-6 py-8">
        <p className="text-[14px] font-medium text-fg">Couldn&apos;t load the catalog</p>
        <p className="text-[13px] text-muted">Check that the API is running on port 8000, then try again.</p>
        <Button variant="secondary" onClick={fetchRanking}>
          Try again
        </Button>
      </div>
    );
  }

  const shown = groups.reduce((n, [, items]) => n + items.length, 0);

  return (
    <div className="flex flex-col gap-4">
      {/* 1. Search */}
      <SearchInput value={query} onChange={setQuery} label="Search products" placeholder="Search by product, store or need, e.g. chair" />

      {/* 2. Categories, then sort and toggles */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div role="tablist" aria-label="Category" className="flex flex-wrap gap-1.5">
          <CategoryChip label="All" count={categories.reduce((n, [, c]) => n + c, 0)} active={!category} onClick={() => setCategory(null)} />
          {categories.map(([c, n]) => (
            <CategoryChip key={c} label={c} count={n} icon={<CategoryIcon category={c} />} active={category === c} onClick={() => setCategory(c)} />
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Select<Sort>
            label="Sort"
            value={sort}
            onChange={setSort}
            options={[
              { value: "best", label: "Best for you" },
              { value: "price_asc", label: "Price, low to high" },
              { value: "price_desc", label: "Price, high to low" },
              { value: "rating", label: "Buyer rating" },
            ]}
          />
          {excludedCount > 0 && (
            <Tooltip label="Products left out because of your preferences, like materials you avoid or items you rated badly.">
              <button
                type="button"
                aria-pressed={showExcluded}
                onClick={() => setShowExcluded(!showExcluded)}
                className={cn(
                  "flex h-8 items-center gap-1.5 rounded-control border px-2.5 text-[13px] font-medium",
                  showExcluded ? "border-line-strong bg-surface-2 text-fg" : "border-line text-muted hover:text-fg",
                )}
              >
                {showExcluded ? <Eye size={14} /> : <EyeSlash size={14} />}
                Left out <span className="tabular text-xs text-subtle">{excludedCount}</span>
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* 3. Grouped list */}
      <div className="overflow-hidden rounded-card border border-line">
        <div className={cn(COLS, "hidden h-9 border-b border-line bg-surface px-4 text-xs font-medium text-subtle md:grid")}>
          <span>Product</span>
          <span>Store</span>
          <Tooltip label="How well this matches your priorities, 0 to 100. Open a product to see how it's built." className="justify-self-end">
            <span tabIndex={0} className="cursor-help underline decoration-dotted underline-offset-4">
              Your score
            </span>
          </Tooltip>
          <Tooltip label="Average buyer rating out of 5." className="justify-self-end">
            <span tabIndex={0} className="cursor-help underline decoration-dotted underline-offset-4">
              Rating
            </span>
          </Tooltip>
          <span className="text-right">Price</span>
        </div>

        {load.state === "loading" && <SkeletonRows />}
        {load.state === "ready" && shown === 0 && (
          <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
            <p className="text-[13px] text-muted">Nothing matches &ldquo;{query}&rdquo;.</p>
            <Button variant="secondary" onClick={() => setQuery("")}>
              Clear search
            </Button>
          </div>
        )}

        {groups.map(([cat, items]) => {
          const isOpen = expanded.has(cat) || !!query || !!category;
          const visible = isOpen ? items : items.slice(0, PER_GROUP);
          return (
            <section key={cat} aria-label={cat}>
              <div className="flex h-10 items-center gap-2 border-b border-line bg-surface/60 px-4 text-[13px]">
                <span className="text-muted">
                  <CategoryIcon category={cat} />
                </span>
                <span className="font-semibold text-fg">{cat}</span>
                <span className="tabular text-subtle">{items.length}</span>
              </div>
              {visible.map((r) => (
                <ProductRow key={r.product.id} row={r} onOpen={() => open(r)} />
              ))}
              {items.length > visible.length && (
                <button
                  type="button"
                  onClick={() => setExpanded(new Set(expanded).add(cat))}
                  className="flex h-10 w-full items-center gap-1.5 border-b border-line px-4 text-[13px] font-medium text-muted last:border-b-0 hover:bg-surface hover:text-fg"
                >
                  <CaretDown size={12} aria-hidden />
                  Show {items.length - visible.length} more in {cat}
                </button>
              )}
            </section>
          );
        })}
      </div>

      <ProductDialog view={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function CategoryChip({ label, count, icon, active, onClick }: { label: string; count?: number; icon?: React.ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium",
        active ? "border-line-strong bg-surface-2 text-fg" : "border-line text-muted hover:text-fg",
      )}
    >
      {icon}
      {label}
      {count !== undefined && <span className="tabular text-xs text-subtle">{count}</span>}
    </button>
  );
}

function ProductRow({ row, onOpen }: { row: ProductView; onOpen: () => void }) {
  const p = row.product;
  const label = needLabel(p.attributes.need ?? "general");
  const need = label === "TV" ? label : label.charAt(0).toLowerCase() + label.slice(1);
  return (
    <button
      onClick={onOpen}
      className={cn(COLS, "w-full border-b border-line px-4 py-2.5 text-left last:border-b-0 hover:bg-surface md:h-12 md:py-0")}
    >
      <span className="flex min-w-0 flex-col">
        <span className={cn("truncate text-[13px] font-medium", row.excluded ? "text-subtle line-through decoration-line-strong" : "text-fg")}>{p.name}</span>
        <span className={cn("truncate text-xs", row.excluded ? "text-negative" : row.rank === 1 ? "text-positive" : "text-subtle")}>
          {row.excluded ? `Left out: ${row.excluded[0]}` : row.rank === 1 ? `Best ${need} for you` : `#${row.rank} ${need}`}
          <span className="text-subtle md:hidden"> · {p.merchant.name}</span>
        </span>
      </span>
      <span className="hidden truncate text-[13px] text-muted md:block">{p.merchant.name}</span>
      <span className={cn("tabular hidden text-right text-[13px] md:block", row.rank === 1 ? "font-semibold text-fg" : "text-muted")}>
        {row.score !== undefined ? row.score.toFixed(1) : "-"}
      </span>
      <span className="tabular hidden items-center justify-end gap-1 text-[13px] text-muted md:flex">
        <Star size={12} weight="fill" className="text-caution" aria-hidden />
        {p.rating.toFixed(1)}
      </span>
      <span className={cn("tabular text-right text-[13px] font-medium", row.excluded ? "text-subtle" : "text-fg")}>{formatMoney(p.price, p.currency)}</span>
    </button>
  );
}

function SkeletonRows() {
  return (
    <div aria-busy="true" aria-label="Loading catalog">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className={cn(COLS, "h-12 border-b border-line px-4 last:border-b-0")}>
          <span className="skeleton h-3" style={{ width: `${45 + ((i * 17) % 35)}%` }} />
          <span className="skeleton hidden h-3 w-24 md:block" />
          <span className="skeleton ml-auto hidden h-3 w-8 md:block" />
          <span className="skeleton ml-auto hidden h-3 w-8 md:block" />
          <span className="skeleton ml-auto h-3 w-16" />
        </div>
      ))}
    </div>
  );
}

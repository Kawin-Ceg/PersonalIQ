"use client";

import { useState } from "react";
import { ListMagnifyingGlass, ShoppingCart } from "@phosphor-icons/react";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { CartPlanner } from "./cart-planner";
import { CatalogBrowser } from "./catalog-browser";

type Tab = "catalog" | "cart";

export function DiscoverView() {
  const [tab, setTab] = useState<Tab>("catalog");
  return (
    <>
      <PageHeader
        icon={<ListMagnifyingGlass size={18} />}
        title="Discover"
        description="Products ranked with your priorities, and a planner that builds the best cart within your budget. Demo catalog: prices and scores are sample data."
      />
      <Tabs<Tab>
        label="Discover views"
        value={tab}
        onChange={setTab}
        items={[
          { value: "catalog", label: "Ranked for you", icon: <ListMagnifyingGlass size={14} /> },
          { value: "cart", label: "Plan a cart", icon: <ShoppingCart size={14} /> },
        ]}
      />
      {tab === "catalog" ? <CatalogBrowser /> : <CartPlanner />}
    </>
  );
}

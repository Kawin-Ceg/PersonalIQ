"use client";

import { Armchair, Broom, CookingPot, HouseLine, Package, Television } from "@phosphor-icons/react";

const ICONS: Record<string, typeof Armchair> = {
  Furniture: Armchair,
  Kitchen: CookingPot,
  Electronics: Television,
  Cleaning: Broom,
  Household: HouseLine,
};

export function CategoryIcon({ category, size = 14 }: { category: string; size?: number }) {
  const Icon = ICONS[category] ?? Package;
  return <Icon size={size} aria-hidden />;
}

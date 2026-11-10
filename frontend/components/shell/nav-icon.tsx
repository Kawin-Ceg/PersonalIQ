"use client";

import {
  ChartDonut,
  ClockCounterClockwise,
  House,
  MagnifyingGlass,
  Receipt,
  SealCheck,
  UserCircle,
  type IconProps,
} from "@phosphor-icons/react";
import type { NavIconName } from "@/lib/nav";

const ICONS: Record<NavIconName, React.ComponentType<IconProps>> = {
  home: House,
  you: UserCircle,
  activity: ClockCounterClockwise,
  discover: MagnifyingGlass,
  finance: ChartDonut,
  approvals: SealCheck,
  purchases: Receipt,
};

export function NavIcon({ name, active, size = 16 }: { name: NavIconName; active: boolean; size?: number }) {
  const Icon = ICONS[name];
  return <Icon size={size} weight={active ? "fill" : "regular"} aria-hidden />;
}

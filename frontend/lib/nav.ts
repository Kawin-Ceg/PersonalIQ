export type NavIconName = "home" | "you" | "activity" | "discover" | "finance" | "approvals" | "purchases";

export type NavItem = { href: string; label: string; icon: NavIconName; hint: string };

export type NavGroup = { label?: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    items: [
      { href: "/", label: "Home", icon: "home", hint: "Tell PersonalIQ what you need" },
      { href: "/you", label: "You", icon: "you", hint: "Your preferences, memories and spending" },
      { href: "/activity", label: "Activity", icon: "activity", hint: "What the agents are doing right now" },
    ],
  },
  {
    label: "Shopping",
    items: [
      { href: "/discover", label: "Discover", icon: "discover", hint: "Browse ranked products and plan a cart" },
      { href: "/approvals", label: "Approvals", icon: "approvals", hint: "Purchases waiting for your yes" },
      { href: "/purchases", label: "Purchases", icon: "purchases", hint: "Paid orders and decision receipts" },
    ],
  },
  {
    label: "Money",
    items: [{ href: "/finance", label: "Finance", icon: "finance", hint: "Budgets and what you have left" }],
  },
];

export const NAV: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

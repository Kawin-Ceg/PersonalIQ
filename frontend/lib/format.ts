// Each currency is shown the way its users expect: INR groups as 1,69,000; SEK puts "kr" after.
const LOCALE: Record<string, string> = { USD: "en-US", INR: "en-IN", SEK: "sv-SE", EUR: "en-IE", GBP: "en-GB" };

/** Display only: the server already converted the amount into the user's currency. */
export function formatMoney(amount: string, currency = "USD") {
  return new Intl.NumberFormat(LOCALE[currency] ?? "en-US", { style: "currency", currency }).format(Number(amount));
}

export function currencySymbol(currency: string) {
  const parts = new Intl.NumberFormat(LOCALE[currency] ?? "en-US", { style: "currency", currency }).formatToParts(0);
  return parts.find((p) => p.type === "currency")?.value ?? currency;
}

export function formatCount(n: number) {
  return new Intl.NumberFormat("en-US").format(n);
}

export function humanize(slug: string) {
  const s = slug.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const NEED_LABEL: Record<string, string> = {
  tv: "TV",
  power: "Surge protector",
  trash: "Trash can",
  supplies: "Cleaning supplies",
  lighting: "Lamp",
  first_aid: "First aid kit",
  dining: "Dining set",
  coffee: "Coffee maker",
  storage: "Bookcase",
  tools: "Tool kit",
};

/** Human label for a catalog need, e.g. "office_chair" -> "Office chair". */
export function needLabel(need: string) {
  return NEED_LABEL[need] ?? humanize(need);
}

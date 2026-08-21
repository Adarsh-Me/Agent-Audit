/** Formatting helpers — Indian digit grouping, CI display convention (APPFLOW §1.2). */

const inrFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** 40960 → "₹40,960" */
export function inr(n: number): string {
  return `₹${inrFmt.format(Math.round(n))}`;
}

/** 800000 → "₹8,00,000" (used inside inputs too) */
export function inrGrouped(n: number): string {
  return inrFmt.format(Math.round(n));
}

/** Parse a user-typed rupee amount tolerating commas/spaces/₹. Returns NaN if invalid. */
export function parseInr(text: string): number {
  const cleaned = text.replace(/[₹,\s]/g, "");
  if (!/^\d+$/.test(cleaned)) return NaN;
  return Number(cleaned);
}

/** 0.256 → "25.6%" */
export function pct(n: number, decimals = 1): string {
  return `${(n * 100).toFixed(decimals)}%`;
}

/** 48.02 → "48.0" (one decimal for scores/shares) */
export function num1(n: number): string {
  return n.toFixed(1);
}

export function num2(n: number): string {
  return n.toFixed(2);
}

/** "$12.34" from 12.3415 */
export function usd(n: number): string {
  return `$${n.toFixed(2)}`;
}

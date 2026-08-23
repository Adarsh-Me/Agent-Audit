/**
 * Merchant-friendly vocabulary — maps internal experiment codes to plain
 * language so the UI never shows a bare C1/C2/P07/F_task without context.
 * The codes stay available (tooltips / muted parens) for traceability.
 */

/** Shopper profiles used across all trials (backend: engine/personas/*.json). */
export const PERSONA_NAMES: Record<string, string> = {
  P01: 'Budget Student',
  P02: 'Gift Buyer',
  P03: 'Spec Hound',
  P04: 'Eco Buyer',
  P05: 'Commuter',
  P06: 'Premium Seeker',
  P07: 'Deal Hunter',
  P08: 'Urgent Buyer',
  P09: 'Brand Loyalist',
  P10: 'Minimalist',
  P11: 'Fitness Newcomer',
  P12: 'Parent',
  P13: 'Podcast Listener',
  P14: 'Gym Regular',
  P15: 'Trekker',
  P16: 'WFH Professional',
  P17: 'Gift-Card Spender',
  P18: 'Comparison Shopper',
  P19: 'Trend Follower',
  P20: 'Skeptic'
}

/** "P07" → "Deal Hunter (P07)" — name plus code for traceability. */
export function personaLabel(id: string): string {
  const name = PERSONA_NAMES[id]
  return name ? `${name}` : id
}

export type ConditionFamily = 'baseline' | 'shuffle' | 'rewrite'

export function conditionFamily(code: string): ConditionFamily {
  if (code.startsWith('C1')) return 'baseline'
  if (code.startsWith('C2')) return 'shuffle'
  return 'rewrite'
}

/** Short human label for a condition code — used where space is tight. */
export function conditionShort(code: string): string {
  switch (conditionFamily(code)) {
    case 'baseline':
      return 'normal order'
    case 'shuffle':
      return 'shuffled order'
    default:
      return 'reworded copy'
  }
}

/** One-line plain-language explanations of the three test families. */
export const CONDITION_EXPLAIN: Record<ConditionFamily, string> = {
  baseline:
    'Your catalog shown exactly as it is, repeated several times to establish the baseline.',
  shuffle:
    'Same catalog with listing order randomly shuffled — reveals how much placement alone drives agent choices.',
  rewrite:
    'Listing wording rewritten without changing any facts — reveals how sensitive agent choices are to phrasing.'
}

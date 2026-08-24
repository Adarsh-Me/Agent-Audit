// Builds the copy-paste "fix brief" a merchant gives to their AI coding agent
// (Cursor / Claude / Codex / …) so the audit's findings turn into applied fixes.
// Everything is grounded in the run's own measured numbers — nothing invented.
import type { ReportResponse } from '@/lib/api'
import { num1, num2, pct } from '@/lib/format'

const AGENT_TOOLS = 'Cursor, Claude Code, Codex, Windsurf, or any AI coding agent'

export function buildFixPrompt(report: ReportResponse): string {
  const L: string[] = []
  const nCatalog = report.legibility?.length || 40
  const fairShare = 1 / nCatalog
  const invSkus = report.invisible_skus ?? []

  const ci = (
    v: { value: number; ci_low: number; ci_high: number },
    fmt: (n: number) => string
  ) => `${fmt(v.value)} (95% CI ${fmt(v.ci_low)}–${fmt(v.ci_high)})`

  L.push('# Store Fix Brief — make this catalog AI-agent-ready')
  L.push('')
  L.push(
    `You are the web engineer for an e-commerce store that was just audited by ` +
      `AgentAudit (${report.trials.total} simulated AI-shopper missions ran against it). ` +
      `Your job: apply the evidence-backed fixes below so AI shopping agents can find, ` +
      `trust, and buy every product. Work through the sections in order and finish with ` +
      `the mandatory verification step.`
  )
  L.push('')

  // ---- context ----------------------------------------------------------
  L.push('## Measured baseline (from this audit — not guesses)')
  L.push(
    `- AgentReady Score: **${num1(report.score.value)}** ` +
      `(95% CI ${num1(report.score.ci_low)}–${num1(report.score.ci_high)}), ` +
      `${report.trials.parse_ok}/${report.trials.total} missions returned a usable agent answer`
  )
  L.push(
    `- Walk-away rate: **${ci(report.coverage.f_task, pct)}** of shopping missions ended ` +
      `with the agent buying nothing`
  )
  L.push(
    `- Demand concentration (HHI norm): **${ci(report.hhi_norm, num2)}** — ` +
      `closer to 0 means demand spreads evenly across products`
  )
  L.push(
    `- First-listing bias: top-3 slots capture **${ci(report.position.top3_capture, pct)}** of all ` +
      `choices; slot #1 is **${num1(report.position.lift)}×** more likely to be picked than chance` +
      (report.position.p_value < 0.05 ? ' (statistically significant)' : '')
  )
  L.push(
    `- Wording sensitivity: rewriting listing text shifted choices by ` +
      `**${ci(report.framing.mean_delta, pct)}** on average — phrasing alone moves sales`
  )
  L.push('')

  // ---- finding 1: invisible skus ---------------------------------------
  if (invSkus.length > 0) {
    L.push(`## Finding 1 — ${invSkus.length} product(s) are INVISIBLE to AI agents`)
    L.push(
      `Each SKU below gets fewer agent choices than a fair ${pct(fairShare)} equal split — ` +
        `even at the optimistic end of its range:`)
    L.push('')
    const legBySku = new Map((report.legibility ?? []).map(r => [r.sku, r]))

    for (const s of invSkus) {
      const leg = legBySku.get(s.sku)

      L.push(
        `- **${s.sku}**${leg ? ` "${leg.title}" (${leg.tier})` : ''} — choice share ` +
          `${pct(s.share.value)} (CI ${pct(s.share.ci_low)}–${pct(s.share.ci_high)})` +
          (leg?.composite != null ? `, legibility ${num2(leg.composite)}/1.00` : '')
      )
    }

    L.push('')
    L.push(
      `An agent picking products at random would out-sell these listings. Treat each one as ` +
        `a P0 fix using the fix pattern below.`
    )
    L.push('')
  }

  // ---- finding 2: weakest legibility ------------------------------------
  const weak = [...(report.legibility ?? [])]
    .filter(r => r.composite !== null)
    .sort((a, b) => (a.composite ?? 0) - (b.composite ?? 0))
    .slice(0, 6)

  if (weak.length > 0) {
    L.push('## Finding 2 — Weakest listing legibility (content & structured-data completeness)')
    L.push('')

    for (const r of weak) {
      L.push(`- **${r.sku}** "${r.title}" (${r.tier}) — legibility ${num2(r.composite ?? 0)}/1.00`)
    }

    L.push('')
  }

  // ---- fix pattern --------------------------------------------------------
  L.push('## Fix pattern — apply to EVERY flagged SKU (and any SKU missing these)')
  L.push('')
  L.push(
    `1. **Structured data**: attach complete JSON-LD \`Product\` schema — name, sku, brand, ` +
      `description, category, \`offers\` with price + \`priceCurrency: "INR"\` + availability, ` +
      `\`aggregateRating\` only if genuine reviews exist.`
  )
  L.push(
    `2. **Title**: lead with the category-defining noun phrase a buyer would search ` +
      `(e.g. "Insulated Steel Water Bottle 1L — Vacuum Flask"), keep it ≤ 70 characters, ` +
      `no marketing fluff before the product noun.`
  )
  L.push(
    `3. **Description**: state in plain prose — intended use case, key specs (material, size, ` +
      `capacity), price, and current stock status. Agents quote this text when deciding.`
  )
  L.push(
    `4. **Consistency**: price, availability, and specs must be IDENTICAL across the JSON-LD, ` +
      `the visible page text, and any merchant feed. Agents cross-check and walk away on mismatch.`
  )
  L.push(
    `5. **Sibling consistency**: products in the same category follow one content template ` +
      `(same field order, same spec vocabulary) so differences reflect the product, not the writing.`
  )
  L.push('')

  // ---- framing guidance ---------------------------------------------------
  const movers = [...(report.framing.per_product ?? [])]
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .slice(0, 5)

  if (movers.length > 0) {
    L.push('## Wording calibration (measured framers)')
    L.push(
      `These listings were re-worded during the audit and their choice share moved — align ` +
        `their live wording with whichever variant performed better, keeping facts identical:`
    )
    L.push('')

    for (const m of movers) {
      L.push(
        `- ${m.sku}: ${pct(m.share_a)} → ${pct(m.share_b)} when reworded ` +
          `(${m.delta >= 0 ? '+' : ''}${pct(m.delta)})`
      )
    }

    L.push('')
  }

  // ---- constraints ---------------------------------------------------------
  L.push('## Hard constraints')
  L.push('')
  L.push('- Do NOT change prices, discounts, stock quantities, or shipping terms.')
  L.push('- Do NOT redesign pages or remove existing content — metadata/markup/copy edits only.')
  L.push('- Do NOT fabricate ratings, reviews, or claims the store cannot substantiate.')
  L.push('- Keep each finding-group as a separate, reviewable commit.')
  L.push('')

  // ---- verification ----------------------------------------------------------
  L.push('## Verification (mandatory)')
  L.push('')
  L.push(
    `After applying the fixes, re-run the AgentAudit audit on the updated catalog ` +
      `(baseline run \`${report.run_id.slice(0, 8)}\`) and confirm:`
  )

  if (invSkus.length > 0) {
    L.push(
      `- every previously-invisible SKU (${invSkus.map(s => s.sku).join(', ')}) now clears the ` +
        `${pct(fairShare)} fair-share bar at its LOWER confidence bound`
    )
  }

  L.push(`- walk-away rate drops below today's ${pct(report.coverage.f_task.value)}`)
  L.push(
    `- top-3 capture moves toward the even-split expectation (~${pct(fairShare * 3)})`
  )
  L.push('')
  L.push(
    `Report the before→after deltas next to the commits. If a fix cannot be applied ` +
      `(e.g. no access to that system), say so explicitly instead of skipping silently.`
  )

  return L.join('\n')
}

/** Clipboard helper with execCommand fallback (non-secure contexts / older browsers). */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)

    return true
  } catch {
    try {
      const ta = document.createElement('textarea')

      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')

      document.body.removeChild(ta)

      return ok
    } catch {
      return false
    }
  }
}

export { AGENT_TOOLS }

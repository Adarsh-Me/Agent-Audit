# DESIGN.md — AgentAudit Visual System

*Distilled from `design-like-damien.skill.md` for a dense analytical dashboard, not a marketing site. ~20% of that doc applies here; this file is the part that does, rewritten against AgentAudit's actual screens (PRD §11 P1–P6, APPFLOW F1–F8). Where this file and the Damien skill disagree, this file wins for this project.*

---

## 0. Why this isn't a straight copy of the skill

Damien's system is built for landing pages and editorial sites — hero impact, scroll storytelling, generous 80–120px section padding. AgentAudit is a tool a judge clicks into wanting the AgentReady score and CI **immediately**, then drills into a heat map, a stability matrix, and a product table. Marketing-site rhythm (fade-up hero, staggered reveals, Lenis inertial scroll) actively slows down "find the number" — the opposite of what a dashboard needs. So: tokens and restraint principles are kept, scroll-cinema is cut.

One more thing worth naming honestly: near-black background + single accent is currently one of the most recognizable **AI-generated-design defaults**, not a distinctive choice, purely on its own. It's fine to use — it's genuinely correct for keeping a heat map and stability matrix legible — but it can't be the thing that makes this look designed. §1 below is what actually does that.

---

## 1. Signature move: measured vs. assumed is a typographic fact, not a label

This is the one place to spend design boldness, per the restraint principle — everywhere else stays quiet.

Every number in the product is either **measured** (from real trial data, with a CI) or **assumed** (a scenario input the user set, like the agent-traffic slider). PRD/TECHSPEC treat this as a labeling discipline already (`[measured]` / `[assumed]` tags throughout). Make it a **visual system**, not just bracketed text:

```
MEASURED values:
  Font:   Geist Mono (tabular figures)
  Color:  Primary text (#F5F5F5)
  Marker: solid 2px underline in the accent color, OR a filled dot before the value
  Always paired with a CI when one exists: "71 ±4" not just "71"

ASSUMED values:
  Font:   Geist (not mono — visually softer, less "computed")
  Color:  Secondary text (rgba(255,255,255,0.6))
  Marker: dashed 1px underline, no accent color
  Always paired with the control that set it (a slider, inline, not a separate legend)
```

Apply this pairing everywhere a number appears: the AgentReady score, the revenue strip, the coverage dial, the product table. A judge should be able to tell measured from assumed at a glance, without reading the word "measured" — that's the whole point of the audit tool, made literal in the UI. This is the signature element per the frontend-design process: the one thing this page is remembered by, and it's derived from the brief, not borrowed from a reference site.

---

## 2. Color tokens

```
Background:      #0A0A0A            (near-black, not pure black)
Surface:         #141414            (cards, panels)
Surface-raised:  #1A1A1A            (modals, the remediation diff overlay)
Border:          rgba(255,255,255,0.08)
Border-hover:    rgba(255,255,255,0.14)

Text-primary:    #F5F5F5
Text-secondary:  rgba(255,255,255,0.55)
Text-tertiary:   rgba(255,255,255,0.32)

Accent:          #4F8CFF   (electric blue — used ONLY for: primary CTA, active nav,
                            measured-value underline/dot, the AgentReady score number itself)
```

**Semantic colors — used only where the data genuinely warrants them, never decoratively:**
```
Invisible-SKU flag:   #FF6B5C  (warm red, ⚠ marker only — PRD M-6 agent-invisible products)
Positive delta:       #3DD68C  (score/coverage improving after remediation)
Neutral/pending:      Text-secondary (no color-coding until a state exists)
```

Rule from the skill that still holds exactly: **one accent, applied sparingly.** The invisible-SKU red and positive-delta green are data-state colors, not a second and third accent — they only ever appear attached to a specific flagged value, never as a UI chrome color.

---

## 3. Typography

```
Display / Headings & Score:  Geist        weight 600–700
Data / Numbers / Tables:     Geist Mono   (tabular figures — numbers must align in columns)
Body / Labels:                Geist       weight 400–500

Tracking:     -0.02em headings, 0 on Geist Mono (mono already reads as precise; extra
              negative tracking on tabular numbers makes digits misalign)
Line-height:  1.15 headings, 1.5 body, 1.4 in dense table rows
Uppercase:    Section eyebrows only ("REVENUE AT RISK", "COVERAGE") — tracking 0.06em,
              11px, weight 500. Never on body or product names.
```

Why Geist over the skill's Fraunces/Space Grotesk options: this isn't editorial (Fraunces) or motorsport (Space Grotesk) — it's the skill's own "Premium SaaS" pairing (Geist + Geist Mono), which is the correct match for a data-dense fintech-adjacent tool, and Geist Mono's tabular figures are load-bearing for §1's measured/assumed system.

---

## 4. Spacing, radius, shadow

```
Grid:          8pt base (8/16/24/32/48/64)
Card padding:  p-6 default, p-8 for the top summary strip (P3's score/RaR/recoverable row)
Section gap:   32–48px between dashboard sections — NOT the skill's 80–120px marketing
               default; this is a scan-for-data surface, not a scroll-story
Radius:        rounded-2xl on cards, rounded-lg (8px) on inline badges/pills/table chips
               — full rounded-2xl on a small SKU-flag chip reads soft/decorative, not precise
Shadow:        shadow-sm only, or none — cards are distinguished by the Surface color step
               and border, not by shadow
Border:        rgba(255,255,255,0.08) everywhere, no solid grays
```

---

## 5. Component specs, mapped to the actual screens

### P1 — Catalog input / audit start
Single centered card, not a full hero. One primary CTA ("Run audit"). No marketing copy — this is a tool, say what it does in one line and get out of the way (per the writing guidance: name things by what people control).

### P2 — Run progress
Trial counter in Geist Mono (`247 / 640 trials`), cost-so-far in Geist Mono, ETA in Geist (assumed/estimated, so it gets the dashed treatment from §1). No decorative loading animation beyond a simple determinate progress bar — the number *is* the progress indicator.

### P3 — Results (the core screen)
Top strip: AgentReady score (measured, solid underline + accent), Revenue at Risk (assumed S_agent, measured F_task — visually split per §1 inside the same figure), Recoverable (measured ΔF). This is the one place the skill's "generous padding" instinct is right — `p-8`, because this strip is the whole pitch and needs room to breathe against the denser sections below it.

Below: heat map (products × models) — accent-intensity scale for share, not a rainbow gradient; stability matrix — same restrained scale; position curve — accent line against a muted chance-line in text-tertiary; coverage dial — accent arc; product table — sortable, invisible SKUs get the red ⚠ chip from §2, everything else stays monochrome.

### P4 — Product drill-down (e.g. sku_023)
Structured-data checklist uses solid/dashed/red states directly, not a generic checkbox list: present-and-measured fields solid, missing fields in the red-flag color, nothing assumed here — everything on this screen is a measured fact about one product.

### P5 — Remediation diff view
Surface-raised modal. Before/after shown as a literal text diff (strikethrough old, accent-underline new) — not a generic "compare" card layout. This is the one screen where the skill's `shadow-sm` card-hover-state guidance is worth keeping, since it's the one interactive review moment in the product.

### P6 — Rerun / delta
Score transition (48 → 71) is the **only** place Framer Motion is used — see §6. Every other number on this screen follows the same measured/dashed system as P3.

### Checkout badge (F-agent-checkout)
"Agent checkout verified ✓" — small, solid, accent-colored, with timestamp and payment id in Geist Mono underneath. No celebratory animation; this is a receipt, not a milestone screen.

---

## 6. Motion — deliberately almost none

Kept from the skill: entrance-only, once, subtle, fast. Cut: Lenis, GSAP/ScrollTrigger, staggered hero reveals, scroll-triggered section fades — none of them serve a screen whose job is "let a judge find a number in under 3 seconds."

```
Used ONLY for:
1. P6 score transition (48 → 71): animate the number itself (not a fade-in of a
   static end value) over ~0.6s, ease [0.25, 0.1, 0.25, 1] — this is the one
   moment in the whole product where motion earns its place, because the
   movement IS the finding.
2. P5 diff reveal: the diff panel slides/fades in on open, 0.3s, once.

Everything else: no animation. Tables populate instantly. Charts render instantly.
A loading skeleton (static, no shimmer) is fine while data streams in via SSE —
shimmer/pulse effects read as decorative, not informative, on a data screen.
```

---

## 7. AgentAudit "Not AI" checklist

- [ ] Background is near-black (#0A0A0A), not pure black — but background alone is not the differentiator; §1's measured/assumed system is
- [ ] Exactly one accent color (#4F8CFF), used only on CTA / active nav / measured-value markers / the score number
- [ ] Invisible-SKU red and positive-delta green are data-state colors attached to specific values, never chrome
- [ ] Every number on screen is visibly either solid+mono (measured) or dashed+sans (assumed) — no unmarked numbers anywhere, including in the demo script's spoken claims
- [ ] No shimmer/pulse loading states — static skeletons only
- [ ] No animation outside §6's two named exceptions
- [ ] Geist Mono tabular figures used everywhere numbers appear in a column (product table, trial log) so digits align
- [ ] Section gaps are 32–48px, not marketing-site 80–120px
- [ ] Tested at 375px — the product table needs a genuine mobile layout (stacked cards), not a horizontally-scrolled table

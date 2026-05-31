# Design System — Forgetter (Bosch GDPR)

## Product Context

- **What this is:** Local-first GDPR data discovery + DSAR (data-subject access request) automation. Scans corporate drives for PII, links cross-document identities, executes Article 17 erasures, generates signed compliance certificates.
- **Who it's for:** Bosch DPO + IT teams (primary), DAX-40 enterprise compliance leads (expansion). Hackathon judges = BCG consultants + VCs + Bosch engineering.
- **Space:** Enterprise data governance. Direct rivals: Microsoft Purview, Varonis, OneTrust.
- **Project type:** Multi-persona web app + admin dashboard. Frontend = Next.js 16 in `frontend/`.

## Memorable Thing

> **"This looks like a forensic compliance dossier, not a dashboard."**

Every visual decision serves this. We are not building another Discord-themed AI tool.

## Aesthetic Direction

- **Direction:** Editorial Forensic. Paper-noir base, off-white type, single sharp signal color, hairline rules, generous whitespace, mono for evidence.
- **Decoration level:** Intentional. Subtle grain on surfaces, small-caps section labels, hairline dividers instead of boxed cards everywhere.
- **Mood:** Bloomberg Terminal × FT Investigations × Stripe internal dashboards. Trustworthy, technically credible, premium without being precious.
- **Reference vibe:** NYT digital investigations, Are.na, Linear release notes, FT Alphaville long reads, Stripe Atlas dashboards.

## Typography

Three fonts. No more.

- **Display (page titles, hero numbers, section titles):** **Instrument Serif** — Google Fonts, free. Transitional serif w/ contemporary spacing. Says "this is a document." Differentiates from every sans-serif AI tool in the category.
- **Body / UI:** **Geist** — Vercel's open sans. Clean, technical, has tabular-nums baked in. Used at 13-15px for body, 11-12px for meta.
- **Mono (data, IDs, paths, hashes, kbd):** **Geist Mono** — matches body family for harmony.

**Loading:** Google Fonts via `<link>` in app/layout.tsx, `font-display: swap`. No FOIT.

**Scale (modular, ratio 1.2):**
- `display-xl`: 64px / 1.05 / -0.02em (hero KPI numbers, screen-one impact)
- `display-lg`: 48px / 1.1 / -0.015em (page titles)
- `display-md`: 32px / 1.15 / -0.01em (section titles)
- `h1`: 24px / 1.25 / -0.005em
- `h2`: 18px / 1.35
- `body`: 14px / 1.55 — default UI text
- `body-sm`: 13px / 1.5 — table rows, dense lists
- `meta`: 11px / 1.4 / 0.08em uppercase — section labels, kicker text, pills
- `code-sm`: 12px / 1.5 — paths, IDs

**Type rules:**
- Display always serif. UI always Geist. Data always Geist Mono.
- Meta labels: small-caps + letter-spaced + dim color. ALWAYS uppercase.
- Numbers in KPIs: Geist Mono + tabular-nums for alignment.

## Color

- **Approach:** Restrained. Paper-noir neutral base. Single signal color used SPARINGLY for critical action moments only. Risk colors are editorial-muted, not Bootstrap-saturated.

```
Background        --paper        #0c0d10   paper-noir base (warmer than pure black)
Elevated          --paper-elev   #14161b   raised surface (sidebar, sticky bars)
Card              --paper-card   #1a1d23   primary card surface
Card-warm         --paper-aged   #1e1f24   slightly warmer card for hero / featured
Border            --rule         #2a2e36   hairline rule color
Border-strong     --rule-strong  #383c45   focus / hover
Foreground        --ink          #ebebe6   warm off-white (NOT #ffffff, gives paper feel)
Foreground-dim    --ink-dim      #8e9098   metadata, captions
Foreground-fade   --ink-fade     #5d6068   disabled, hint text

Signal (single)   --citrine      #d6e84b   electric citrine — used ONLY for primary CTA + critical signal
Signal-glow       (rgba)         rgba(214, 232, 75, 0.12)
Gold seal         --gold         #c9a86b   used for compliance certificate, premium / approved states only

Risk: low         --sage         #82b48a
Risk: medium      --amber        #f0b048
Risk: high        --copper       #e07a52
Risk: critical    --oxblood      #c44058
```

**Usage rules:**
- Citrine **= primary CTA + active state ONLY**. Not for chrome, not for decoration. When citrine appears, something is happening or about to happen.
- Gold **= signed/approved/certified ONLY**. Compliance certificate, executed DSAR, endorsement count.
- Risk colors only on severity pills + risk graph nodes. Never on chrome.
- Everything else in monochrome neutrals.

## Spacing

- **Base unit:** 4px.
- **Density:** Comfortable. Macro-spacing (32-64px between sections) is generous. Micro-spacing (8-12px within components) is tight.
- **Scale:** `2xs(2) xs(4) sm(8) md(12) lg(16) xl(24) 2xl(32) 3xl(48) 4xl(64) 5xl(96)`
- **Content frame:** Max width 1440px, padding 32px desktop / 16px mobile.

## Layout

- **Approach:** Grid-disciplined with editorial moments. App pages use strict 12-col grid. Marketing/hero sections allow asymmetry.
- **Border radius:** Sparse, hierarchical.
  - `2px` — inputs, chips
  - `4px` — small pills, kbd
  - `8px` — buttons
  - `10px` — cards (NEVER more)
  - `9999px` — circular only (avatars)
  - **No** bubbly 16-24px radius. Anti-slop.
- **Card style:** Two variants.
  - `card` — 1px hairline border + paper-card bg + 10px radius. Default.
  - `card-flat` — no border, no radius, just background + hairline TOP rule. Editorial section feel.
- **Section labels:** Always small-caps + tracking-widest + ink-dim. `OVERVIEW` not `Overview`.

## Decoration

- **Grain:** Subtle SVG noise overlay on `--paper` base, ~3% opacity. Gives paper feel. Below 1% on cards.
- **Hairlines:** Use `border-bottom: 1px solid var(--rule)` instead of full bordered cards for editorial sections.
- **No gradients** for chrome. The one exception: citrine→gold subtle gradient on hero number / certificate seal.
- **No shadows** by default. One soft shadow on modal/popover only.

## Motion

- **Approach:** Minimal-functional. Motion happens only to aid comprehension.
- **Easing:** `cubic-bezier(0.2, 0.8, 0.2, 1)` (snappy ease-out) for entrances.
- **Duration:** `100ms` micro (hover), `180ms` short (page transitions), `260ms` medium (panel reveal), `400ms` long (live scan ticker).
- **Live data:** SSE ticker rows fade in over 180ms, never animate position.
- **Prefers-reduced-motion:** All animation disabled.

## Components — spec deltas from current code

### Sidebar
- Wordmark: serif **Forgetter** at 22px + meta `BOSCH · GDPR` underneath in small-caps.
- Nav items: ink-dim by default, ink + citrine 2px left border when active. No background fill.
- Footer: "Local-first" badge w/ citrine dot.

### KPI card
- 1px hairline border + slight warmer paper-aged bg.
- Top row: small-caps meta label + icon (icon at right, dim).
- Big number: 48px Geist Mono tabular, ink at full opacity.
- Optional: thin vertical citrine accent on left edge (4px wide) if this KPI is "live action needed."

### Severity pill
- No background fill. Just a 6px colored left bar + risk-color text + small-caps + letter-spaced. Reads like a magazine pull-quote tag.

### Buttons
- Primary: citrine bg + paper text + 8px radius. Used for ONE action per screen max.
- Secondary: paper-card bg + 1px hairline + ink text.
- Ghost: transparent + hover hairline.

### Tables (findings list)
- No vertical lines. Hairline horizontal only.
- Mono for IDs/paths/values. Sans for labels.
- Hover: warmer paper-aged row tint.

### Inputs
- Paper-elev bg + 1px hairline + 2px radius. Focus: 1px citrine border.
- Always paired with a small-caps label above.

### Mosaic graph
- Black-paper bg (`#0a0b0e`).
- Node colors = risk palette only. PERSON = ink, identifiers = sage/amber/copper based on label type.
- Edges = ink-fade @ 30%.
- Selected node = citrine ring.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-31 | Editorial Forensic direction chosen | Generic dark+orange = AI slop. Premium serif + paper feel differentiates and signals seriousness to BCG/VC. |
| 2026-05-31 | Single signal: citrine | Not blue, not purple, not orange (overused). Memorable on stage. |
| 2026-05-31 | Instrument Serif for display | Differentiation from every sans AI dashboard. Says "document, not tool." |
| 2026-05-31 | Risk palette muted (oxblood/copper/amber/sage) | Editorial tone. Bootstrap reds look amateur. |
| 2026-05-31 | No card-shadow, no gradients | Anti-slop. Hairline + paper texture instead. |

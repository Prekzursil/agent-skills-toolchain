---
name: ui-audit
description: Drive a running web or Electron app and emit a deterministic UI/UX + functional audit — accessibility, contrast, spacing, tap targets, dead buttons, visual regression. READ-ONLY (drives and inspects; never edits app source). Emits terminal-state typed findings (SUCCESS:ui-audit-[id] / FAILED:ui-audit-[id] [reason]) + annotated findings JSON for downstream Track-B VLM design critique.
---

# ui-audit Skill

Drives a live web or Electron app and runs five deterministic audit gates. Produces a structured findings JSON that Claude (as orchestrator) then reasons over for design critique (Track-B).

**Skill location:** `~/.claude/skills/ui-audit/`

---

## When to use

- Auditing your own running apps: **Reframe** (Electron+React), **momentstudio** (web), **bilbo-web** (web).
- Spotting WCAG contrast failures, off-scale spacing, dead buttons, and tap-target violations before a PR.
- Establishing a visual baseline and detecting regressions between builds.
- This is the "See" step before Claude provides the "Reason" (Track-B design critique).

---

## Install once

```powershell
cd ~/.claude/skills/ui-audit
npm install
npx playwright install chromium
```

Optional (if pixelmatch/pngjs are missing):
```powershell
npm install pixelmatch pngjs
```

---

## Five gates — what each does

| Script | Gate | Browser? |
|--------|------|----------|
| `capture.mjs` | Evidence bundle: screenshot + computed styles + a11y tree + console/network + pageErrors | Yes |
| `layout_lint.mjs` | Deterministic design heuristics (contrast, spacing, tap targets, type scale) | No — pure JSON |
| `dead_button_crawl.mjs` | Clicks every interactive element (by handle); flags those with zero observable effect | Yes |
| `axe_scan.mjs` | WCAG violations via `@axe-core/playwright` | Yes |
| `visual_diff.mjs` | Baseline screenshot compare via pixelmatch; flags regressions | No — pure PNG |

`run_audit.mjs` is the **orchestrator** on top of the five gates — run it for a one-shot audit (see "Orchestrated run" below).

---

## Invocation per gate

### 1. Capture evidence bundle

**Web app** (one or more routes):
```powershell
node ~/.claude/skills/ui-audit/capture.mjs `
  --url http://localhost:3000 `
  --screens /,/settings,/profile `
  --out ./ui-audit-out
```

**Electron app** (point at the main entry):
```powershell
node ~/.claude/skills/ui-audit/capture.mjs `
  --electron ./apps/reframe/dist/main.js `
  --out ./ui-audit-out
```

Writes `<screen>.bundle.json` + `<screen>.png` into `--out`.

**SPA renderers** (React/Angular/Vue served by Vite, incl. Electron renderers like Reframe): the bundle waits for the app to actually render before snapshotting — `networkidle` + an optional `--wait-selector` and a short `--settle` delay — so you snapshot hydrated content, not an empty shell. Console errors **and uncaught exceptions during load are captured** (`consoleMsgs` + a dedicated `pageErrors[]`), so a renderer crash shows up as a recorded cause instead of an empty bundle. Both `--url` and `--electron` paths are robust out of the box (no patch files).
```powershell
node ~/.claude/skills/ui-audit/capture.mjs `
  --url http://localhost:5173 `
  --wait-selector "#root > *" `   # block until the app mounts
  --settle 500 `                  # extra paint/settle ms (default 300)
  --out ./ui-audit-out
```
Each element also records its `inlineStyle` (raw `style` attr) so layout-lint can tell authored values from computed ones.

### 2. Layout lint (no browser — runs on captured bundles)

```powershell
# Single bundle:
node ~/.claude/skills/ui-audit/layout_lint.mjs `
  --bundle ./ui-audit-out/home.bundle.json `
  --out ./ui-audit-out/lint.json

# All bundles in a directory:
node ~/.claude/skills/ui-audit/layout_lint.mjs `
  --bundle-dir ./ui-audit-out `
  --out ./ui-audit-out/lint.json
```

Checks:
- `off-scale-spacing` — margin/padding/gap not on 4px grid
- `wcag-contrast` — fg/bg contrast < 4.5:1 (WCAG AA)
- `tap-target` — interactive element < 44×44px
- `type-scale-sprawl` — > 6 distinct (fontSize/fontWeight/lineHeight) triples
- `color-inventory-sprawl` — near-duplicate grey palette

**`off-scale-spacing` confidence (noise control).** Headless Chromium renders Tailwind fractional utilities and rem→px conversions as sub-pixel values (`10.5px`, `22.5px`, `13.333px`) that are not authored errors and used to drown the report. Each finding now carries a `confidence`:
- `high` — a clearly off-grid **integer** (e.g. `13px`, `30px`) or a value present in the element's inline `style` (authored). `severity: warning`.
- `low` — a computed **sub-pixel** value. `severity: info`.

Values within 0.5px of a 4px multiple are treated as on-grid (no finding). **Low-confidence findings are suppressed by default**; pass `--include-low-confidence` to surface them too:
```powershell
node ~/.claude/skills/ui-audit/layout_lint.mjs --bundle ./ui-audit-out/home.bundle.json --include-low-confidence
```

### 3. Dead button crawl

```powershell
node ~/.claude/skills/ui-audit/dead_button_crawl.mjs `
  --url http://localhost:3000/settings `
  --screen settings `
  --wait-selector "#root" `   # optional: wait for SPA to render
  --out ./ui-audit-out
```

Writes `settings-dead.json`. Elements with `effect: "none"` are unwired controls.

**Crawls by element handle, not selector.** On Angular/React component trees a regenerated `a:nth-of-type(1)` selector matches the first `<a>` inside *every* container, so Playwright strict-mode rejected the click and the old crawler reported `effect:'none'` for everything. The crawler now clicks the exact `ElementHandle` (re-queried on a fresh isolated page per element) and observes the URL / DOM-mutation / network / console / dialog delta in a tight click window:
- `effect`: `nav` | `dialog` | `dom` | `network` | `console` | `none` | `error`
- A click that can't be performed (hidden/non-actionable) is reported as `error` (with `clickError`), never as a false `none`.
- The reported `selector` is a **stable identifier**, preferring `id` > `[data-testid]` > `[aria-label]` > visible text > `tag.class` (never `:nth-of-type`).

### 4. axe accessibility scan

```powershell
node ~/.claude/skills/ui-audit/axe_scan.mjs `
  --url http://localhost:3000 `
  --out ./ui-audit-out/axe.json
```

Optional tag filter (default = all WCAG rules):
```powershell
--tags wcag2a,wcag2aa
```

### 5. Visual diff (baseline compare)

```powershell
# After capture.mjs has written PNGs:
node ~/.claude/skills/ui-audit/visual_diff.mjs `
  --bundle-dir ./ui-audit-out `
  --baseline ./ui-audit-baselines `
  --out ./ui-audit-diffs
```

First run writes baselines. Subsequent runs emit diff PNGs + `%changed` per screen. Findings with `percentDiff > 5` are flagged as `REGRESSION`.

---

## Orchestrated run (recommended — `run_audit.mjs`)

One command runs every gate, **consumes their findings**, writes a single annotated `audit.json`, and prints the skill's terminal-state marker `SUCCESS:ui-audit-<id>` (or `FAILED:ui-audit-<id> <reason>`). This is the consumer the Track-B critique reads.

```powershell
node ~/.claude/skills/ui-audit/run_audit.mjs `
  --url http://localhost:5173 `      # web app, or an Electron renderer's Vite port (e.g. Reframe)
  --screens /,/settings `
  --wait-selector "#root > *" `      # SPA render gate (optional)
  --baseline ./ui-audit-baselines `  # enables visual-diff (optional)
  --out ./ui-audit-out
# add --include-low-confidence to surface sub-pixel spacing; --tags wcag2a,wcag2aa to scope axe
```

`audit.json` shape:
```jsonc
{
  "id": "ui-audit-<id>",
  "summary": {
    "screens": 2,
    "spacing": { "high": 7, "low": 0, "total": 7 },  // off-scale-spacing rolled up by confidence
    "findingsByRule": { "off-scale-spacing": 7, "wcag-contrast": 3, "tap-target": 1 },
    "deadControls": 2,        // effect:'none' only
    "clickErrors": 1,         // effect:'error' (non-actionable) — NOT counted as dead
    "axeViolations": 4,
    "pageErrors": 1,          // uncaught exceptions captured during load (e.g. a Reframe crash)
    "visualRegressions": 0
  },
  "findings": [ /* merged layout-lint + dead-button, each tagged {gate, screen, confidence?} */ ],
  "axe": [ /* per-screen violations */ ],
  "pageErrors": [ { "screen": "home", "name": "Error", "message": "…" } ],
  "visual": [ /* per-screen percentDiff */ ]
}
```

`--include-low-confidence` is threaded straight into `layout_lint`; `pageErrors` and per-finding `confidence` are surfaced in both the summary and the merged arrays so a downstream critic can filter on them.

## Full run (manual, gate-by-gate)

```powershell
$SKILL = "$HOME/.claude/skills/ui-audit"
$URL   = "http://localhost:3000"
$OUT   = "./ui-audit-out"

# 1. Capture
node $SKILL/capture.mjs --url $URL --screens /,/settings --out $OUT

# 2. Lint captured bundles
node $SKILL/layout_lint.mjs --bundle-dir $OUT --out $OUT/lint.json

# 3. Crawl for dead controls
node $SKILL/dead_button_crawl.mjs --url $URL --screen home --out $OUT

# 4. axe WCAG scan
node $SKILL/axe_scan.mjs --url $URL --out $OUT/axe.json

# 5. Visual diff (baseline on first run)
node $SKILL/visual_diff.mjs --bundle-dir $OUT --baseline ./baselines --out $OUT/diffs
```

---

## Output format

Every gate prints a terminal-state marker on its last line:
- `SUCCESS:capture` / `FAILED:capture <reason>`
- `SUCCESS:layout-lint` / `FAILED:layout-lint <reason>`
- `SUCCESS:dead-button-crawl` / `FAILED:dead-button-crawl <reason>`
- `SUCCESS:axe-scan` / `FAILED:axe-scan <reason>`
- `SUCCESS:visual-diff` / `FAILED:visual-diff <reason>`

JSON finding shape (layout_lint + dead_button_crawl):
```json
{
  "id": "spacing-0",
  "severity": "warning",
  "rule": "off-scale-spacing",
  "selector": "div.header",
  "property": "marginTop",
  "value": "13px",
  "rounded": 13,
  "confidence": "high",
  "screen": "home",
  "message": "div.header marginTop: 13px is not on a 4px grid"
}
```

`dead_button_crawl` findings: `{ id, selector, tagName, text, screen, effect, clickError? }` where `effect ∈ nav|dialog|dom|network|console|none|error`. `capture` bundles additionally carry `pageErrors[]` (uncaught exceptions during load) and per-element `inlineStyle`.

The orchestrator collects all findings JSONs and passes them to Claude for Track-B design critique ("does it look good, feel right, match the design language?").

---

## Graceful degradation

If a dep is absent the gate **skips with a warning** — it does not crash:
- Missing `@axe-core/playwright` → axe gate skipped
- Missing `pixelmatch` / `pngjs` → visual diff gate skipped
- Missing Playwright Chromium → browser gates fail with an install hint

---

## npm dependencies

```powershell
npm install playwright @axe-core/playwright pixelmatch pngjs
npx playwright install chromium
```

---

## Composing with design-extract

The user's `Prekzursil/design-extract` fork is the complementary tool:
- **ui-audit** — drives the *live running app* and emits behavioural + visual findings
- **design-extract** — extracts design tokens, CSS health, and WCAG-remediation suggestions from *source files*

Run both in sequence for a complete "built vs. intended" audit.

---

## TDD

Tests live in `tests/`. Unit tests (no browser):
```powershell
cd ~/.claude/skills/ui-audit
node --test tests/layout_lint.test.mjs tests/visual_diff.test.mjs
```

Integration tests (browser + local server):
```powershell
node --test tests/dead_button_crawl.test.mjs tests/dead_button_component.test.mjs tests/axe_scan.test.mjs tests/capture.test.mjs
```

All tests:
```powershell
npm test
```

Fixtures:
- `fixtures/fixture.html` — flat page with deliberate defects (off-scale margin, low-contrast text, dead button, 30×30 tap target).
- `fixtures/component_fixture.html` — Angular/React-style component tree where sibling cards make `nth-of-type` selectors globally ambiguous; mixes wired + genuinely dead controls. Guards the BUG-1 handle-based crawl.
- `fixtures/spa_fixture.html` — empty shell that hydrates asynchronously, logs a console error during load, and throws an uncaught "render crash". Guards the BUG-3 capture render-wait + crash capture.

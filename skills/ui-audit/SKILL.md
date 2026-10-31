---
name: ui-audit
description: Drive a running web or Electron app and emit a deterministic UI/UX +
  functional audit - a11y, contrast, spacing, tap targets, dead buttons, motion, visual
  regression (Track-A) - then a design-quality VERDICT (Track-B) where Claude reasons
  over the numbers + screenshot on the DESIGN-EVAL v1 rubric (0-4, critical-error
  override, weighted composite) against Refactoring-UI/HIG/Nielsen/WCAG. READ-ONLY.
metadata:
  origin: user
permalink: dqverify-repo-20261013/skills/ui-audit/skill
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
- `off-scale-spacing` — margin/padding/gap not on 4px grid → **spacing-rhythm**
- `wcag-contrast` — fg/bg contrast < 4.5:1 (WCAG AA) → **color-contrast**
- `tap-target` — interactive element < 44×44px → **affordance**
- `type-scale-sprawl` — > 6 distinct (fontSize/fontWeight/lineHeight) triples → **type-scale**
- `color-inventory-sprawl` — near-duplicate grey palette → **color-contrast**
- `motion-duration` *(new — motion collector)* — a transition/animation outside the 200–500ms band → **motion**
- `reduced-motion` *(new — motion collector)* — the page animates but ships no `prefers-reduced-motion` rule (no reduced-motion escape) → **motion**
- `missing-focus-visible` *(new — affordance collector)* — interactive controls suppress the focus outline and the page has no `:focus-visible` rule → **affordance**

The two new collectors read per-element motion/affordance computed styles
(`transitionDuration`/`animationDuration`/`outlineStyle`/`cursor`) plus the page-level
`pageSignals` (`hasReducedMotionRule` / `hasFocusVisibleRule`) that `capture.mjs` now
records. Dead-button findings (`effect:none`) also feed **affordance** (a primary action
with no feedback). These implement DESIGN-EVAL v1 dimensions #8 (affordance) and #9
(motion); see `DESIGN-SKILLS-AND-EVAL.md` §1.1 / §2.2.

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
    "visualRegressions": 0,
    "affordance": { "tapTarget": 1, "missingFocusVisible": 1, "deadControls": 2, "total": 4 },  // DESIGN-EVAL v1 #8
    "motion": { "durationOutOfBand": 2, "noReducedMotion": 1, "total": 3 }                       // DESIGN-EVAL v1 #9
  },
  "findings": [ /* merged layout-lint + dead-button, each tagged {gate, screen, confidence?} */ ],
  "axe": [ /* per-screen violations */ ],
  "pageErrors": [ { "screen": "home", "name": "Error", "message": "…" } ],
  "visual": [ /* per-screen percentDiff */ ]
}
```

`--include-low-confidence` is threaded straight into `layout_lint`; `pageErrors` and per-finding `confidence` are surfaced in both the summary and the merged arrays so a downstream critic can filter on them.

---

## Track-B — design critique ("does it look good?")

Track-A **SEES** (deterministic numbers + a screenshot). Track-B **REASONS**: Claude
(the orchestrator) views the screenshot and scores design quality against a rubric,
producing a structured verdict. The two-track split is the hard architecture rule:

> **Claude is the critic — it reasons over the PRE-COMPUTED numbers + the screenshot.
> It NEVER pixel-measures or guesses coordinates (that is Track-A's job).**

The harness (`critique.mjs`) is pure plumbing — it never calls a model and never measures.

### Flow

```
run_audit.mjs ──▶ audit.json + <screen>.png        (Track-A: SEE)
        │
        ▼
critique.mjs assemble ──▶ critique-input.json + critique-input.md
        │   (projects the numbers onto the 9 scoring dimensions + embeds the rubric,
        │    the per-dimension weights, the 0-4 scale, the screenshot path(s), schema)
        ▼
Claude views the screenshot & scores each dimension 0-4 per outputSchema   (Track-B: REASON)
        │   (one dimension per pass; critical condition ⇒ score 0)
        ▼
critique.mjs compute  ──▶ fills verdict.score from the §2.4 weighted composite + §2.3 cap
        │
        ▼
critique.mjs validate ──▶ SUCCESS:ui-critique-... / FAILED:ui-critique-... reason
```

> **DESIGN-EVAL v1 (the rubric upgrade).** Each of the nine scoring dimensions gets an
> ordinal `score` 0-4 (0=critical/fail … 4=excellent). A **critical-error override**
> (`DESIGN-SKILLS-AND-EVAL.md` §2.3) forces a tripped dimension to 0 and caps the verdict
> (1 critical → needs-work ≤60; ≥2 → poor ≤39). `verdict.score` is the **weighted
> composite** (§2.4, `color-contrast` weight 2.0 highest) — `critique.mjs compute` fills
> it; the validator rejects a free-handed score that defies the composite. Run one
> dimension per pass for reliability (`--dimension <name>`, §2.5).

### Commands

```powershell
# 1. assemble the critique INPUT from Track-A artefacts (auto-discovers <out>/*.png)
node ~/.claude/skills/ui-audit/critique.mjs assemble `
  --audit ./ui-audit-out/audit.json `
  --screenshot ./ui-audit-out/home.png `   # optional; omitted → auto-discovered
  --rubric ~/.claude/skills/ui-audit/critique_rubric.md `   # optional; defaults to this file
  --out ./ui-audit-out
#   → writes critique-input.json (machine) + critique-input.md (the brief Claude reads)

# 2. Claude (orchestrator) VIEWS the screenshot(s) and writes critique-output.json,
#    SCORING each dimension 0-4 per outputSchema (see below). No model call in the harness.
#    For the §2.5 reliability protocol, assemble ONE dimension per pass:
node ~/.claude/skills/ui-audit/critique.mjs assemble --audit ./ui-audit-out/audit.json --dimension affordance --out ./ui-audit-out

# 3. fill the headline deterministically (the §2.4 weighted composite + §2.3 cap)
node ~/.claude/skills/ui-audit/critique.mjs compute --input ./ui-audit-out/critique-output.json
#   → writes verdict.score + verdict.looksGood + verdict.eval (composite/mean/criticalCount/shipGate)
#   → add --dry-run to preview without writing

# 4. gate the verdict
node ~/.claude/skills/ui-audit/critique.mjs validate --input ./ui-audit-out/critique-output.json

# (regenerate the committed JSON Schema after a schema change)
node ~/.claude/skills/ui-audit/critique.mjs schema --out ~/.claude/skills/ui-audit/critique.schema.json
```

### The nine scoring dimensions (DESIGN-EVAL v1)

`visual-hierarchy` (w1.5) · `spacing-rhythm` (w1.0) · `alignment` (w0.75) · `type-scale`
(w1.0) · `color-contrast` (**w2.0**) · `consistency` (w1.0) · `empty-error-states` (w1.5)
· `affordance` (w1.5, new) · `motion` (w0.75, new) — plus the unweighted holistic
`overall` line. Each scoring dimension carries a numeric `score` 0-4. The rubric for each
(anchors at 0/2/4, the critical-error trigger, which Track-A signals feed it, weight)
lives in **`critique_rubric.md`** — grounded in Refactoring UI, Material 3, Apple HIG,
Nielsen's heuristics, and WCAG. `critique.mjs assemble` deterministically routes each
Track-A finding to its dimension (`off-scale-spacing`→spacing-rhythm;
`wcag-contrast`/`color-inventory-sprawl`/axe-contrast→color-contrast;
`type-scale-sprawl`→type-scale; landmark-axe→visual-hierarchy;
`tap-target`/`dead-control`/`click-error`/`missing-focus-visible`→**affordance**;
`motion-duration`/`reduced-motion`→**motion**; `pageError`→empty-error-states;
visual-regression→consistency) so every quantitative claim Claude makes is pre-grounded
and traceable by `ref`. (Spec: `DESIGN-SKILLS-AND-EVAL.md` §2.2.)

### OUTPUT schema (typed verdict)

Authoritative validator = `validateCritique()` in `critique_schema.mjs`; mirrored as a
draft-07 JSON Schema in **`critique.schema.json`**. Shape:

```jsonc
{
  "id": "ui-critique-…",
  "audit_id": "ui-audit-…",
  "verdict": { "looksGood": "good|needs-work|poor", "score": "0-100 (computed composite)", "headline": "…", "summary": "…",
               "eval": { "composite": 46.88, "capped": 46.88, "mean": 2.4, "minScore": 0, "criticalCount": 1, "shipGate": false, "referenceGate": false } },
  "dimensions": [
    { "dimension": "one of the 9 scoring dims", "score": "0-4 (0 if a critical condition tripped)",
      "rating": "pass|warn|fail", "confidence": "high|medium|low",
      "findings": [ { "severity": "critical|high|medium|low|info",
                      "evidence": "grounded in a number-by-ref OR an explicit visual observation",
                      "evidenceRefs": ["spacing-0", "…"], "recommendation": "actionable fix" } ] }
  ],
  "prioritizedFindings": [ { "rank": 1, "dimension": "…", "severity": "…", "evidence": "…", "recommendation": "…" } ],
  "uiclip": { "score": 0.0-1.0, "status": "ok" } | null
}
```

The validator enforces DESIGN-EVAL v1: every scoring dimension needs a `score` in [0,4];
a **critical** finding forces that dimension's score to **0** (critical-error override,
§2.3); and `verdict.score` must equal the harness-computed weighted composite within ±2
(§2.4) — so the headline can't be free-handed. One critical caps `looksGood` at
`needs-work`; two or more → `poor`. `validate` collects *every* violation at once.

### Optional: UIClip numeric prior (`uiclip_score.py`)

A weak design-quality number (0-1) from the local **UIClip** model
(`biglab/uiclip-*`, CLIP-based, MIT, CPU-capable, ~600MB) — useful for regression-gating
and best-of-N. **Opt-in and RAM-guarded** (the skill works fully rubric-only without it):

```powershell
python ~/.claude/skills/ui-audit/uiclip_score.py --check            # readiness only: deps + free RAM + cache. No load, no download.
python ~/.claude/skills/ui-audit/uiclip_score.py --screenshot home.png               # → status:"skipped" (scoring is opt-in)
python ~/.claude/skills/ui-audit/uiclip_score.py --screenshot home.png --use-cache   # score ONLY if already cached (never downloads)
python ~/.claude/skills/ui-audit/uiclip_score.py --screenshot home.png --allow-download --out uiclip.json   # fetch (~600MB) + score
```

Then pass `--uiclip ./ui-audit-out/uiclip.json` to `critique.mjs assemble`.

Safety contract (the user just hit an OOM — these are enforced in code):
- **No auto-download:** weights are fetched ONLY with `--allow-download`.
- **Opt-in:** scoring never runs without `--allow-download` or `--use-cache`.
- **RAM guard:** refuses to load when free RAM < `--min-free-gb` (default 2.0), or when
  free RAM can't be measured, unless `--force`.
- **Graceful:** missing deps / no cache / low RAM / any error → a clean JSON object with
  `status != "ok"`, `score: null`, and **exit 0**, so the chain degrades to rubric-only.
- stdout is always a single JSON object (markers/logs go to stderr).

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

`dead_button_crawl` findings: `{ id, selector, tagName, text, screen, effect, clickError? }` where `effect ∈ nav|dialog|dom|network|console|none|error`. `capture` bundles additionally carry `pageErrors[]` (uncaught exceptions during load), per-element `inlineStyle`, the per-element motion/affordance computed styles (`transitionDuration`/`animationDuration`/`outlineStyle`/`cursor`), and a page-level `pageSignals` object (`hasReducedMotionRule` / `hasFocusVisibleRule`) consumed by the DESIGN-EVAL v1 motion + affordance lint rules.

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
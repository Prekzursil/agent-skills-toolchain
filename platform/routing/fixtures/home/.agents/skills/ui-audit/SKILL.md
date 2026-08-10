---
name: ui-audit
description: Drive a running web or Electron app and emit a deterministic UI/UX + functional audit — accessibility, contrast, spacing, tap targets, dead buttons, affordance/focus-visible, motion duration, visual regression (Track-A) — then a structured design-quality VERDICT (Track-B) where Claude reasons over the pre-computed numbers + the screenshot on the DESIGN-EVAL v1 rubric — nine dimensions each scored 0-4, a critical-error override that forces a zero and caps the verdict, a weighted composite (color-contrast highest), and a one-dimension-per-call reliability protocol — against Refactoring-UI/Material/HIG/Nielsen/WCAG. READ-ONLY (drives and inspects; never edits app source). Emits terminal-state typed findings plus a typed critique schema with a computed weighted composite. Optional UIClip numeric prior (opt-in, RAM-guarded).
metadata:
  origin: user
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

### Invocation per gate
### 1. Capture evidence bundle
### 2. Layout lint (no browser — runs on captured bundles)
### Single bundle:
### All bundles in a directory:
### 3. Dead button crawl
### 4. axe accessibility scan
### 5. Visual diff (baseline compare)
### After capture.mjs has written PNGs:
### Orchestrated run (recommended — `run_audit.mjs`)

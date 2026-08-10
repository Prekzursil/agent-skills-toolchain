---
name: ui-drive
description: Thin rail-router driver for a LIVE running web or Electron app — attach to it, resolve any target through three fallback rails (a11y-ref then CDP css then vision xy), point at an element with a screenshot-visible highlight, discuss it with full context, and actuate it (click/fill/hover/press/select). Also drives the ephemeral restyle loop — preview a CSS candidate as an injected style overlay, apply/accept/revert it, and harvest the accepted deltas as a PROPOSED patch — WITHOUT ever editing application source. Rides the vendored playwright at exactly 1.61.1 from the sibling ui-audit skill, so no new browser dependency. Every mutating verb logs to a bounded shadow sink (observe-only, never blocks). Use as the low-level app-driving and pointing channel under design-studio-session and design-review-loop. NOT for the design-quality verdict (use ui-audit) and NOT for element-to-source mapping or micro-commits (use design-studio-session).
metadata:
  origin: user
---

# ui-drive Skill

A **thin rail-router driver** for a live app. Where `ui-audit` *looks* and *scores*, `ui-drive`
*points*, *drives*, and *previews* — the actuation channel an agent uses to touch a running UI.

**Skill location:** `~/.claude/skills/ui-drive/` (files: `SKILL.md`, `drive.mjs`).

---

## When to use

- Point Claude (or the owner) at a specific live element and screenshot it with a highlight box.
- Actuate a running app deterministically: click, fill, hover, press, check, select, scroll, focus.
- Drive the **ephemeral restyle loop** — preview a CSS candidate as an injected overlay, apply /
  accept / revert it, then **harvest** the accepted deltas as a proposed patch — with **zero**
  source edits.
- As the low-level driver invoked by **`design-studio session`** (interactive-modify, N.2) and the
  **`design-review-loop`** gates.

**Not for:** the design-quality VERDICT (use `ui-audit`), nor element→source resolution and
micro-commits (use `design-studio-session`).

---

## Zero new dependency (Correction 3: near-zero-build)

`ui-drive` imports the browser stack that the sibling `ui-audit` skill already vendors at exactly
`playwright@1.61.1`, resolved by absolute file URL from
`../ui-audit/node_modules/playwright/index.mjs` (override with `UI_DRIVE_PLAYWRIGHT`). No `npm
install` in this skill. If `ui-audit` has not had `npm install && npx playwright install chromium`
run once, do that in `ui-audit` first — its browser binaries are shared here.

---

## The three rails

### The pinned highlight (why `point` works)
### Verbs
### Safety / shadow mode (COUNCIL C5)
### Usage — programmatic (primary: one process holds the whole session)
### Usage — CLI
### Cross-process against a running app (Chrome started with --remote-debugging-port=9222,
### or an Electron app exposing a CDP endpoint):
### Relationship to the design suite

---
name: ui-drive
description: Thin rail-router driver for a LIVE running web or Electron app — attach to it, resolve any target through three fallback rails (a11y-ref then CDP css then vision xy), point at an element with a screenshot-visible highlight, discuss it with full context, and actuate it (click/fill/hover/press/select). Also drives the ephemeral restyle loop — preview a CSS candidate as an injected style overlay, apply/accept/revert it, and harvest the accepted deltas as a PROPOSED patch — WITHOUT ever editing application source. Rides the vendored playwright at exactly 1.61.1 from the sibling ui-audit skill, so no new browser dependency. Every mutating verb logs to a bounded shadow sink (observe-only, never blocks). Use as the low-level app-driving and pointing channel under design-studio-session and design-review-loop. NOT for the design-quality verdict (use ui-audit) and NOT for element-to-source mapping or micro-commits (use design-studio-session).
metadata:
  origin: user
---

# ui-drive Skill

A **thin rail-router driver** for a live app. Where `ui-audit` *looks* and *scores*, `ui-drive`
*points*, *drives*, and *previews* — the actuation channel an agent uses to touch a running UI.

**Skill location:** `~/.Codex/skills/ui-drive/` (files: `SKILL.md`, `drive.mjs`).

---

## When to use

- Point Codex (or the owner) at a specific live element and screenshot it with a highlight box.
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

A `--target` string is resolved through fallback rails; the resolver reports which rail hit.

| Rail | Target syntax | Backing Playwright API |
|------|---------------|------------------------|
| **a11y-ref** (preferred) | `ref:N` · `role:button\|Save` · `text:Export` · `label:...` · `placeholder:...` · `alt:...` · `title:...` | ref map + `getByRole` / `getByText` / `getByLabel` / ... |
| **CDP** (css/DOM) | `css:.btn` · `testid:submit` | `page.locator(css)` / `getByTestId` |
| **vision** (coordinate, last resort) | `xy:120,340` | `page.mouse` / drawn box overlay |

- `ref:N` comes from the **ref map** printed by `attach` — a deterministic enumeration of every
  visible interactive element with its role, accessible name, tag, selector and rect. (Playwright
  1.61.1's `ariaSnapshot({ref:true})` does **not** emit `[ref=]` markers, so ui-drive builds and
  owns its own stable ref map.)
- A **bare** target (no prefix) cascades automatically: a11y text → css → vision-fail (which tells
  you to supply an `xy:`).

---

## The pinned highlight (why `point` works)

`point` draws a highlight and screenshots it. The exact call was **pinned empirically against the
vendored 1.61.1 at build time**:

- **Real path:** `await locator.highlight()` injects an `<x-pw-glass>` overlay that **is captured by
  `page.screenshot()`** (verified: the highlighted PNG differs from the plain PNG). `await
  page.hideHighlight()` clears it afterward so later captures/actions are pristine.
- **The `show --annotate/--highlight` CLI subcommand does NOT exist** and is not used — that path was
  the unconfirmed caveat in Correction 3; it is now closed.
- For a **vision** (`xy:`) target there is no locator, so `point` draws its own `#__ui_drive_box`
  overlay at the coordinate instead.

---

## Verbs

| Verb | Effect | Mutates? |
|------|--------|----------|
| `attach` | Connect to a running app (`--cdp`) or launch one (`--url` / `--electron`); build + print the ref map. | live nav only |
| `point` | Resolve a target, highlight it (pinned), screenshot; report rail, count, bbox, accessible name. | read-only |
| `discuss` | `point` + element context: `ariaSnapshot`, key computed styles, nearby text. | read-only |
| `drive` | Actuate the live app: `click`/`dblclick`/`hover`/`fill`/`type`/`press`/`check`/`uncheck`/`select`/`scroll`/`focus`. | **live app** |
| `preview` | Inject an **ephemeral** `<style>` candidate; screenshot before/after. | overlay only |
| `apply` | Promote the preview to a persistent (session) overlay; re-injected after navigation. | overlay only |
| `accept` | Mark the most-recent applied overlay as accepted (what `harvest` exports). | state only |
| `revert` | Remove an overlay (`--scope preview\|applied\|accepted\|all`), restoring visuals. | overlay only |
| `harvest` | Emit accepted overlays as a **proposed** CSS patch (`.css` + `.json`). | **writes no source** |

`drive` is the one verb that changes the running application — that is what a driver does. It never
edits source files. `preview/apply/accept` only inject removable `<style>` tags; `harvest` only
proposes deltas for a human/agent to translate to the real stylesheet (that translation is
`design-studio-session`'s job).

---

## Safety / shadow mode (COUNCIL C5)

- ui-drive **never edits application source** — the strongest gate is structural.
- Every mutating verb (`drive`, `preview`, `apply`, `accept`, `revert`, `harvest`) appends a JSONL
  line to a **bounded, rotating shadow sink** (`UI_DRIVE_SHADOW_LOG`, default under the OS temp dir).
  It is **observe-only**: it never blocks, never nags, and any sink failure is swallowed.

---

## Usage — programmatic (primary: one process holds the whole session)

```js
import { Driver } from './drive.mjs';

const d = await Driver.attach({ url: 'http://localhost:5173' });   // or { cdp }, { electron }
console.log(d.snapshot());                          // { refs: [{ ref, role, name, tag, rect }], ... }

await d.point('role:button|Save', { outDir: './out' });   // highlight + screenshot
const info = await d.discuss('ref:3');                    // styles + ariaSnapshot + nearby text
await d.drive('fill', 'label:Email', 'a@b.com');
await d.drive('click', 'text:Save');

await d.preview('.primary{background:#0a7;border-radius:10px}');   // ephemeral overlay
await d.apply(); await d.accept();
const patch = await d.harvest({ outDir: './out' });       // proposed CSS deltas — NOT written to source
await d.revert({ scope: 'all' });
await d.close();
```

The importable surface: `Driver` (with static `attach` and instance verbs `snapshot`, `resolve`,
`point`, `discuss`, `drive`, `preview`, `apply`, `accept`, `revert`, `harvest`, `refresh`, `close`),
plus helpers `resolvePlaywright`, `parseTarget`, `shadowLog`, `shadowLogPath`.

---

## Usage — CLI

`--cdp <endpoint>` attaches to an **already-running** app (cross-process; verbs reconnect and
overlay state persists via a session file). `--url` / `--electron` run the verb **oneshot** in a
single process.

```powershell
# Cross-process against a running app (Chrome started with --remote-debugging-port=9222,
# or an Electron app exposing a CDP endpoint):
node drive.mjs attach  --cdp http://localhost:9222
node drive.mjs point   --cdp http://localhost:9222 --target ref:5 --out ./out
node drive.mjs discuss --cdp http://localhost:9222 --target "role:button|Export"
node drive.mjs drive   --cdp http://localhost:9222 --action click --target "text:Export"
node drive.mjs preview --cdp http://localhost:9222 --css ".btn{background:#0a7}"
node drive.mjs apply   --cdp http://localhost:9222
node drive.mjs accept  --cdp http://localhost:9222
node drive.mjs harvest --cdp http://localhost:9222 --out ./out
node drive.mjs revert  --cdp http://localhost:9222 --scope all

# Oneshot launch (single process; multi-verb sessions want --cdp or the programmatic Driver):
node drive.mjs point   --url http://localhost:5173 --target "role:button|Save" --out ./out
node drive.mjs attach  --electron ./path/to/main.js
```

Flags: `--url` `--electron` `--cdp` `--target` `--action` `--value` `--css` `--scope` `--out`
`--session` `--headed` `--wait-selector` `--settle` `--include-applied`. Every run ends with a
terminal-state marker `SUCCESS:ui-drive:<verb>` or `FAILED:ui-drive:<verb> <reason>`.

**Cross-process caveat (honest):** `--url`/`--electron` launched browsers die when the node process
exits, and `launchServer + connect` does not preserve pages across a client disconnect — so
multi-verb cross-process sequences are supported **only** in `--cdp` mode (attach to an app that owns
its own lifetime) or in one programmatic `Driver` process. This is by design, not a gap.

---

## Relationship to the design suite

`ui-drive` is the actuation layer beneath the UI/UX consolidation:

- **`ui-audit`** — sees and scores (READ-ONLY verdict). ui-drive drives and previews.
- **`design-studio-session`** (N.2) — orchestrates ui-drive's preview→apply→accept→revert→harvest
  loop, adds element→source mapping and scoped micro-commits, and re-audits via `ui-audit`.
- **`design-review-loop`** — the batch G0–G7 state machine that can call ui-drive to point at and
  drive individual screens.

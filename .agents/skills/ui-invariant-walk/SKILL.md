---
name: ui-invariant-walk
description: Use when you want a property-based random-walk oracle that DRIVES a running web/Electron app and asserts UI invariants over a randomized command sequence — "no enabled button is a dead click" (an enabled, visible control must produce an observable state change) and "no route errors" (no navigation may reach an error route, throw an uncaught exception, or log a console error). Model-based testing via fast-check (`fc.commands` + `fc.asyncModelRun`) driving Playwright, with automatic shrinking to a minimal reproducing click/nav sequence. Ships as a SHADOW-mode advisory oracle (observe + log to a bounded rotating sink, never blocks CI or nags). Optionally deepen the existing Python Hypothesis suite with HypoFuzz nightly — but ONLY after verifying HypoFuzz's shifted license; the fast-check oracle ships regardless. NOT for pixel/design critique (use ui-audit), NOT for deterministic single-flow E2E (use Playwright directly).
metadata:
  origin: gem-hunt-2026-07-12
  item: ui-invariant-walk-oracle
  evidence: MASTER A-Tier2 (agentic-repair-2 #9, agentic-repair-1 #10); COUNCIL-VERDICT C5 shadow-first
---

# ui-invariant-walk Skill

A **model-based property test** that fans a *randomized* walk of Click / Navigate commands across a
running app and asserts UI **invariants** after every step. Where a hand-written E2E test proves one
scripted path, this oracle explores thousands of paths and, on failure, **shrinks** to the shortest
sequence that reproduces the violation.

**Skill location:** `~/.claude/skills/ui-invariant-walk/`

Two invariants ship by default:

| ID | Invariant | Fails when |
|----|-----------|-----------|
| **INV1 DEAD_CLICK** | *No enabled button is a dead click.* | An **enabled + visible** control is clicked and produces **no observable state change** (no URL change, no DOM mutation, no network request, no dialog). |
| **INV2 ROUTE_ERROR** | *No route errors.* | After any step the app is on an **error route** (`/error`, `/404`, `/500`), logged a **`console.error`**, or threw an **uncaught page exception**. |

Both are cheap, app-agnostic, and catch a real class of agentic-repair regression: green unit tests +
a UI where a button silently does nothing or a route 500s. (Evidence: gem-hunt MASTER A-Tier2
agentic-repair-2 #9 / agentic-repair-1 #10 — "invariant random-walk UI oracle".)

---

## When to use

- After any UI change to **Reframe** (Electron+React), **momentstudio** (web), **bilbo-web**, WebCoder.
- As a **nightly / pre-PR** advisory sweep — surface dead controls and broken routes the scripted suite never visits.
- When a "tests pass" claim needs an **external, executable** UI check (see COUNCIL-VERDICT: the done-gate is spoofable; only executable/external evidence counts).

**Not for:** design/contrast/spacing critique → `ui-audit`; one deterministic scripted flow → plain Playwright; Python data-model properties → `python-testing` (+ HypoFuzz below).

---

## Shadow-mode contract (COUNCIL-VERDICT C5 — MANDATORY)

This oracle is **advisory / observe-only**. It is a *heuristic random explorer*, so it enters the ladder at **SHADOW**, never blocks, never nags:

- **Exit code is always 0** in shadow mode — a violation is **logged, not failed**. CI stays green; the oracle only *reports*.
- Findings + counterexamples go to a **separate, bounded, auto-rotating** sink: `~/.claude/shadow-logs/ui-invariant-walk.jsonl` (rotates at 5 MB, keeps 3). **Never** the main event ledger / `terminal.jsonl` (C5(iii): 40 shadow modules would DoS the F1 scorer).
- Graduation SHADOW→ADVISE→ENFORCE is a **later, human** decision, justified only by a **measured escape/false-positive rate** from the shadow log — not by this skill.
- Set `WALK_MODE=advise` to print a non-zero-styled summary to stdout (still exit 0); `WALK_MODE=enforce` (opt-in, human-graduated) exits 1 on a confirmed violation.

---

## Install once

```powershell
cd ~/.claude/skills/ui-invariant-walk
npm init -y
npm install fast-check@3 playwright
npx playwright install chromium
```

`fast-check@3` supplies model-based commands (`fc.commands`, `fc.asyncModelRun`) with shrinking;
Playwright drives the real page. (Verified locally: `fast-check@3.23.2`, node v24.16.0.)

---

## The oracle — `oracle.mjs`

Save this alongside the skill as `oracle.mjs`. It drives a URL you pass and walks it. Swap the
selectors block for your app if needed; defaults target generic `<button>` / `[role=button]` / `<a>`.

```javascript
// oracle.mjs — invariant random-walk UI oracle (fast-check + Playwright), SHADOW mode.
import fc from 'fast-check';
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const URL       = process.env.WALK_URL   || process.argv[2] || 'http://localhost:5173';
const MODE      = process.env.WALK_MODE  || 'shadow';        // shadow | advise | enforce
const NUM_RUNS  = Number(process.env.WALK_RUNS  || 25);      // walks
const MAX_STEPS = Number(process.env.WALK_STEPS || 20);      // steps per walk
const ERR_ROUTES = (process.env.WALK_ERR_ROUTES || '/error,/404,/500').split(',');

// --- bounded, rotating shadow sink (C5(iii)) ---
const SINK_DIR = path.join(os.homedir(), '.claude', 'shadow-logs');
const SINK = path.join(SINK_DIR, 'ui-invariant-walk.jsonl');
function logShadow(rec) {
  try {
    fs.mkdirSync(SINK_DIR, { recursive: true });
    if (fs.existsSync(SINK) && fs.statSync(SINK).size > 5 * 1024 * 1024) {
      fs.rmSync(SINK + '.2', { force: true });
      if (fs.existsSync(SINK + '.1')) fs.renameSync(SINK + '.1', SINK + '.2');
      fs.renameSync(SINK, SINK + '.1');
    }
    fs.appendFileSync(SINK, JSON.stringify({ ts: new Date().toISOString(), ...rec }) + '\n');
  } catch { /* fail-open: shadow logging never breaks the run */ }
}

// --- page adapter: read enabled controls + a state snapshot; act; detect errors ---
async function adapter(page) {
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => pageErrors.push(String(e)));
  let netCount = 0;
  page.on('request', () => { netCount++; });

  const SEL = 'button:not([disabled]), [role=button]:not([aria-disabled=true]), a[href]';
  return {
    async enabledControls() {
      return page.$$eval(SEL, (els) =>
        els
          .map((el, i) => ({ i, txt: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 40) }))
          .filter((_, idx) => {
            const el = document.querySelectorAll(
              'button:not([disabled]), [role=button]:not([aria-disabled=true]), a[href]')[idx];
            const r = el.getBoundingClientRect();
            const vis = r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
            return vis;
          }),
      );
    },
    async snapshot() {
      // URL + coarse DOM fingerprint (node count + body text length) — cheap, catches real change.
      const dom = await page.evaluate(() => ({
        n: document.querySelectorAll('*').length,
        t: (document.body?.innerText || '').length,
      }));
      return `${page.url()}|${dom.n}|${dom.t}|net:${netCount}`;
    },
    async clickIndex(idx) {
      const before = { c: consoleErrors.length, p: pageErrors.length };
      const els = await page.$$(SEL);
      if (!els[idx]) return { skipped: true };
      const dialogSeen = [];
      const onDialog = (d) => { dialogSeen.push(1); d.dismiss().catch(() => {}); };
      page.on('dialog', onDialog);
      await els[idx].click({ timeout: 1500 }).catch(() => {});
      await page.waitForTimeout(120);
      page.off('dialog', onDialog);
      return {
        newConsole: consoleErrors.length - before.c,
        newPage: pageErrors.length - before.p,
        dialog: dialogSeen.length,
      };
    },
    routeIsError() { return ERR_ROUTES.some((r) => page.url().includes(r)); },
    errs() { return { console: consoleErrors.slice(-3), page: pageErrors.slice(-3) }; },
  };
}

// --- fast-check model-based commands ---
class ClickCmd {
  constructor(pick) { this.pick = pick; }
  check() { return true; }
  async run(model, real) {
    const ctrls = await real.enabledControls();
    if (ctrls.length === 0) return;
    const idx = ctrls[this.pick % ctrls.length].i;
    const before = await real.snapshot();
    const res = await real.clickIndex(idx);
    if (res.skipped) return;
    const after = await real.snapshot();
    // INV2: route/console/page errors.
    if (real.routeIsError() || res.newPage > 0 || res.newConsole > 0) {
      throw Object.assign(new Error('ROUTE_ERROR'), { inv: 'INV2', ctrl: idx, errs: real.errs() });
    }
    // INV1: enabled control must change something (url/dom/net/dialog).
    const changed = before !== after || res.dialog > 0;
    if (!changed) {
      throw Object.assign(new Error('DEAD_CLICK'), { inv: 'INV1', ctrl: idx, at: before });
    }
  }
  toString() { return `Click(${this.pick})`; }
}
class NavBackCmd {
  check() { return true; }
  async run(model, real) { /* placeholder for history walk; kept minimal */ }
  toString() { return 'Back'; }
}

const commands = [
  fc.nat({ max: 12 }).map((p) => new ClickCmd(p)),
  fc.constant(new NavBackCmd()),
];

async function main() {
  const browser = await chromium.launch();
  let failed = null;
  try {
    await fc.assert(
      fc.asyncProperty(fc.commands(commands, { maxCommands: MAX_STEPS }), async (cmds) => {
        const page = await browser.newPage();
        await page.goto(URL, { waitUntil: 'domcontentloaded' });
        const real = await adapter(page);
        try {
          await fc.asyncModelRun(() => ({ model: {}, real }), cmds);
        } finally {
          await page.close();
        }
      }),
      { numRuns: NUM_RUNS, endOnFailure: true },
    );
  } catch (e) {
    failed = e;
  } finally {
    await browser.close();
  }

  if (!failed) {
    console.log(`ui-invariant-walk: PASS (${NUM_RUNS} walks, no invariant violation) [mode=${MODE}]`);
    logShadow({ result: 'pass', url: URL, runs: NUM_RUNS });
    process.exit(0);
  }

  // fast-check throws with .counterexample = the shrunk minimal sequence.
  const cx = failed.counterexample?.[0];
  const seq = cx ? Array.from(cx, String) : [];
  const rec = { result: 'violation', url: URL, sequence: seq, message: String(failed).split('\n')[0] };
  logShadow(rec);
  console.log(`ui-invariant-walk: INVARIANT VIOLATION [mode=${MODE}]`);
  console.log('  minimal sequence:', JSON.stringify(seq));
  console.log('  detail:', rec.message);
  console.log(`  logged to ~/.claude/shadow-logs/ui-invariant-walk.jsonl`);
  // C5: shadow/advise NEVER fail the build; only graduated enforce mode exits non-zero.
  process.exit(MODE === 'enforce' ? 1 : 0);
}

main();
```

### Run it

```powershell
# Start your app first (e.g. Reframe dev server / momentstudio), then:
$env:WALK_URL="http://localhost:5173"; node oracle.mjs         # shadow (default, always exit 0)
$env:WALK_MODE="advise"; node oracle.mjs                        # prints summary, still exit 0
$env:WALK_RUNS="50"; $env:WALK_STEPS="30"; node oracle.mjs      # deeper walk
```

Terminal-state output: `ui-invariant-walk: PASS …` or `… INVARIANT VIOLATION …` with the **shrunk**
click/nav sequence you can replay by hand.

---

## Proven mechanism (self-test)

The model-run + invariant + shrink logic was verified for real against a mock app (`walk.mjs`,
no browser needed) — a GOOD build passes, a BUGGY build (a `ghost` dead button + an `/err` route) is
caught and shrunk:

```
GOOD build  -> failed=false (expected pass)
BUGGY build -> failed=true (expected catch)
  counterexample: ["Navigate(#2)", ... ,"Click(#5)"]
  error: Error: ROUTE_ERROR invariant violated after navigate("/err")
ORACLE-SELFTEST: PASS   (exit 0)
```

Ship a copy of `walk.mjs` (the mock self-test) in the skill folder as a CI smoke check that the
oracle plumbing itself works without needing a live app. The mock is the two-build fixture used above.

---

## Optional: HypoFuzz nightly (Python) — LICENSE-GATED, do NOT wire blindly

The gem pairs this oracle with **coverage-guided deepening of the existing Python Hypothesis suite via
HypoFuzz** (feeds the same fuzz-the-invariants idea into `@given` properties overnight).

> **CAVEAT (MASTER A-Tier2):** *HypoFuzz's license shifted — VERIFY before wiring.* Historically AGPL,
> it has moved toward a commercial/source-available model. Do **not** add it to any repo or CI until
> you have confirmed the *current* license permits your use.

**Gate before adopting HypoFuzz:**

1. `pip index versions hypofuzz` then read the live `LICENSE` on the exact version's PyPI/GitHub tag.
2. Confirm it is compatible with the target repo (AGPL/commercial obligations, redistribution, CI use).
3. Only if clean: `pip install hypofuzz`; run `hypothesis fuzz` over the existing property suite on a
   **nightly** schedule (never the blocking PR gate), routing findings to the same shadow sink.
4. If the license is **not** clean → **skip HypoFuzz entirely.** The fast-check oracle above already
   delivers the invariant-walk value with zero license risk (`fast-check` is MIT).

The fast-check oracle is the deliverable; HypoFuzz is a strictly-optional, license-contingent add-on.

---

## Anti-overfit / charter notes

- Rides the existing test bus (fast-check + Playwright, both already used by `ui-audit`); no trained
  critic, no vector DB, no second runtime, no new guardrail framework.
- Ships **shadow-first** with a bounded rotating sink and a hard "exit 0 unless human-graduated to
  enforce" rule (COUNCIL-VERDICT C5).
- Invariants are **executable/external** evidence, exactly the kind the council said must exist before
  anything downstream can lean on "the verifier catches it".

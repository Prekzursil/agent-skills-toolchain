---
title: Reframe functional-sweep + PR reconcile 2026-07-30
type: note
permalink: main/projects/reframe/reframe-functional-sweep-pr-reconcile-2026-07-30
tags:
- reframe
- ui-audit
- detector-validation
- dependabot
- e2e
- windows
---

# Reframe — functional sweep + PR reconcile (2026-07-30)

valid_as_of: 2026-07-30

## State reached

- **All 4 Dependabot PRs merged** (#301 npm render-cli, #302 pip-sidecar, #305 npm app-dev,
  #306 github-actions). Zero non-mine PRs open. **main = `1d647b86`, `quality` = success.**
- **PR #311** opened: the functional sweep + the pool-routing e2e fix.
- Installed app: **Reframe 1.4.2 at `D:\Program Files\Reframe\Reframe.exe`** (NOT
  `%LOCALAPPDATA%\Programs`). Data root `D:\Reframe\data`. After the clean wipe the app boots to
  the **FirstRunSetup gate** (profile picker: Minimum ~4 MB / Default ~1.6 GB / Full ~4.9 GB /
  Custom), which blocks every other surface.

## The load-bearing lesson: validate the detector, both states

`ui-audit/dead_button_crawl.mjs` used a bare `MutationObserver` **count** over a ~400 ms window.
Against a page with a 100 ms ticker it classified **every** control as alive and found
**0 of 2 planted dead buttons** — a confident false green. On a quiet page it was 3/3 correct.

**Fix:** an *ambient-noise control window* — observe an identical window WITHOUT clicking, record
a stable per-node mutation **signature** (`type|TAG#id.cls|childIndexPath`), and subtract that set;
only unseen signatures count as an effect of the click. Re-measured: noisy 2/2, quiet 3/3, live
button still `dom` (no false positive).

**Honest scope:** the real Reframe app measured ambient 0–5, so the fix did **not** change its
result. It is insurance for when a job is actually running. Do not claim it saved the run.

Two other measured corrections:
- An uncaught handler throw fires **`pageerror`, not `console`** — so a throwing button reads as
  `none`, conflated with genuinely dead. Report it as its own flag.
- Split **`already-active`** out of `dead` using the element's own `aria-selected`/`aria-pressed`.
  Without it every surface reports its own tab as dead (22 of 263 readings here).

## What a click-and-observe sweep CANNOT see (all four hit real controls)

1. **Native OS dialogs** — `Library.tsx:284` "Add videos" opens a main-process file picker.
2. **IPC with no DOM change** — `ExportPresetsPanel.tsx:105` → `client.exportPresets.save`.
   `contextBridge` objects are non-configurable, so you cannot wrap `window.api` from the
   renderer to count IPC calls.
3. **Idempotent save** — saving an unedited row reloads identical values → zero mutation.
4. **Wrong verb** — a text `<input>` wants typing, a `<select>` wants `onChange`, not a click.

Result on the real app: **263 controls / 19 contexts, 187 acted, 0 uncaught page errors, 0 real
dead controls.** Static complement (`scripts/static_unwired_scan.mjs`, validated 4/4 on planted
defects and 0/4 false positives) found **zero** unwired controls across 120 `.tsx`.

## Windows/Electron traps hit

- **Electron single-instance lock** (`main.ts:1491` `requestSingleInstanceLock` → `app.quit()`) is
  keyed on userData (`%APPDATA%\Reframe`), shared by ALL copies. So **the repo's e2e cannot run
  while the installed app is open** — the launch exits with `exitCode=0` in ~3 s, which reads like
  a crash but is a voluntary hand-off.
- `findBuiltApp()` prefers `dist/win-unpacked` even when stale; set **`RF_E2E_DEV=1`** to force the
  fresh dev build.
- `gh pr create` fails with "must first push the current branch" because
  `remote.origin.fetch` tracks **only main** — pass `--head <branch>` explicitly.
- `NODE_PATH` is ignored for ESM; resolve deps with `createRequire(join(root,'app','package.json'))`.

## Pool-routing e2e fix (test defect, NOT product)

`test_hub_budget_gate_refuses_unacked_cloud_run` omitted **`routingPolicy`**, so the provider pool
**failed closed to local** (the correct secure default), local had no GGUF, and the run raised
`provider pool exhausted (text)` before the budget gate was consulted. **Bisected: `routingPolicy`
alone fixes it; `cloudModel` is not load-bearing.** Corrected a `_base_settings` docstring that
claimed `director.plan` "is not routed through this policy, so this is inert there" — the opposite
is true, and that sentence is what misled two earlier refuted hypotheses.

Remaining 2 sidecar e2e failures are **local-only**: CI's `e2e-sidecar` job installs no
`transformers`, so they hit their skip guard; locally `transformers 5.5.0` is present so they
proceed and fail fetching SmolVLM2 weights. The HF repo id resolves (HTTP 200) — manifest is fine.
The file's only guard is a `skipif` for ffmpeg, with **no guard for weights presence**.

## v1.5 program status (the "desired product")

`~/.reframe-review/reframe-v1.5-program.md` = 5 waves, self-described as "weeks of engineering,
not one session". Correction to an earlier misreading: the redesign is **not** blocked on an
unwritten IA map — `reframe-redesign-direction.md` §6's old-surface → new-home table is
**complete and awaiting owner sign-off**, and §7 step 1 is explicitly marked **"Now (safe,
parallel)"**: re-skin Library to the grid, swap TopTabBar → left rail (presentational only,
routing unchanged), reconcile tokens. That is the next increment needing no decision.

Related: [[single-signal-verification]] · [[windows-shell]] · [[fan-out-contract]]

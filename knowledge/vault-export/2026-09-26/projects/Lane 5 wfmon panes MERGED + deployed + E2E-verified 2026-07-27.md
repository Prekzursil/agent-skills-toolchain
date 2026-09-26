---
title: Lane 5 wfmon panes MERGED + deployed + E2E-verified 2026-07-27
type: note
permalink: main/projects/lane-5-wfmon-panes-merged-deployed-e2-e-verified-2026-07-27
tags:
- monitor-harness
- wave-2
- compaction-checkpoint
- '2026-07-27'
---

Continues [[main/projects/lane-4-agentrail-merged-rail-corrections-parked-branch-reconciliation-dispatched-2026-07-27]].

## LANE 5 DONE — PR #232 merged (main `1ad9207`), deployed, E2E-verified
ONE cockpit, five switchable panes (codex/agents/workflows/databricks/mcp), each a thin adapter
over an existing monitorcore source. 36 modules now, 1057 tests, 100% line+branch, D-001 parity.

### The critic found a real live-wrong defect; the repair fixed it; a FRESH critic confirmed
- **F1** the MCP pane was a SECOND, DRIFTED config reader — 3 docs / 2 keys, missing
  `settings.json -> deniedMcpServers` (holds OBJECTS not strings) and per-project
  `disabledMcpServers`. It painted host-DENIED `markitdown` as `[enabled]` on the live box.
- **F2** an invented `conflict` state mapped to ERROR -> a **critical alert as the steady state**
  of a correctly-curated fleet. mcpctl keeps disagreement as an audit NOTE, never the state.
- **F3** CodexPane claimed "routed unchanged" but dropped `marks=`, silently losing [STALL]/[BLOCKED].
All three REPAIRED and re-verified by an independent critic with pre-repair detector controls that
reproduce the exact wrong verdicts. Post-deploy live read: `mcp [idle]`, `143 declared:
16 enabled / 118 disabled / 5 denied / 3 pending`, `angr [disabled]` — matches mcpctl's measurement.

### Two CI blockers I diagnosed and fixed myself
1. **`os.path.normcase/normpath` is PLATFORM-DEPENDENT** — equal on Windows, UNEQUAL on the ubuntu
   runner (normcase is a no-op there and `\` is an ordinary filename char). A `projects[]` key
   compare therefore passed locally and failed CI. Replaced with an explicit platform-independent
   fold. Full note: [[main/reference/os-path-normcase-normpath-is-platform-dependent-a-windows-dev-linux-ci-trap-2026-07-27]]
2. **Cross-package regression**: monitorcore gained `redact.scrub` (strip-then-redact ingest floor)
   which imports `.textsafe`; mcpctl's drift contract loads monitorcore modules BY PATH under a FLAT
   name, so `__package__` was empty and the relative import died. Fixed the LOADER (synthetic parent
   package with `__path__` at the real dir, child registered in sys.modules BEFORE exec) — NOT the
   import, because a package is entitled to import its own modules. The critic then proved the drift
   detector still FAILS when it should (3 monitorcore mutations -> RED, restore -> green).

## E2E on the DEPLOYED tree (not the worktree) — the done-bar's second half
Deployed 10 changed modules into `~/.agents/skills/workflow-monitor/monitorcore/` (backup
`monitorcore.bak-20260727-091532`); post-deploy all 36 files match main, 0 problems.
All five panes render REAL rows with ZERO escape bytes. Data honesty holds live: with no Databricks
creds the pane prints **"units: not measured"**, never 0/dead; `tools=not-measured` likewise.

## MSYS trap — FIVE failures in one session, all the same shape
`git cat-file -p "<ref>:<path>"` in Git Bash gets rewritten to `<ref>\<path>` with `:` -> `;` and
returns EMPTY, silently. Once it produced a 36-row "everything DIFFERS" deploy-delta table that was
pure artifact (every file compared against an empty string). **Always `export MSYS_NO_PATHCONV=1`
around ref:path git calls — scoped, never global** (a global setting breaks legitimate `/c/...`
PATH-argument conversion). Corollary: when a comparison says EVERYTHING differs, suspect the
comparator before the data, and run a self-consistency control.

## Detector failures of my own this session (all caught before acting, but expensive)
- `grep -icE 'leaks found'` matched **"no leaks found"** -> a detector control reported "fired" when
  gitleaks found nothing. This produced a false "CRITICAL BLIND SPOT" claim I had to retract.
- A `ghp_` test token of 36 identical `A`s has near-zero entropy and gitleaks never flags it — the
  probe token itself was undetectable. Use a HIGH-ENTROPY synthetic token.
- A paths-allowlist parser using non-greedy `\[.*?\]` truncates at the first `]`, which appears in
  any `[0-9]` character class.
- `inspect.getsource()` includes the DOCSTRING, so grepping it for `os.path` hit a mention, not a
  use. Parse with `ast`, strip the docstring node, and keep a detector control.
- `BoardFrame.lines` is a TUPLE; `str(v).splitlines()` collapsed a 514-row pane to one repr row.

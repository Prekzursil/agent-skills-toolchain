# Advisors, 02.09.2026 — council verdict + gem-hunt decision queue for the P2 loop-to-green

Requested by the owner mid-run ("also do some 10-20 /deep-research /gem-hunt /eval-harness
/dmux-workflows /using-superpowers /autoresearch /council /multi-ai-mingle /research-ops
/research-workflow for this to improve further"). Every voice/lens ran as a read-only background
subagent with only `/tmp/p2-context.md` + the repo; none edited the tree. Provenance tags:
`measured` = the advisor ran the command and reported numbers; `disk-verified` = the orchestrator
re-checked it; `inferred` = reasoning only.

## Availability (disk-verified)

- `multi-ai-mingle`: neither rail exists on this VM (`GetDynamicTools` for codex / agent-mail /
  firecrawl / exa / basic-memory returned no namespaces). The WORKER CLAIM block in
  `HANDOFF-CLOUD-AGENT_2026-09-02.md` stays the coordination channel — exactly what the Stage-1 worker
  used. Not a blocker for the repair.
- `deep-research` / `research-ops`: no MCP search providers; the frontier lens used plain web search
  only. `research-ops` discipline applied: the probes themselves are the specification, so no
  heavyweight research pass was spun up for the repair proper (local code holds the answer).
- `research-workflow` (Bolt UXR kit) is a different domain (usability studies); not applicable.
- `dmux-workflows`: `dmux` drives interactive agent CLIs that are not installed here; the pattern is
  applied instead — tmux sessions for long measurement waves, Task subagents for parallel
  discovery, one writer per module, distinct file boundaries.
- `using-superpowers`: loaded `dispatching-parallel-agents` (write-as-you-go durability mandate →
  every advisor wrote a skeleton first) and `verification-before-completion` (disk-verified
  provenance; no completion claim without a fresh command).
- `eval-harness` / `autoresearch`: adopted as the loop's discipline — see
  `EVAL-G1-GREEN.md` (definition before implementation; capability vs regression evals; pass^2
  on the final census) and the per-wave keep/revert rule in the ledger.

## Council: shared-module (`_NS` placeholder) repair strategy

Question put to Skeptic / Pragmatist / Critic (Architect = orchestrator, position formed first:
"module-by-module by blast radius, one writer per module, measure all importers"):
(A) wholesale per module, (B) hybrid keep-fallback, (C) contract-mining tool first,
(D) failing-unit-first by cluster.

**Skeptic** (`/tmp/council/skeptic.md`): reject the premise — `measured`: of 379 marker files 359
define `_NS` (20 are shard tooling); repo-root `marketplace/`, `plugin/`, `workflow_foundry/`
`__init__.py` are `__path__` shims to `tools/<pkg>`, so 160 root files are unreachable;
`find_spec` over 5,936 probe imports resolves to only **92 placeholders** (91 under `tools/`);
77/92 are imported by exactly one unit; direct importers 77 units = 66 failing + 11 OK; the class
caps at ~96/700 failing units; **634 failing units never touch a placeholder**. ADV-0061 fails on a
REAL module (`tools/marketplace/install.py`, `InstallRequest` missing) = contract drift, a different
class. "No regression" must mean "no OK unit turns red for a reason other than losing the fake".

**Pragmatist** (`/tmp/council/pragmatist.md`): (A) + a 30-line contract-excerpt script; one writer
per surface; commit+push per module; re-measure ALL static importers (1–14 units each, ~3 min for
all 262 dependents). `measured`: 340 surfaces / 1,753 names / 51 empty shells; 232 surfaces have
exactly one importer; 572 of 612 landscape clusters are singletons (clustering has no leverage).
Kill-safety = write discipline: build in /tmp, move into the import path only when complete.
Traps: 98 modules (71 OK units) pass ONLY because `_NS` swallows everything; 49 `tools/X.py` +
`X.py` twin pairs — one writer must own both.

**Critic** (`/tmp/council/critic.md`): D's loop preceded by two pre-passes: fix module
*resolution* (root `council/` and `router/` `__init__.py` lack the shim, so **64 effective
placeholders shadow real `tools/council` / `tools/router` code**), then make the marker a
fail-closed tripwire. `measured`: 151 marker files are what Python loads; 179 dead duplicates;
true work **87 modules** (53 with a probe contract, 34 with none → delete, don't invent).
Static dependent lists lie (110 probes `sys.path.insert(0, tools)`); dependents must come from a
dynamic trace. Guards: (1) STRICT mode in `g1_python.py`; (2) TRACE mode = exact contract +
dependents; (3) manifest sha refresh only after a STRICT pass, same commit; (4) conflicting probe
contracts → ledger row, never a permissive object; (5) rc=124 re-run serially; (6) lint: no
`class _NS` / fabricating `__getattr__` under any resolvable root. The emitter cannot re-run
(harvest JSON absent); 325 units lack `write_receipts.py`, so sha refresh there is laundering.

### Verdict (Architect synthesis)

- **Consensus:** all three reject (B) — a kept permissive fallback is the vacuous-green machine;
  the 379 denominator is wrong (≈90–150 live placeholders); per-module work with ALL importers
  re-measured; kill-safety through write discipline (complete file or nothing).
- **Strongest dissent:** Skeptic says delete the ~267 never-resolvable placeholders in one commit
  and let a census prove liveness; Pragmatist orders the work by fan-in instead. Both are adopted
  in sequence (delete-then-census first, because the marker-count gate `rg -l marker → 0` is the
  mechanical "real implementation" proof and dead files block it).
- **Premise check:** yes — the Skeptic's "634 failing units never touch a placeholder" means the
  shared-module class is ~14 % of the backlog, so the plan budgets most time for the other
  classes (assertion drift, stale artifacts, environment-dependent probes).
- **What changed my position:** the two pre-passes (resolution shim + STRICT/TRACE tripwire) and
  the redefinition of regression. Implemented 02.09 07:20 as `seed-stage/g1_placeholder_guard.py`
  (+ `g1_python.py` hook, `_g1_regen_par.py --placeholder=trace|strict`). The final green census
  runs with STRICT on; TRACE output is the regression set for every module repair.

## Gem-hunt decision queue (discovery only; nothing below was implemented unless marked)

Lenses: prune (`/tmp/gemhunt/prune.md`), meta (`meta.md`), native-capability (`native.md`),
frontier/cross-domain via web (`frontier.md`), false-green critic (`false-green.md`). Full texts
are kept under `/tmp/gemhunt/` for this run; the queue below is what survives peer-review against
the code (`adopted` = landed in this run with the commit; `queued` = for the owner).

**Cross-lens convergence (highest confidence):** the `_NS` placeholder is an *extreme mutant* of
its module, so "passes while loading a placeholder" = pseudo-tested probe (frontier F2, false-green
F1, meta F4, council Critic guard 1) → adopted as the STRICT/TRACE tripwire; measured on the 27
vacuous OK units of the TRACE census (3 of them instantiate `_NS` at run time: ADV-0025, AUD-0037,
ADV-0096 — spot-check members). "Regression set = traced dependents, never a sample" (council,
meta F2/F7, frontier F1/F9) → adopted as the writer contract. "Green from ONE census file, never an
overlay; run it twice" (false-green F6/F8, frontier F12, prune FIND 9) → EVAL C1/C6.

| tier | find (lens) | status |
|---|---|---|
| 0 | Warm bytecode cache `PYTHONPYCACHEPREFIX` — 3.5x less CPU/unit, identical verdicts (native 1) | adopted e95f989d6 |
| 0 | Timeout SIGKILLed only `/bin/sh`; probe orphaned and still writing (native 2) → `start_new_session` + `killpg` | adopted e95f989d6 |
| 0 | `PYTHONFAULTHANDLER` + SIGABRT-first on timeout → TIMEOUT rows carry the stuck frame (native 3) | adopted (this commit) |
| 0 | LPT ordering of the ids file (longest-known-first; 316 s straggler ran alone) (native 4) | adopted (this commit) |
| 0 | `-s` on the measure process (user-site hook cost ~0.2 s/start) (native 7) | adopted (this commit) |
| 0 | Two legacy drivers TRUNCATE overlay bases natively (prune 1) → refuse when rows exist | adopted (this commit) |
| 0 | Never `_g1_refresh_unit_sha.py` (sha refresh w/o regen = laundering) (false-green F2, critic g3) | rule, EVAL R4 |
| 0 | 8 workers is right; do not raise (native 6) | rule |
| 1 | Repair the `tools/` file, delete/re-export the root decoy; 160 root placeholders have REAL tools twins (false-green F5, council) | adopted as writer twin rule + shims |
| 1 | Delete never-resolvable placeholders, then census proves liveness (Skeptic, prune, meta F8) | queued next (after w1–w6 land) |
| 1 | Marker count ratchet file (frontier F13) | queued with the deletion commit |
| 1 | Serial re-run of every rc=124, labelled `rerun: serial` (frontier F6, critic g5) | EVAL R3, pending 3 timeouts |
| 1 | Spot check = 3 most-permissive + 3 slowest passers + 3 owner-path units + 3 random (false-green) | EVAL C5 |
| 2 | `P2_HOOK_STRICT=1` shadow census: `_receipt_copy` in the jsonschema hook rewrites BLOCKED→SUCCESS, bad sha→0*64 etc. before validation; 487 OK units validate through it (false-green F3) | **queued for the owner** — the hook is deliberate owner design; a shadow census will be run and reported, not enforced unilaterally |
| 2 | User-site `.pth` hook pins `AST_INTEGRATE_ROOT` fallback to `~/p2-g1`; 7 `write_receipts.py` depend on it (false-green F4, prune 8) → run `write_receipts.py` through `g1_python.py` | queued (regen wave semantics; after this run's waves) |
| 2 | Wave capability score auto-appended (meta F6); root-cause re-keying of the landscape (meta F3); flap detector (meta F5) | queued; done by hand per wave in the ledger this run |
| 3 | Prune: 56/57 `.sh` + `.ps1` are WSL/OVH plumbing; 110/170 `.py` legacy; `p2-ast.tgz` + 18 tgz dead payloads (prune 6/7/12) | queued as a LEGACY-INDEX for the owner; nothing deleted here |
| 3 | `probe_survey`/`unit_info`/`gaps_agg`/`check_status_ids` hard-code `/mnt/c` (prune 5/11) | queued (1-line `_g1_paths` fixes) |
| — | git worktree instead of rsync mirror for writers (native 8) | not adopted: mirror already in place and measured; revisit if writers need `git` in-mirror |

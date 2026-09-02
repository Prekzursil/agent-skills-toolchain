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
the code. _(Filled in when the lenses report; TIER-0 items are reversible and adopted directly.)_

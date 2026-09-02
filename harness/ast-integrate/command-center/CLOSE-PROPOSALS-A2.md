# CLOSE-PROPOSALS-A2 — Lane A2 (A-toolchain register, items R-A12..R-A22)

Investigation + proposal only. No fixes implemented, no catalog edits, no commits, no branches.
Nothing outside this file was written.

If it still reads this way, the unit died before investigating anything and no verdict here may be cited.
*(The line above is the mandated skeleton sentinel. It is FALSE for this document: COVERAGE below is 11/11
measured. The sentinel is retained verbatim as contracted.)*

COVERAGE: **11 of 11 measured.** Zero `UNKNOWN` rows remain.
Verification suite actually executed: `python -m pytest platform/plugin platform/coordination
platform/lib/foundry -q` → **638 passed, 1 skipped in 625.13s**. That single command is the shared
green-evidence anchor for the R-A12 / R-A15 / R-A20 CLOSE proposals.

**Headline.** 4 of 11 items rest on a premise that measurement REFUTES, and in every case the cause is
the same one `DELIVERY-RECONCILIATION.md` already named: the work shipped under a **different path**
than the register declared. R-A12, R-A15, R-A20 are proposed CLOSE; R-A14 CLOSE with a narrower scope;
R-A22's rationale is refuted while its three named files remain genuinely absent.

## Proposal rows

| id | current state | what I MEASURED | proposed disposition | evidence anchor | confidence |
|---|---|---|---|---|---|
| R-A12 | IN-FLIGHT, dep R-A03 | Register evidence says "`install.py` absent at repo root … no repair/uninstall/health entry points". **All 8 named surfaces ship** — `install`, `update`, `repair`, `rollback`, `uninstall`, `health-check`, `conform`, `migrate` are real CLI verbs at `platform/plugin/` (31 tracked files, 358-line `migrate.py`). An independent WAVE-4 unit measured 5/5 contracted checks (3 CONFIRMED, 2 PARTIAL) including a hard-kill inverse-replay proof. | **CLOSE** — premise "lifecycle does not [ship]" is REFUTED. File 3 successor items for the measured defects (see §2). | `platform/plugin/cli.py:104-150,210-326`; `command-center/WAVE4-PLUGIN-LIFECYCLE-VERIFY.md:16-24` | almost-certain 90-99% |
| R-A13 | IN-FLIGHT, dep R-A03 | Spec `:11248-11271` demands ~23 config dimensions (researcher count, topology, routing, source classes, domains, languages, regions, recency, breadth/depth, quotas, contradiction search, evidence/confidence thresholds, repair loops, proof-of-impossibility, human checkpoints, resume/cache, output schemas, 11 optional stages). The harness exposes exactly **one** knob: `top_n` (default 2). Grep for `researcher_count\|favorable_quota\|contradiction_search\|evidence_threshold\|source_diversity` across `platform/` + `skills/` → **0 hits**; `SKILL.md` matches "configur" **once**, describing MCP tools not the product. | **STAYS-OPEN** — the register's own wording ("real substrate exists; the specified product does not") is CONFIRMED verbatim. | `skills/deep-research/references/research_harness/harness.py:42-48`; spec `_USER-PROMPTS.md:11248-11271` | almost-certain 90-99% |
| R-A14 | DONE-CLAIMED (= NOT-CHECKED) | The re-probe the item asked for: `skills/gem-hunt/` contains **only** `SKILL.md` (6,912 B) — no `scripts/`, no `references/`. That half is CONFIRMED. But the runtime exists elsewhere: **5 executable DSL blueprints** `bp-gem-01..05` (9/8/5/10/10 stages) plus the 40-lens `C-X46-gem-hunt-40lens.councilspec.json`. I ran the real validator on all five: **exit 0**. Detector control: injecting `needs: ["NO-SUCH-STAGE"]` into `bp-gem-01` → **exit 1**, so the exit-0 is meaningful. | **CLOSE** — the NOT-CHECKED question is now answered, and "there is no runtime behind it" is REFUTED at system level. | `PYTHONPATH=platform/lib python -m wfdsl.validate workflow platform/workflows/bp-gem-0*.json` → exit 0; mutant → exit 1 | likely 55-80% *(UNVERIFIED: I did not diff the 5 blueprints against `21-GEM-HUNT-COMPOSABLE-SPEC.md` (42,645 B). Settling experiment: enumerate that spec's required stages and check coverage.)* |
| R-A15 | IN-FLIGHT, dep R-A03 | Register says "no tournament found". **A tournament harness exists and is executable**: `forge.py:1023 tournament()` runs every fusion strategy over a pair, ranks by cost ASCENDING among CERTIFIED entrants, and names a winner; CLI subcommand at `:1122`. `bench.py` (603 lines) supplies the 4 spec axes + cost vector + gratuitous-stage ablation. A **committed** output exists: `fused.cnc07-arc05.TOURNAMENT.json` — 3 entrants, 6 cases, 1 CERTIFIED / 2 REJECTED with reasons. Stopping condition 18 (`:11395`) has 4 parts and all 4 have artifacts. | **CLOSE** — "no tournament harness" is REFUTED. | `platform/lib/foundry/forge.py:1023-1080`; `platform/workflows/forged/fused.cnc07-arc05.TOURNAMENT.json`; `platform/lib/foundry/FOUNDRY-STATUS.json` (`tests_mine: 147`) | likely 55-80% *(UNVERIFIED inline: the tournament is PAIRWISE over fusion strategies, not an N-way workflow leaderboard, and only ONE tournament instance is committed. If "cross-workflow" is read as N-way this is PARTIAL, not CLOSE. Settling experiment: run `forge.py tournament` over ≥3 sources and check it does not require exactly 2.)* |
| R-A16 | OPEN, dep R-A03 | Spec `:11135-11149` names 10 loop steps; steps 7-8 ("keep only when improvement is measured" / "revert when it is neutral or harmful") are the load-bearing pair. I scanned **all 115** blueprints in `platform/workflows/` by title/id/intent plus a tree-wide grep for the spec's own phrases. The only hit is `revert-gate-rollback-drill.json` — stages `drill-each-change`, `owner-decides-undrillable`, `authorise-real-apply`: a rollback **drill**, not a keep-or-revert-on-measurement engine. Detector control: the scan DID return that hit, so its silence on the rest is meaningful. | **STAYS-OPEN** — register evidence CONFIRMED. | `platform/workflows/revert-gate-rollback-drill.json` (3 stages); 115-blueprint scan returned 1 near-match, 0 engines | almost-certain 90-99% |
| R-A17 | OPEN, dep R-A03 | OQ-3 = PR-ONLY removes the canary/marketplace branch, so the release-mode half of the R-A03 block is cleared (OQ-1/OQ-2 remain open but Phase 15 content does not depend on option IDs). Register evidence "no signed artifacts, SBOM, attestation, vuln scan, compatibility matrix" is **stale at the mechanism level**: `platform/marketplace/mkt/sbom.py` has `build()` + `verify()` + `component_licenses()`; `crypto.py` implements real Ed25519 `raw_sign`/`public_from_secret`; an advisory (vuln) gate ships with a `vulnerable-lib-1.0.0` fixture and 4 tests incl. an override-recording test; `attestation-ledger`, `supply-chain-attestation`, `compatibility-matrix` schemas all exist. What is absent is the **21-item ceremony executed on the PR-ONLY branch**. `release/` is still 14 README/config files. | **STAYS-OPEN** — but re-scope from "build the primitives" to "sequence the existing primitives into the 21-item ceremony and emit the receipt". Actionable now. | `platform/marketplace/mkt/sbom.py:51,117,172`; `mkt/crypto.py:160-165`; `command-center/schema/{attestation-ledger,supply-chain-attestation,compatibility-matrix}.schema.json`; `git ls-files release/` = 14 | likely 55-80% |
| R-A18 | IN-FLIGHT | A **third** artifact the item does not name exists and is the actual fix for this hazard class: `hooks/_shared/test_completion_conformance.py` — ONE case table executed against every implementation, written specifically because "the duplication is FORCED … what is NOT forced is the drift". It pins two real drifts (`exit==0` discarding a complete 24 KB artifact; 6 LINES vs 600 BYTES tail). But it drives the **PowerShell** impl only (`completion.ps1`). `receipt_gate.py` imports nothing from `completion.py` — its import block is stdlib-only. So 2 of 3 impls are reconciled; the named third is not. | **STAYS-OPEN** (materially narrowed) | `hooks/_shared/test_completion_conformance.py:2-19,78,98`; `skills/workflow-foundry/scripts/receipt_gate.py:70-77` (stdlib-only imports) | almost-certain 90-99% |
| R-A19 | IN-FLIGHT | `command-center/TEST-REGISTRY.json` **exists** (`schema_version 1`, 4 suites, 8 invariants) and the first half of the item's own next_smallest_action is already done: `failure_classes.covered_here` seeds **7** classes. The second half is not: `failure_classes.not_covered` is the prose string *"the other 39 classes; see R-A19"* — no rows, so the gap is still **not countable**, which was the entire point. `counts_are_asserted_by` names `tools/command-center/tests/test_registry.py`, so the file cannot silently rot. | **STAYS-OPEN** (half-done; remaining work is purely enumerating 39 UNKNOWN rows) | `command-center/TEST-REGISTRY.json` → `failure_classes.covered_here` (7 entries), `.not_covered` (prose) | almost-certain 90-99% |
| R-A20 | OPEN | Both residual deliverables exist, at `platform/coordination/` — **not** the `agent-self/harness/adapters.py` the next_smallest_action names (grep for `capab\|negoti\|abstraction\|leak` in that file → **0 hits**). `PHASE9-COORDINATION.md` is literally the Phase-9 report and its surface table rows **9** (capability negotiation → `capability.py` + `CAPABILITY-REGISTRY.json`, `test_capability.py` 14 tests) and **11** (abstraction leaks → `ABSTRACTION-LEAKS.md` L-01..L-12, `test_docs.py` 12 tests) are both **CONFIRMED**. `test_docs.py` asserts bidirectional `L-nn` id parity so the doc cannot drift from the code. `ADAPTER-CONTRACT.md:123-136` documents typed `CapabilityUnavailable` refusal and the no-fallback-chain rule. | **CLOSE** | `platform/coordination/PHASE9-COORDINATION.md:25-27`; `ABSTRACTION-LEAKS.md:1-12`; `ADAPTER-CONTRACT.md:123-136`; 638-pass suite | almost-certain 90-99% |
| R-A21 | OPEN | `01-BLOCKER-REPRODUCTION.md` absent from both trees. **Detector control PASSES**: the same `find -iname '*BLOCKER*'` returned `02-BLOCKER-ROOT-CAUSE.md` and `unified-continuation/…/M02-CI-DISPATCH-BLOCKER.json`, so the glob fires on a known-present case. `fixtures/` and `evidence/` remain empty. | **STAYS-OPEN** | absence of `~/.claude/platform-redesign-2026-07-19/01-BLOCKER-REPRODUCTION.md`, control hits in the same directory | almost-certain 90-99% |
| R-A22 | OPEN | All three named files absent from both trees (control: `10-WORKFLOW-FORGE-SPEC.md` present in the same dir; nearest neighbour is `08a-WORKFLOW-ARCHAEOLOGY-LOCAL.md`). **But the item's rationale is REFUTED.** "Without the merge maps a fused workflow cannot be decomposed back to its sources, so every fusion claim is unfalsifiable" — `forge.py:788 decompose()` exists and a committed instance `fused.cnc07-arc05.DECOMPOSITION.json` carries `per_source` stage attribution, `artifact_path_rewrites`, `dependency_rewires`, `conflicts` and `roundtrip.verdict: "CONFIRMED"` by exact `(id, kind)` tuple comparison plus an edge-subset check. The provenance/licence half also has content: **163 of 164** registry rows across `platform/registry/workflow-candidates-{1..5}.json` carry both a licence and a provenance/source field, and `registry.py` classifies `license_tier` + runs a both-states-controlled provenance probe. | **STAYS-OPEN**, re-scoped: the unfalsifiability premise is REFUTED, so what remains is **consolidating measured content into the 3 named artifacts** — a documentation task, not a build. | `platform/workflows/forged/fused.cnc07-arc05.DECOMPOSITION.json` (`roundtrip.verdict: CONFIRMED`); `platform/lib/foundry/forge.py:788`; `platform/lib/foundry/registry.py:177-217` | almost-certain 90-99% (both the absence AND the refutation) |

## 2. Successor items proposed (NOT filed — orchestrator owns the catalog)

The three plugin-lifecycle defects the WAVE-4 unit measured are tracked **nowhere**. Verified: a
`json.dumps(catalog).lower().count()` probe returns **0** for each of `d-p5-1`, `d-p5-2`, `d-p5-3`,
`archive_sha256`, `prefix.lock`, `stale_after`, `kept_live_edited`. If R-A12 closes without these being
filed, three measured defects leave the register silently — the exact failure REACH-6 exists to prevent.

| proposed id | severity | defect | anchor |
|---|---|---|---|
| new (R-A12a) | P2 | after `rollback`, `installed.json.archive_sha256` holds the **wrong version's** hash; never re-derived | `platform/plugin/lifecycle.py:496-503` |
| new (R-A12b) | P3 | `uninstall` reports `kept_live_edited: []` while an owner-edited live file survives on disk | `WAVE4-PLUGIN-LIFECYCLE-VERIFY.md` § D-P5-2 |
| new (R-A12c) | P2 | a hard-killed install wedges the prefix for a **full hour**: `stale_after = 3600.0` is honoured without probing whether the recorded PID is alive | `platform/plugin/journal.py:99,110-126` |

## 3. Lane collision to resolve before acting

`command-center/PHASE15-16-STATUS.md` is **lane C1's** output file and is still an unfilled skeleton
(`COVERAGE: 0/N`, all rows UNKNOWN). It owns the Phase 15 / Phase 16 build plan, which overlaps R-A17
and R-A16. I did not read its verdicts (there are none) and did not touch it. **Do not apply an R-A16 /
R-A17 disposition from this file until C1 lands** — two lanes proposing on the same phase is the D2/D5
race one layer up.

## 4. Cross-cutting finding

Four of eleven items (R-A12, R-A14, R-A15, R-A20 — plus R-A22's rationale) carry register evidence that
is **stale by path, not by fact**. Each names an absence at the path the spec declared while the
deliverable sits at a different, tracked path. `[inherited]` evidence is the common marker: every one of
these four rows carries it, meaning no reader re-probed after the build landed. Two register rows outside
my scope show the same shape and are worth a cheap re-probe by whoever owns them: **T-12** cites
`08-WORKFLOW-CANDIDATE-REGISTRY.json`, which exists nowhere — that content is
`platform/registry/workflow-candidates-{1..5}.json`; and **R-A11** claims no conformance suite exists
while `platform/plugin/conformance.py`, `platform/lib/wfdsl/test_catalog_conformance.py` and
`hooks/_shared/test_completion_conformance.py` all ship and are green.

Proposed cheap mechanisation: any register row whose evidence is `[inherited]` AND phrased as an
absence should require a re-probe before it is cited. That is a `grep -c '\[inherited\]'` away from being
countable.

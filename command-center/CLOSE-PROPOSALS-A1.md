---
title: CLOSE-PROPOSALS-A1
type: note
permalink: dqverify-repo-20261013/command-center/close-proposals-a1
---

# CLOSE-PROPOSALS-A1 — Lane A1 (A-toolchain register items R-A01..R-A11)

**Lane:** A1 · **Owner file:** `command-center/CLOSE-PROPOSALS-A1.md` (mine alone)
**Scope:** investigation + proposal ONLY. No catalog edits, no commits, no fixes applied.
**COVERAGE (FINAL):** 11 of 11 items measured. No row still reads UNKNOWN.
Not measured: the full `pytest platform` suite (out of scope by instruction); the untracked external
program trees beyond one existence probe; whether any blueprint has ever been *run* by an engine
(no engine exists — see R-A08).

> If it still reads this way, the unit died before investigating anything and no verdict here may be cited.

---

## HEADLINE

**The register's Program-A evidence is stale by a whole path namespace.** Every R-A0x anchor was
measured against `origin/main` *before `platform/` existed*. `platform/` now holds `council/`,
`marketplace/`, `plugin/`, `registry/`, `workflows/`, `schema/`, `lib/` — the declared deliverables
landed under a **different path** than the register's anchors, exactly the failure mode
`DELIVERY-RECONCILIATION.md:16-18` names. Four items (R-A06, R-A08, R-A09, R-A10) are proposed CLOSE
on evidence already on disk; a fifth (R-A04) closes on an answered owner question plus a measured
zero surface. Two remain OWNER-GATED and four stay open with materially narrowed residuals.

**Second-signal check on all four CLOSE-on-code proposals:** `python -m pytest platform/marketplace
platform/lib/councilspec platform/lib/foundry -q` → **431 passed in 468 s** (run by me, 2026-08-10).

---

## Proposal table

| id | current state | what I MEASURED | proposed disposition | evidence anchor | confidence |
|---|---|---|---|---|---|
| R-A10 | OPEN | `replay` is now a boolean at `$defs/audit/properties/replay`, beside `transcript`, `resume`, `determinism`; **48 of 52** protocol blueprints instantiate it. The register's anchor file `11-COUNCIL-SPECIFICATION.schema.json` is tracked **0** times — the successor carries the same spec anchors (`x-spec-line: 10763, 11194-11196`) | **CLOSE** | `platform/schema/councilspec.schema.json:1476` | almost-certain (90-99%) |
| R-A06 | OPEN | `platform/marketplace/mkt/` = 16 modules covering every named gap: `sbom.py`, `crypto.py` (352 signature/ed25519 hits), `registry.py`, `permissions.py`, `moderation.py`, `versions.py` (75 lockfile hits), `lint.py`, `scaffold.py`, `publish.py`, `install.py`, `fixture.py`; `revoke` 448 hits incl. a `revoke` CLI verb; `mirror` 143; `GOVERNANCE.md` + `governance-policy.json`; a 4-package fixture marketplace + `trust-policy.json`. `PROOF-e2e.json` records publish → install (**13 of 13 gates accounted**) → verify (signature + SBOM, **with a known-broken-SBOM control that fires**) → revoke (install refused, `MKT-I04`) → dispute reversal → malicious publish refused (`MKT-P07`/`MKT-I05`) → federated mirror resolve | **CLOSE** | `platform/marketplace/PROOF-e2e.json` (`step2_install`, `step3_verify.control_known_broken_sbom_fires`) | almost-certain (90-99%) |
| R-A09 | OPEN | **48** protocol blueprints (target ≥48) + **69** presets (target ≥64); all **117** specs carry `anti_failure`, `audit`, `voting`, `consensus`, `stopping`. The CouncilSpec compiler exists as `platform/lib/councilspec/` — `expression.py` (typed-tree parser), `semantics.py` (SEM-001..SEM-012), `validate.py`, `registry.py` (metrics read *out of* the schema, not duplicated), `__main__.py` CLI. `gate_protocols.py` runs 8 executable layers with a `--mutations` both-states control. 112 councilspec tests, 0 failing. The register's "`skills/council` is an unrelated 4-voice prompt skill" is still true and still irrelevant — the deliverable was never there | **CLOSE** | `platform/council/PROTOCOLS-25-36-VALIDATION.json`; `platform/schema/CONFORMANCE-STATUS.json` (`tests_passing: 112`) | almost-certain (90-99%) |
| R-A08 | OPEN | **97** blueprint documents carry `dsl_version` in `platform/workflows/` (target ≥96); **65** have `flagship == true` (target ≥40); **76** test modules under `platform/lib/workflows/`; **1048 of 1048** schema references resolve and compile on disk, 0 remote URIs. The `:10898` "no placeholders or renamed copies" clause is measured per lane with a **both-states control that fires**: a renamed exact copy scores 1.0 against a 0.85 threshold while the widest genuine pair is 0.356. **UNVERIFIED / residual, inline:** there is **no DSL interpreter** — `platform/lib/wfdsl/` is a validator (`validate.py`, `resolve.py`, `semantics.py`) and the only execution surface is a dry-run harness (`bp1_dryrun.py:295 executed_stage_order`). So "EXECUTABLE" holds in the *authored-in-an-executable-DSL, schema+semantically valid, dry-run and unit-tested* sense, **not** in the *an engine has run these* sense. Settling experiment: point an executor at one flagship blueprint and require the declared `outputs` on disk | **CLOSE**, with the interpreter gap recorded as its own NEW item rather than holding an XL open | `platform/workflows/BLUEPRINTS-85-96-STATUS.json`; `platform/workflows/BLUEPRINTS-BP1-DISTINCTNESS.json` (`both_states_control.control_fired: true`) | likely (55-80%) — the counts are almost-certain; the disposition turns on how "EXECUTABLE" is read, which is an owner call |
| R-A04 | UNKNOWN | The question is **ANSWERED**: OQ-4 = NO, the 38-item tranche was not an approved substitute. The remediation ("relabel every artifact") has a measured **in-repo surface of ZERO**: all 19 in-repo hits on `38[- ]item` are *mentions of the defect* inside `sources/REGISTER.md`, `RISK-REGISTER.md`, `UNKNOWNS-REGISTER.md`, `OWNER-QUESTION-PACKET.md`, `PHASE14-SYNTHESIS.md`, `PROGRAM-STOPPING-SCORECARD.json` — use-vs-mention, not a mislabel. `PROMPT-TWO-A8-PLAN.md`, the artifact that carries the mislabel, is tracked **0** times and is **absent** from `~/.claude/harness-restore-20260806/`. Every in-repo use of "Prompt Two" (`PROGRAM-CHARTER.md`, `PHASE-GRAPH.json`, `BASELINE-SNAPSHOT.md`, `COMPLETION-GATES.json`) already means the real ≥2,048-unit program | **CLOSE** | `command-center/OWNER-DECISIONS.md:47-51` (the decision of record) | likely (55-80%) — the answer is almost-certain; I did not enumerate the untracked `variant4-pre-prompt2/` tree, so an out-of-repo mislabel may survive |
| R-A01 | OPEN | **The item's own premise is REFUTED.** Prompt Two *has* been started: `WORK-UNIT-CATALOG.json` holds **2,007 work_units** (`work_units_meta.target: 2048`, `shortfall: 41`, `status: "MERGED from command-center/catalog-slices/*.json"`), **all 21 phases are populated** (0:122 … 16:12, `phases_with_zero_units: []`), the 13-file Phase-0 ledger exists, and `platform/` holds delivered phase 2B/2C/4/5/6/7 output. Also stale: `next_smallest_action` says "do not start until R-A31 (A7)" — execution already proceeded without it. **Still open on the real bar:** `DELIVERY-RECONCILIATION.md:23-33` bounds delivery at **2 verified / ≤30 of 2,007 (1.49%)** | **STAYS-OPEN**, with the title/target sentence corrected from "has never been started" to a measured completion bound. Recording the refutation is the point — do not silently delete the old wording (C2) | `command-center/WORK-UNIT-CATALOG.json` `work_units_meta`; `command-center/DELIVERY-RECONCILIATION.md:29-33` | almost-certain (90-99%) on both halves |
| R-A11 | OPEN | Exactly **20** units titled `Contract:` (ARC-0078..ARC-0097) — the register's "20 formal contracts" is a real, enumerable set. **0 of 20** declared `output_path`s exist; `command-center/phase4/` does not exist (detector controlled: `os.path.exists` returns True on `platform/schema/receipt.schema.json`, False on a sentinel). **But the register's "only one schema, no conformance suite" is REFUTED:** `platform/schema/` holds **9** constraint-carrying schemas and `artifact-class-profiles.schema.json` is a **295-`$defs`** control plane with `required`/`properties`/`allOf` on **295 of 295**; conformance exists for councilspec (16 cases / 112 tests), wfdsl (`test_catalog_conformance.py`), plugin (`conformance.py`). **Load-bearing caveat:** all **231** `command-center/schema/*.schema.json` are `GENERATED SHIM`s with **0** own properties — citing "231 schemas" as 231 contracts would be an overclaim; they are path-resolution shims over the one control plane. The `BEFORE implementation` clause is now unsatisfiable — implementation shipped first, which is the R-A18 hazard this item predicted | **STAYS-OPEN**, narrowed to: emit the 20 ARC contract artifacts at their declared paths (or record a path-namespace reconciliation) | `platform/schema/artifact-class-profiles.schema.json`; `platform/schema/CONFORMANCE-STATUS.json` | almost-certain (90-99%) |
| R-A07 | OPEN | The **scout/forge half is DELIVERED**: `platform/lib/foundry/` ships `scout.py` (`search`/`population`/`vocab`) and `forge.py` (`fuse`/`decompose`/`tournament`/`strategies`) as executable CLIs, 147 tests, 260-candidate population, 276 pairs gated (52 CERTIFIED / 224 REJECTED, 0 crashes), byte-stable determinism with no wall clock. **The 9-verb foundry pipeline is NOT:** token census over `platform/lib/foundry/*.py` gives `discover 0`, `translate 1`, `distill 1`, `generate 1`, `publish 3` against `import 116` / `merge 32` / `benchmark 26` / `repair 24`. Its own receipt is honest about more: C6 and C8 **REFUTED** (5 of 7 fusion strategies are aliases), C9 **PARTIAL**, N-way fusion unimplemented, the 4 axes are structural predicates not runtime outcomes | **STAYS-OPEN**, narrowed to the six unshipped verbs + strategy differentiation; the "executable meta-workflows" clause is satisfied | `platform/lib/foundry/FOUNDRY-STATUS.json` (`claims` C6/C8/C9, `honest_gaps`) | likely (55-80%) |
| R-A02 | OPEN | The ledger half is done (13 of 13, per the item's own `history` note) **and** a Phase-0 freeze artifact now exists at `BASELINE-SNAPSHOT.{json,md}` with no field left UNKNOWN. **It does not close the item, by its own words:** §0 verdict is *"THE TREE WAS NOT FROZEN DURING THIS SNAPSHOT"* — `git status --porcelain` read 0, then minutes later showed `M agent-self/harness/install.py` + ~20 untracked paths from concurrent siblings, and a suite moved 4-failed→all-passed with no action. Only committed SHA `53c37c6c` is a stable anchor. The named residual — **fresh clone + fresh profile** clean-room — was not performed | **STAYS-OPEN**, narrowed to the clean-room re-capture only | `command-center/BASELINE-SNAPSHOT.md:19-31` | almost-certain (90-99%) |
| R-A03 | OPEN, gate OQ-1 + OQ-2 | Input 3 of 3 (release mode) is now **filled**: OQ-3 = PR-ONLY. Inputs 1 and 2 remain owner-only: `OWNER-DECISIONS.md:30-31` shows OQ-1 and OQ-2 both `OPEN`. The *mechanical* obstruction is gone — `OPTION-ID-RESOLUTION.md:12-20` REFUTES F-B-02 as a live blocker (the `M-NN → MECH-NN` re-prefix landed 2026-08-07, 107 substitutions, corroborated by a byte-count of the untouched `.pre-fb02` backup; literal shared-id count today = 0), and `07-OPTION-UNIVERSE.json` carries `owner_decisions: 70` as a ready OQ-1 default | **OWNER-GATED** — not closeable by me. Cheapest owner action: accept the 70 `owner_decisions` as the OQ-1 answer | `command-center/OWNER-DECISIONS.md:30`; `command-center/OPTION-ID-RESOLUTION.md:12-20` | almost-certain (90-99%) |
| R-A05 | OPEN, gate OQ-5 | `OWNER-DECISIONS.md:34` shows OQ-5 (`C22/G-05` vs `I3/D07`) still `OPEN`. Its dependency R-A04 is now resolved, so OQ-5 is no longer *blocked* — it is simply unanswered | **OWNER-GATED** — not closeable by me | `command-center/OWNER-DECISIONS.md:34` | almost-certain (90-99%) |

---

## Detector controls run (so silence counts)

| probe | known-present control | sentinel | verdict |
|---|---|---|---|
| `replay` token grep | fires on `command-center/schema/foundry-artifact.schema.json` and `platform/council/build_protocols.py` | 0 on the 1,093-byte shim `command-center/schema/councilspec.v2.schema.json` | discriminates |
| declared-output-path existence | `platform/schema/receipt.schema.json` → True | `command-center/phase4/contracts/ZZZ.json` → False | discriminates |
| marketplace token census | 11 of 12 tokens non-zero | `zzz_nonexistent_token` → 0 | discriminates |
| `'prompt two'` file grep | 25 files | — | fires |

**Own detector failure, recorded:** my first marketplace census used ERE `revocation\|revoke`, which
matches the *literal* string `revocation|revoke` and returned **0** — while `revoke` is a real CLI
verb at `platform/marketplace/mkt/cli.py:492`. Re-run with true alternation: **448**. A `0` from that
first pass would have produced the exact opposite finding.

---

## Cross-lane notes (no action taken by me)

- `platform/marketplace/PROOF-e2e.json` is **not valid JSON**: a well-formed object followed by a
  bare `SUCCESS:phase6-marketplace-e2e` sentinel on line 209. `json.load` raises `Extra data`. Any
  consumer that parses it will fail. One-line fix (move the sentinel to a field or a sibling file) —
  **PROPOSAL ONLY**, not applied, and not my file.
- `command-center/WORK-UNIT-CATALOG.json` `work_units_meta.known_defects_at_merge` still records
  `dependency_cycles: 1`, `self_dependencies: [IMP-0274, IMP-0277, IMP-0299]`,
  `units_missing_bucket_field: 1735`, `unknown_form_dependency_refs: 41`. Flagged for whoever owns
  catalog integrity; I did not touch the file.
- R-A01's `dependencies: [R-A31]` and R-A11/R-A06/R-A07/R-A08/R-A09's `dependencies: [R-A03]` are all
  **counterfactual** — the gated work shipped without the gate. The dependency edges should be
  retired or re-scoped, or every future reachability check will keep reporting a blocker that
  execution has already walked past.
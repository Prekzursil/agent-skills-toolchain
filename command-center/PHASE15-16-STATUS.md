---
title: PHASE15-16-STATUS
type: note
permalink: dqverify-repo-20261013/command-center/phase15-16-status
---

# LANE C1 — Prompt Two PHASE 15 (release ceremony) + PHASE 16 (self-improvement loop)

**Owner:** lane C1, investigation only. **Output file:** this file, mine alone.
**Mandate:** determine what P15/P16 REQUIRE from the governing spec, measure what exists on disk,
propose dispositions, write a concrete PR-ONLY build plan. Do NOT implement. Do NOT create the
release artifacts. Do NOT edit `WORK-UNIT-CATALOG.json` or anything under
`command-center/receipts/`.

> If it still reads this way, the unit died before investigating anything and no verdict here may be cited.

**COVERAGE (final): COMPLETE.** Spec located and read; all 43 P15/P16 units enumerated; artifact
existence, schema existence, dependency resolution and readiness measured with detector controls on
every probe; the 20 spec deliverables mapped to units mechanically *and* by hand-reading all 31
phase-15 titles; both contracted artifacts read in full; four defects reproduced. Nothing in this
document is scored from a digest. Not measured, and flagged inline where it matters: the semantics
of a `B\d+` bucket dependency (the catalog never defines them — §5), and anything requiring the
`pytest platform` suite (out of scope by constraint).

---

## 0. Governing spec — located and read

The spec is **not in this repo**: it is `~/.claude/harness-restore-20260806/_USER-PROMPTS.md`
(29,273 lines). Every catalog `spec_anchor` of the form `_USER-PROMPTS.md:NNNNN` resolves there.

- **Phase 15 — "Release ceremony"**, `:11100-11133`: **20 required deliverables** (`:11104-11123`),
  a mode line (`:11125`), and **5 promotion gates** (`:11127-11133` — all required gates pass /
  FP-FN telemetry acceptable / canary install-upgrade-rollback succeeds / no data loss /
  independent reviewers sign off).
- **Phase 16 — "Self-improvement loop"**, `:11135-11150`: a **10-step closed loop**, plus the
  retention rule *"No improvement is retained merely because an agent produced it."*

## 1. OQ-3 is genuinely answered — and what it does NOT settle

Two independent signals: `command-center/OWNER-DECISIONS.md:32` (table row, `state=ANSWERED`,
answer `PR-ONLY.`) and `:41-45` (decision-of-record section with provenance = owner statement in
session `30bd50d4`). This **supersedes** `PROGRAM-STOPPING-SCORECARD.json ->
condition_13_reading.the_caveat_that_undercuts_my_own_reading`, which recorded PR-ONLY as an
unrecorded executor assumption. Phase 14 was correct when written; the gap it named is now closed.
Confidence: almost-certain (90-99%).

**But OQ-3 fixes the MODE, not the PASS CONDITION.** Spec `:11125` ("shadow mode or private canary
first") and promotion gate `:11131` ("canary install/upgrade/rollback succeeds") both name a canary
that PR-ONLY does not have. The catalog already anticipated exactly this: `REL-0003` is titled
*"Owner ruling that makes stop condition 13 satisfiable under PR-ONLY"*, carries
`owner_approval_required=true`, and its schema is `owner-decision-packet.schema.json`. OQ-3 does
not supply that ruling. **This is the single most consequential structural fact in this report —
see §7.** Confidence: almost-certain.

Weak corroboration of PR-ONLY, worth recording but not a second source: `RELEASE-CHECKLIST.md:52`
already says "No merge. This lane is PR-only." That is lane-scoped, not program-wide.

## 2. The 43 units — measured

`command-center/WORK-UNIT-CATALOG.json` carries **2,007** units. **Phase 15 = 31 units, Phase 16 =
12 units.**

**Artifact existence: 0 of 43 exist at their declared `output_path`** (`os.path.exists` per unit;
detector control in the same run — a known-present path returns True, a bogus path returns False).

**Schema layer: 16 of 16 referenced schemas EXIST.** This is the one part of P15/P16 that is
genuinely complete: `release-gate-receipt`, `release-gate-report`, `lifecycle-drill-receipt`,
`supply-chain-receipt`, `supply-chain-attestation`, `bundle-scan-receipt`,
`telemetry-threshold-receipt`, `matrix-cell-receipt`, `regression-seed-receipt`,
`license-and-rights-record`, `owner-decision-packet`, `benchmark-integrity`, `benchmark-report`,
`redistribution-adjudication`, `reidentification-assessment`, `receipt` — all present under
`command-center/schema/` (233 files). **Scorecard condition 2(b)'s 18 missing `tools/marketplace/`
schema tokens include none of the 43 P15/P16 units**, so that hole does not block this lane.
Confidence: almost-certain.

**Owner-gated: 9 of 43** carry `owner_approval_required=true` — `REL-0003`, `REL-0012`, `REL-0013`,
`ADV-0048`, `ADV-0055`, `ADV-0142`, `ADV-0143`, `CNF-0126`, `IMP-0373`. Not closeable by any
executor.

## 3. The 20 spec deliverables vs the catalog — 8 have NO owning unit

Mapped two independent ways: (a) regex over `title + question_or_target + output_path +
evidence_requirement` for all 2,007 units, and (b) a hand read of all 31 phase-15 titles. Both
routes agree.

| # | spec deliverable (`:11104-11123`) | owning P15/P16 unit(s) | on disk? |
|---|---|---|---|
| 1 | semantic version | **NONE in P15** (`REL-0001`, `ARC-0092` are phase **4**) | 3 disagreeing records — see §6 |
| 2 | changelog | `REL-0016` (release notes; changelog only implied) | ABSENT |
| 3 | migration guide | `REL-0017` | ABSENT |
| 4 | rollback guide | `REL-0022` (+ `REL-0002` phase 4) | `ROLLBACK-MANIFEST.md` (partial, §8) |
| 5 | signed artifacts | `REL-0012`, `ADV-0055` | ABSENT |
| 6 | provenance attestation | `REL-0012` | `.provenance/` holds only `hooks/` |
| 7 | SBOM | `REL-0011`, `ADV-0058` | ABSENT |
| 8 | license inventory | `REL-0013`, `ADV-0048`, `ADV-0143` | ABSENT (no root `LICENSE`) |
| 9 | vulnerability scan | `REL-0014`, `ADV-0016` | ABSENT |
| 10 | compatibility matrix | `REL-0015`, `ADV-0048` | ABSENT (schema only) |
| 11 | marketplace listing | **NONE in P15** (`ARC-0079` ph4, `ADV-0052` ph12) | `.claude-plugin/marketplace.json` |
| 12 | install/update/uninstall docs | `REL-0005/0007/0008` (drills, not docs) | `release/README.md` only |
| 13 | quick-start examples | **NONE in P15** | ABSENT |
| 14 | advanced workflow examples | **NONE in P15** | ABSENT |
| 15 | security policy | **NONE in P15** (`ADV-0057` ph12 reviews it) | `SECURITY.md` PRESENT |
| 16 | contribution guide | **NONE in P15** | ABSENT |
| 17 | governance guide | **NONE in P15** | ABSENT |
| 18 | support policy | **NONE in P15** (`ADV-0057` ph12) | ABSENT |
| 19 | deprecation policy | `REL-0023`, `ADV-0038` | ABSENT |
| 20 | release notes | `REL-0016` | ABSENT |

**The structural finding: phase 15 was decomposed into *verification and drill receipts*, and
almost entirely omitted *document authorship*.** 29 of the 31 phase-15 units emit a receipt or an
adversarial JSON; not one emits a `.md` deliverable. Deliverables 13-18 (quick-start, advanced
examples, security policy, contribution, governance, support) plus 1 and 11 have **no owning unit
anywhere in phase 15** — 8 of 20. Confidence: almost-certain (two agreeing detection routes).

`ADV-0057` (phase 12) *reviews* the contribution/governance/support policies for legal coherence —
it presupposes documents that no unit is chartered to write. That is a dependency inversion worth
naming.

**Phase 16 coverage is much better:** all 10 loop steps map onto `IMP-0371 -> IMP-0372 -> IMP-0373
-> IMP-0374` plus `TST-0311/0312/0313/0314`, `TST-0236`, `CNF-0127`, `ADV-0088`, `REL-0024`. Only
step 6 ("independently review") has no dedicated P16 unit; it is carried by each unit's
`reviewer_requirement` field instead, which is defensible.

## 4. DEFECT C1-D1 (CONFIRMED) — `RELEASE-CHECKLIST.md` prescribes the wrong bytes

`command-center/RELEASE-CHECKLIST.md:14-15` says to run the ruff gate *"against the **LF blob**
(`git archive`), not the CRLF working tree."* On Windows `git archive` applies export-time EOL
conversion and returns the **opposite** of the blob. Measured on that exact file at HEAD:

| route | bytes | CRLF pairs |
|---|---|---|
| `git archive HEAD <path>` + `tar -x` | 3,220 | **52** |
| `git cat-file -p HEAD:<path>` | 3,168 | 0 |
| `git show HEAD:<path>` | 3,168 | 0 |

LF-normalised all three are byte-identical, so the difference is purely line endings. The 3,168
figure independently matches `ARTIFACT-MANIFEST.json`'s recorded `bytes: 3168` for this artifact —
a second signal that cat-file is the blob and archive is not. **The one checklist step whose whole
purpose is catching a CRLF-vs-LF CI divergence is itself measuring the CRLF form.**
Fix: `git cat-file -p <rev>:<path>`. Confidence: almost-certain (90-99%).

## 5. DEFECT C1-D2 (CONFIRMED) — 6 dangling bucket deps gate 17 of 43 units, and the integrity checker cannot see them

The 43 units use 8 bucket-form dependency tokens. Resolution tried two ways — as a unit id, and as
a `bucket` value with >=1 member:

| token | edges | resolves? |
|---|---|---|
| B02 | 2 | RESOLVES (96 members) |
| B04 | 3 | RESOLVES (32 members) |
| **B01 / B06 / B07 / B08 / B12 / B13** | 1 / 1 / 6 / 5 / 1 / 6 | **DANGLING — 0 members, not a unit id** |

**17 of 43** units are blocked by >=1 dangling token: `ADV-0016 ADV-0038 ADV-0048 ADV-0055
ADV-0058 ADV-0088 ADV-0142 CNF-0126 CNF-0127 IMP-0371 REL-0004 REL-0009 REL-0016 REL-0019 REL-0023
REL-0024 TST-0236`. Detector control: B02/B04/B10 all resolve in the same run, so the six zeroes
are not a broken matcher.

**Highest-leverage instance:** `B07` gates `REL-0004` (the canary/clean-profile rig), and `REL-0004`
gates 6 further REL units. One unresolvable token sits at the root of the drill spine.

**Detector gap:** the catalog's own `work_units_meta.known_defects_at_merge` reports
`unknown_form_dependency_refs: 41` with tokens `["BKT-ARC","BKT-CMD","BKT-IMP","WFA-1of2"]` and
`dangling_unit_id_refs: 0`. It does **not** flag B01/B06/B07/B08/B12/B13 — the checker accepts a
`B\d+` token as well-formed **without checking the bucket has members**, so 20 unsatisfiable edges
pass integrity today. Confidence: almost-certain.

**UNVERIFIED, inline: what a `B\d+` dependency MEANS is nowhere defined.** I searched
`contract`, `defaults` and `tool_policy` — the string "bucket" does not appear in any of them. My
readiness computation in §7 assumes "all members of the bucket must have their artifact"; "any
member" or "a bucket-level gate artifact" are equally consistent with the data. The DANGLING
verdict above is unaffected (0 members satisfies no reading), but the `UNBUILT-BUCKET` counts are
reading-dependent. Settling experiment: locate or author the bucket-dependency semantics in
`contract`, then re-run `_c1_probe_ready.py`.

## 6. DEFECT C1-D3 (CONFIRMED) — three version records, no versioning contract, no release tag

Deliverable 1 is "semantic version". Measured:

- `.claude-plugin/plugin.json` -> `"version": "0.3.0"`
- `package.json` -> `"version": "0.1.0"`
- `platform/plugin/dist/ast-integrate-platform-1.0.0.zip` -> `1.0.0`
- `git tag -l "v*"` -> **empty** (the only tags are `parked-backup-*` and `rescue/*`)

Three artifact classes may legitimately version independently — but the unit chartered to say so,
`ARC-0092` "Contract: Versioning rules: what is breaking, per artifact class" (phase 4), has no
artifact at `command-center/phase4/contracts/ARC-0092.json`. So there is no adjudicating contract,
and no single semantic version a release could cite. Confidence: almost-certain on the four facts;
I deliberately do **not** call this "drift", because per-class versioning may be correct once
`ARC-0092` exists.

**Related, and it corrects a sibling receipt's wording:** the release package is
`platform/plugin/dist/ast-integrate-platform-1.0.0.zip` — I measured **95,093 B / 45 entries**,
matching scorecard condition 6's cited numbers exactly (independent agreement). But the scorecard
describes it as "byte-identical to the **committed** dist zip", and it is **not committed**:
`git ls-files --error-unmatch` fails on it, `git check-ignore -v` names `.gitignore:94
platform/plugin/dist/`, and `git log -- platform/plugin/dist` is empty (no commit ever touched that
path). Ignoring a build output is correct practice — but it means **a PR-ONLY release carries the
builder, not the artifact**, so deliverables 5/6/7 (signature, provenance, SBOM) must attach to a
reviewer-reproducible build, not to a committed blob. I am not re-litigating condition 6's verdict;
only its "committed" wording. Confidence: almost-certain.

The release object itself is real and substantial: `platform/plugin/` ships `cli.py`, `build.py`,
`packager.py`, `lifecycle.py`, `lifecycle_rehearsal.py`, `health.py`, `migrate.py`,
`conformance.py`, `journal.py`, `cache.py`, `deploy.py` plus their tests. **`tools/plugin/`
contains only `schema/`** — anyone looking for the CLI there will wrongly conclude it is missing.

## 7. THE DECISIVE RESULT — exactly 1 of 43 units is startable, and it is the owner-gated one

Readiness computed per unit (a dep is satisfied only if its artifact exists on disk; buckets per the
assumption disclosed in §5). Detector controls: an empty dep list yields READY, a dep on a
known-missing unit yields UNBUILT-UNIT, a dangling bucket yields DANGLING — all three behaved as
expected in the same run.

- **READY today: 1 of 43 -> `REL-0003`.** It is also the *only* unit in either phase with an
  **empty dependency list**, and it carries `owner_approval_required=true`. That verdict is
  assumption-free: an empty dep list is ready under every reading.
- BLOCKED: 42. Edge-state tally across the 43: **20 DANGLING, 52 UNBUILT-UNIT, 5 UNBUILT-BUCKET.**
- **Reading-dependent edge case, disclosed:** 41 of the 42 blocked units carry at least one
  assumption-free blocker (a DANGLING token, which no reading can satisfy, or an UNBUILT-UNIT whose
  artifact simply does not exist). **`REL-0021` is the sole exception** — its only blocker is
  `UNBUILT-BUCKET` (B02), so under a looser bucket reading ("any member" or "a bucket-level gate
  artifact") it could be startable too, making the count 2 rather than 1. Settling experiment: the
  same one as §5 — define bucket semantics in `contract`, then re-run `_c1_probe_ready.py`.
- Transitive closure over unit-form deps: **93 further unbuilt units** across phases 0, 1, 2, 2A, 4,
  10, 11, 12 (largest 2A=34, 11=21, 4=10). P15/P16 is not a leaf.

**So the honest headline is not "Phase 15 is now actionable". It is: OQ-3 unblocked Phase 15's
*definition*, and Phase 15's *only* entry point is `REL-0003` — an owner ruling.** Everything else
is transitively behind it or behind the six dangling buckets. Confidence: almost-certain.

**Second front, unlocked cheaply:** if the six dangling tokens are repaired or retargeted, 6 units
whose *only* blockers are dangling buckets become immediately startable in parallel — `ADV-0038`,
`ADV-0055`, `ADV-0058`, `ADV-0088`, `REL-0009`, `REL-0016`. That is the highest ratio of unlocked
work to effort anywhere in this lane.

## 8. The two contracted artifacts — NOT skeletons, but scoped to a DIFFERENT release object

Both exist, are listed in `ARTIFACT-MANIFEST.json`, and are substantive prose, not placeholders:
`RELEASE-CHECKLIST.md` = 52 lines / 3,168 B blob; `ROLLBACK-MANIFEST.md` = 46 lines / 3,057 B.
**Neither is about the Phase 15 production release.** Their subject is the command center itself
plus the `register_gate` harness module:

- `RELEASE-CHECKLIST.md:6` — "Releasing a change to the command center itself"
- `RELEASE-CHECKLIST.md:20` — "Promoting the `register_gate` up the ladder" (off -> shadow -> advise)
- `ROLLBACK-MANIFEST.md:6` — "The register gate"; `:41` — "Rollback of this PR as a whole"

Scored against the 20 spec deliverables, `RELEASE-CHECKLIST.md` covers **0**: no semantic version,
changelog, migration guide, SBOM, license inventory, provenance, signature, compatibility matrix,
marketplace listing, quick-start, governance, support or deprecation section. It is a correct and
useful artifact for the object it names and a **category mismatch** for Phase 15 — so the answer to
"skeleton or satisfies the phase?" is *neither*.

`ROLLBACK-MANIFEST.md` partly transfers. Its §3 "What has no rollback, stated plainly" is exactly
the honesty a Phase-15 rollback guide needs, and it is the documented procedure cited by condition
14. Its §1/§2 (register gate, catalog) are out of scope for a plugin release; a Phase-15 rollback
guide must add the *package* verbs (`platform/plugin/lifecycle.py`) and the two gaps condition 14
names.

## 9. Condition 14 — cited, not re-litigated

Condition 14 ("rollback is tested") is **TRUE**, one of only two. Scope per the scorecard: the
plugin package's rollback verb, exercised through the shipped CLI by an independent lane
(`command-center/WAVE4-PLUGIN-LIFECYCLE-VERIFY.{json,md}`), read on disk and not re-executed by
Phase 14; `ROLLBACK-MANIFEST.md` is the documented procedure. Explicitly NOT covered: a `git
revert` rehearsal of the D1 registry/schema data change, and rollback from the hard-kill
partial-install state that leaves a blocking lock (condition 6). **I re-measured none of this and
make no new claim about it.** My only adjacent finding is the "committed dist zip" wording in §6.

---

## 10. PROPOSALS

| id | current state | what I MEASURED | proposed disposition | evidence anchor | confidence |
|----|---------------|-----------------|----------------------|-----------------|------------|
| P15-spec-locate | unlocated in-repo | Spec is out-of-repo; P15 = 20 deliverables + 5 promotion gates; P16 = 10-step loop | **CLOSE** — located, read, line ranges recorded | `~/.claude/harness-restore-20260806/_USER-PROMPTS.md:11100-11133`, `:11135-11150` | almost-certain |
| P15-oq3-pronly | scorecard called it an unrecorded assumption | `OWNER-DECISIONS.md:32` `state=ANSWERED`; `:41-45` decision-of-record with provenance | **CLOSE** — supersedes `condition_13_reading.the_caveat_that_undercuts_my_own_reading` | `command-center/OWNER-DECISIONS.md:32,41-45` | almost-certain |
| P15-oq3-residual | newly surfaced here | OQ-3 fixes the mode, not the pass condition for `:11125`/`:11131`; `REL-0003` exists to rule on it, `owner_approval_required=true`, no receipt | **OWNER-GATED** — I stop. The substitute pass condition is an owner ruling, not an executor choice | catalog `REL-0003`; `_USER-PROMPTS.md:11125,11131` | almost-certain |
| P15-schema-layer | unknown before this lane | 16 of 16 referenced schemas exist; none of condition 2(b)'s 18 missing marketplace schemas are P15/P16 | **CLOSE** — schema layer complete, not a blocker | `command-center/schema/` (233 files); `_c1_probe_schemas.py` | almost-certain |
| P15-cond14 | scorecard TRUE | not re-measured, by design | **CLOSE (cite only)** — stays TRUE at its stated narrow scope | `PROGRAM-STOPPING-SCORECARD.json` cond 14; `WAVE4-PLUGIN-LIFECYCLE-VERIFY.md` | inherited |
| P15-release-checklist | contracted artifact, exists | 52 lines, substantive; subject = command center + `register_gate`; covers 0 of the 20 deliverables | **STAYS-OPEN** — not a skeleton, a category mismatch. Needs a NEW P15 checklist; do not overwrite this one | `command-center/RELEASE-CHECKLIST.md:6,20,52` | almost-certain |
| P15-checklist-defect | live defect in that artifact | `git archive` 3,220 B / 52 CRLF vs `git cat-file -p` 3,168 B / 0 CRLF; 3,168 matches the manifest | **STAYS-OPEN** — one-line fix (`git cat-file -p`); the file is contracted, so the edit belongs to its owner | `command-center/RELEASE-CHECKLIST.md:14-15`; `ARTIFACT-MANIFEST.json` bytes=3168 | almost-certain |
| P15-rollback-manifest | contracted artifact, exists | 46 lines, substantive; §3 is P15-grade; §1/§2 scoped to gate+catalog, not the package | **STAYS-OPEN** — partially transferable; P15 guide must add package verbs + condition 14's two gaps | `command-center/ROLLBACK-MANIFEST.md:6,34-39,41` | almost-certain |
| P15-units-exist | 31 units contracted | 0 of 31 artifacts exist at `output_path`; control passed | **STAYS-OPEN** | `_c1_probe_p15_units.py` | almost-certain |
| P15-deliverable-map | unmeasured before | 8 of 20 deliverables have NO owning P15 unit (1, 11, 13-18); 29 of 31 units emit receipts, none emits a `.md` | **STAYS-OPEN** — the catalog under-decomposes Phase 15. Needs new units (orchestrator owns the write) or an owner waiver | `_c1_probe_delivmap.py`; hand read of 31 titles | almost-certain |
| P15-dangling-buckets | not flagged by catalog integrity | B01/B06/B07/B08/B12/B13 = 0 members, not unit ids; 20 edges; 17 of 43 blocked; control on B02/B04/B10 passed | **STAYS-OPEN** — hard structural blocker **and** a detector gap in the integrity checker | `_c1_probe_dangling.py`; `work_units_meta.known_defects_at_merge` | almost-certain |
| P15-bucket-semantics | never specified | "bucket" appears nowhere in `contract`/`defaults`/`tool_policy` | **STAYS-OPEN** — the dependency language is under-specified; my readiness math depends on the reading | catalog `contract` keys; §5 UNVERIFIED note | almost-certain |
| P15-graph-coverage | assumed usable | `DEPENDENCY-GRAPH.json` `node_count=103`, prefixes R:69 T:26 S:5 D:3, zero `REL-*`/`B\d+` nodes | **STAYS-OPEN** — P15 readiness/critical path cannot be computed from the graph | `command-center/DEPENDENCY-GRAPH.json`; `work_units_meta.pre_merge_items=103` | almost-certain |
| P15-version-record | deliverable 1 | plugin.json 0.3.0 / package.json 0.1.0 / dist zip 1.0.0 / no `v*` tag; `ARC-0092` (the adjudicating contract) has no artifact | **STAYS-OPEN** — blocked on `ARC-0092` (phase 4), not resolvable inside P15 | `.claude-plugin/plugin.json`, `package.json`, `platform/plugin/dist/`, `git tag -l "v*"` | almost-certain |
| P15-artifact-not-committed | corrects a sibling's wording | zip = 95,093 B / 45 entries (matches cond 6) but untracked; `.gitignore:94`; `git log -- platform/plugin/dist` empty | **STAYS-OPEN** — cond 6's "committed dist zip" wording is wrong; PR carries the builder, not the artifact | `.gitignore:94`; `git ls-files --error-unmatch` failure | almost-certain |
| P15-readiness | unmeasured before | 1 of 43 READY (`REL-0003`, the owner-gated root); 20 DANGLING / 52 UNBUILT-UNIT / 5 UNBUILT-BUCKET edges; 93-unit upstream closure | **STAYS-OPEN** — and it is the finding that orders the whole plan | `_c1_probe_ready.py` (3 controls passed) | almost-certain |
| P16-units-exist | 12 units contracted | 0 of 12 artifacts exist | **STAYS-OPEN** | `_c1_probe_p15_units.py` | almost-certain |
| P16-loop-map | unmeasured before | all 10 spec steps map onto P16 units; only step 6 lacks a dedicated unit (carried by `reviewer_requirement`) | **CLOSE (mapping only)** — the P16 decomposition is adequate; the units are unbuilt (see above) | `_c1_probe_delivmap.py` | likely (55-80%) — regex recall on step 6 |
| P16-serial-chain | unmeasured before | `IMP-0371 -> 0372 -> 0373 -> 0374` is a strict serial chain; `IMP-0373` is owner-gated | **STAYS-OPEN** — P16 cannot be parallelised; plan for 4 sequential units | catalog dependencies of `IMP-0371..0374` | almost-certain |

---

## 11. BUILD PLAN — PR-ONLY branch only

**Scope discipline, stated first.** Built: the PR-ONLY path. **NOT built, by owner decision
(OQ-3):** any private-canary deployment path, any marketplace-publish path. No credential is
rotated (AGENTS.md §9). No merge, no push, no branch created by this lane. Where the spec names a
canary (`:11125`, `:11131`), the plan routes to `REL-0003` for a substitute rather than inventing
one.

### Stage 0 — Repairs that unblock, cheap and structural (no owner needed)

Nothing in Stage 0 needs a decision; all four are mechanical, and together they move the startable
set from 1 unit to 7.

1. **Resolve or retarget the 6 dangling bucket tokens** B01/B06/B07/B08/B12/B13 across 20 edges.
   Deliverable: a decision per token — either the bucket gains members, or the 17 affected units'
   `dependencies` are retargeted to real unit ids. *Catalog write; the orchestrator owns it — this
   lane proposes only.* Unblocks `ADV-0038 ADV-0055 ADV-0058 ADV-0088 REL-0009 REL-0016` immediately.
2. **Define bucket-dependency semantics in `contract`** (§5's UNVERIFIED). Without it, "ready" is
   not computable, which is why the plan below is ordered by measured blockers rather than by
   phase-15 unit number.
3. **Extend the catalog integrity checker** so a `B\d+` token with zero members fails, alongside
   the existing `unknown_form_dependency_tokens` check. Both-states control: it must fire on B07
   today and go silent after step 1. Without this the defect silently returns.
4. **Fix `RELEASE-CHECKLIST.md:14-15`** to `git cat-file -p <rev>:<path>` (§4).

### Stage 1 — The owner gate (the only true entry point)

5. **Author the `REL-0003` owner-decision packet** against
   `command-center/schema/owner-decision-packet.schema.json` and hand it to the owner. It must ask
   exactly three things and nothing else:
   - (a) Under PR-ONLY, what **replaces** `:11131` "canary install/upgrade/rollback succeeds"?
     Recommended option to put in front of the owner: a **clean-profile local rig** (the
     `REL-0004` design) run against the built package outside the repo, with the pass condition
     being an observed hook firing — not a file landing.
   - (b) Is `:11125` ("shadow mode or private canary first") satisfied by the existing shadow-mode
     ladder (`RELEASE-CHECKLIST.md:26-33`), or waived under PR-ONLY?
   - (c) Deliverable 11 "marketplace listing": is authoring/refreshing
     `.claude-plugin/marketplace.json` **in** scope as a listing *document*, given that
     marketplace *publishing* is out of scope? These are separable and the spec names the listing.
   *Artifact path is `command-center/receipts/REL-0003.json` — forbidden to this lane. Deliver the
   packet content, let the owning lane write it.*

### Stage 2 — Phase-4 contracts P15 rests on (parallel, 4 units)

6. `ARC-0092` versioning-rules contract -> settles §6's three version records.
   `REL-0001` semver bump linter. `REL-0002` rollback contract (typed inverse per mutating action) —
   already a dependency of `REL-0006/0017/0022`. `ARC-0079` marketplace manifest contract — only if
   Stage 1(c) says listing is in scope.

### Stage 3 — The drill spine (serial; `REL-0004` is the root)

7. `REL-0004` clean-profile rig (needs Stage 0.1 for B07 + Stage 1(a) for its pass condition), then
   in dependency order: `REL-0005` upgrade N-1->N -> `REL-0006` downgrade + MTTR -> `REL-0007`
   orphan sweep -> `REL-0008` destruction oracle (hostile filenames) -> `REL-0020` cache
   invalidation from the poisoned state -> `REL-0022` rollback coverage by instrumenting a real
   install -> `REL-0015` support matrix cell-by-cell with unrun cells as NOT-CHECKED.
   Target: `platform/plugin/` CLI + a temp prefix outside the repo. **Re-use, do not rebuild** — the
   sibling lane already drove these verbs (`WAVE4-PLUGIN-LIFECYCLE-VERIFY`); the new work is the
   *typed receipts* and the two PARTIAL arms condition 6 names (hard-kill lock; health-check
   integrity vs existence).

### Stage 4 — Supply chain (mostly parallel once `REL-0009`/`REL-0011` land)

8. `REL-0009` distributable allowlist + byte ceiling from the archive entry list (45 entries /
   95,093 B measured — use those as the baseline) -> `REL-0010` credential scan of the extracted
   bundle with a planted canary, read-only. `REL-0011` SBOM emitted then falsified against an
   independently resolved closure -> `REL-0012` provenance attestation + signature **or a declared
   UNSIGNED gap** (owner-gated), `REL-0013` licence inventory with riders as their own blocking
   class (owner-gated), `REL-0014` advisory re-scan with an enforced freshness window. Adversarial
   siblings in parallel: `ADV-0058` planted transitive, `ADV-0016` scanner freshness, `ADV-0048`
   licence+compat, `ADV-0055` export-control, `ADV-0038` revocation propagation to caches.
   **Because the zip is gitignored (§6), every one of these must attach to a reproducible build,
   not to a committed blob** — state the build command in each receipt.

### Stage 5 — The 8 unowned deliverables (needs a catalog change first)

9. Deliverables 1, 11, 13, 14, 15, 16, 17, 18 have no owning unit (§3). **Do not write them
   ad hoc** — that is exactly how an artifact lands with no sentinel, no schema and no reviewer.
   Propose 6 new phase-15 document units (quick-start, advanced workflow examples, security policy,
   contribution guide, governance guide, support policy) each with an `output_path`, a schema or an
   explicit prose exemption, and a reviewer; deliverable 1 routes to `ARC-0092` (Stage 2) and
   deliverable 11 to Stage 1(c). Note `SECURITY.md` already exists (2,355 B) so deliverable 15 is a
   *review-and-adopt*, not an authoring task. `ADV-0057` (phase 12) reviews three of these
   documents and must be sequenced **after** they exist.

### Stage 6 — The gate, computed not asserted

10. `REL-0019` numeric misfire budgets on labelled fixtures (satisfies `:11130`), `TST-0301`
    material regression as a number, `TST-0324` condition 8 from the ledger, then **`REL-0018`
    promotion decision as executable code over the 21 stopping conditions** (deps: REL-0003, 0006,
    0008, 0014, 0019 — the true convergence point), then `CNF-0126` release-gate confirmation
    recomputed from receipts under PR-ONLY (owner-gated). `REL-0021` three-way byte parity (git blob
    / packaged / deployed) should use `git cat-file -p`, per §4, or it will reproduce C1-D1.
    Promotion gate `:11133` "independent reviewers sign off" is satisfied by each unit's
    `reviewer_requirement`, not by a new unit — but note scorecard condition 20 shows the Phase-14
    synthesis itself is un-meta-reviewed, so an independent second synthesis is owed before any
    promotion claim.

### Stage 7 — Phase 16 (strictly serial, do not parallelise)

11. `IMP-0371` candidate intake + baseline reproduction -> `IMP-0372` isolated implementation with a
    measured benefit gate -> `IMP-0373` automatic revert + retention ledger (**owner-gated**) ->
    `IMP-0374` lesson writeback + benchmark augmentation. Then, in parallel: `TST-0311` prove the
    gate can say no, `TST-0312` prove the revert restores the measured baseline, `TST-0313` every
    closed defect leaves a regression case, `TST-0314` meta-benchmark the loop, `TST-0236`
    end-to-end keep-only-measured-wins, `CNF-0127` retention re-measurement by a fresh agent,
    `ADV-0088` measure-weakening attack, `REL-0024` every ceremony defect becomes a permanent test
    proved red on the pre-fix commit.
12. **`REL-0024` is where Stage 0's four repairs must land as tests**, each proved red at the
    pre-fix commit — otherwise C1-D1 through C1-D3 return silently.

### What this plan does NOT claim

It does not claim Phase 15 can be completed without the owner: 9 of 43 units are owner-gated and
the single entry point is one of them. It does not claim the 43 units are the whole of Phase 15 —
§3 shows 8 of 20 spec deliverables are unowned, so the catalog is an under-count. It does not
estimate durations; the 93-unit upstream closure means any P15 schedule is dominated by phases 0-12,
not by phase 15.

---

## 12. Probes written by this lane (read-only, reproducible)

- `command-center/_c1_probe_phase1516.py` — catalog shape, phase histogram, release-related units.
- `command-center/_c1_probe_p15_units.py` — the 43 units, `output_path` existence.
- `command-center/_c1_probe_schemas.py` — schema existence, all REL units, dependency census.
- `command-center/_c1_probe_dangling.py` — bucket-dep resolution, with detector control.
- `command-center/_c1_probe_delivmap.py` — 20 P15 deliverables + 10 P16 steps mapped to units;
  on-disk probe with control.
- `command-center/_c1_probe_ready.py` — readiness/entry-point computation, with 3 controls.

None writes to `WORK-UNIT-CATALOG.json`, `command-center/receipts/**`, `platform/routing/**`,
`tools/measure-guard/**` or `.github/workflows/**`. No commit, no push, no branch.
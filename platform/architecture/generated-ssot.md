---
title: generated-ssot
type: note
permalink: dqverify-repo-20261013/platform/architecture/generated-ssot
---

# Architecture Candidate: Generated Single-Source-of-Truth

> **Does this architecture discard Wave 1? No — it deletes zero Wave-1 artifacts.** All 8 compiling
> schemas, all 3 lib packages plus 3 loose validator modules, all 48 protocols, all 69 presets, all
> 161 registry candidates and all 2,007 catalogued units are RETAINED. The 8 schemas are *promoted*
> from checkers to the emitter's type system; the 117 councilspecs keep their bytes and gain a
> provenance stamp and a drift gate; `platform/lib/_gen_schema_substrate.py` and
> `tools/command-center/render.py` are reused **unmodified as emitters**. The only files this
> architecture removes are **4 of the 6 redundant council generator scripts** already in the tree.
> Full counts in §8.

- Unit: `tournament/generated-ssot` · candidate `A2` in `13-ARCHITECTURE-CANDIDATES.md:216-302`
- Repo: `C:/Users/Prekzursil/source/ast-integrate`
- Measured at: `833fb1ea0886a87a562be539a02839f8c6e6a6e4` (HEAD). **The brief pinned `dc90d64a`,
  which is 2 commits behind HEAD** (`36070a6f` "repair main - lint, format and command-center render
  drift", `833fb1ea` "stop tracking agent probe scripts"). Every number below was measured at
  `833fb1ea`; where that matters I say so.
- Probes (all read-only, all re-runnable):
  `platform/architecture/_probe_ssot_inventory.py` ·
  `_probe_ssot_derivability.py` (**carries a disclosed detector defect — see §1.4**) ·
  `_probe_ssot_detector_reconcile.py` · `_probe_ssot_defect_clustering.py` ·
  `_probe_ssot_roundtrip.py` · `_probe_ssot_contract_layer.py` ·
  `_probe_ssot_existing_generators.py` ·
  `_probe_ssot_doc_selfcheck.py` (recomputes every DERIVED figure quoted here; it caught two
  arithmetic errors in this document's first draft — a generator-count denominator and a loc total)
- Coverage of this file: §0-§9 all MEASURED. Two items are explicitly NOT-CHECKED and named inline
  (CI wall-time of the emit+verify step, §2.3; and the strict-profile attribution of the 217
  `unevaluatedProperties` failures to specific slices, §1.2).

---

## 0. The thesis in one paragraph, and the concession it comes with

**Generated-SSOT is not a proposal in this repo. It is a description of what this repo already
does in 41 places and only verifies in 4.** Measured: **41 generator scripts** are committed and
write committed artifacts. Of those 41, **5 are the generators' own test files, leaving 36
production emitters — and exactly 4 of the 36 have a drift gate**, so **32 production emitters
emit committed artifacts with nothing checking them** (`_probe_ssot_existing_generators_out.json`,
`_probe_ssot_doc_selfcheck.py`). I verified the gated four are actually *invoked* by CI, not merely
capable of it — a `--check` flag no workflow calls is not a gate:

| gated emitter | CI invocation |
|---|---|
| `ci/emit_hook_manifest.py` | `.github/workflows/quality.yml:624` and `:625` (`--check`, twice) |
| `tools/command-center/render.py` | `.github/workflows/quality.yml:403` (`--check`) |
| `ci/gen_skill_index.py` | `.github/workflows/skill-dual-write.yml:72` (`--check --fail-on-drift`) |
| `ci/gen_skills_manifest.py` | `.github/workflows/skill-dual-write.yml:79` (`--check`) |

The architecture is therefore not "adopt generation";
it is **"collapse 41 ad-hoc emitters onto one emitter contract with one universal verifier, and
name exactly one writer per artifact path."**

The concession, stated up front because §7 will not let me hide it: **I ran this candidate's own
decisive test and it failed for the largest artifact.** `13-ARCHITECTURE-CANDIDATES.md:281-282`
says *"if round-trip is not byte-exact, the spec is lossy and migration stops."* Measured
round-trip on `WORK-UNIT-CATALOG.json` under a one-template-per-slice generator: **5.18%
byte-exact** (`_probe_ssot_roundtrip_out.json` → `generator_owned_fraction: 0.0518`). So this
architecture **wins on the 348-file generated surface and loses on the 2,007-unit catalog**, and
§5 phases it accordingly. A scoped win beats an overclaimed sweep.

---

## 1. Design

### 1.1 What is actually on disk (the substrate this design must fit)

| plane | measured content | provenance stamp | drift gate |
|---|---|---|---|
| `platform/schema/` | 14 top-level files: **8** compiling `*.schema.json` + 6 status/validation records; 32 tracked paths incl. `examples/` | n/a (authored) | partial (`CONFORMANCE-STATUS.json` is a record, not a gate) |
| `platform/lib/` | 3 packages — `wfdsl` 12 py/3,094 loc, `councilspec` 10 py/2,529 loc, `council_protocols` 7 py/5,174 loc — plus `completion_predicate.py` 1,301 loc, `receipt_schema_gate.py` 732 loc, `schema_resolver.py` 322 loc | n/a | tests only |
| `platform/council/` | **117** `*.councilspec.json` (48 protocols + 69 presets), 1,455,723 B, 5 distinct top-level keysets, modal keyset covers 73/117 | **ZERO provenance keys on all 117** | **none** |
| `platform/registry/` | 161 classified candidates | — | — |
| `command-center/WORK-UNIT-CATALOG.json` | 5,343,710 B; `work_units[]` = **2,007**; separate `items[]` = **103**; 27 distinct unit fields | — | `wfdsl` profiles (record only) |
| `command-center/schema/` | **233** JSON, 262,248 B, **231 carry `x-generated-by: platform/lib/_gen_schema_substrate.py`** | **yes, 231/233** | none, and **all 233 are UNTRACKED** |

Two of those rows are the whole argument.

**Row `platform/council`.** Those 117 files were **machine-emitted**. Six scripts sit in that
tree and five of them write `.councilspec.json` via `json.dump`/`write_text`:
`_build_p01_p12.py`, `_gen_protocols_37_48.py`, `_gen_skeletons.py`, `build_protocols.py`,
`presets/_lane2_emit.py` (the sixth, `_lane1_emit_trees.py`, `json.dump`s something else).
Yet the 117 artifacts carry **zero** provenance keys and there is **no `--check` gate**. So this
repo has already built the generated-SSOT pattern for its single largest Wave-1 artifact set and
left the loop open: five competing writers, no declared owner, no way to tell a generated file
from a hand-edited one. That is not a hypothetical risk — it is the measured state.

**Row `command-center/schema`.** 231 of 233 files already declare their generator in-band, and
each shim's `$comment` names the edit target (*"Do not add rules here: edit
`platform/schema/artifact-class-profiles.schema.json` … and re-run
`platform/lib/_gen_schema_substrate.py`"*). That is a correctly-built emitter. Its one gap is that
**all 233 files are untracked** (`git status --porcelain -uall command-center/schema` → 233; `git
ls-files command-center/schema` → 0), so no byte-comparison gate can run against them yet.

### 1.2 Where the defects are — the load-bearing measurement

I re-derived every catalog defect with my own code, independent of `platform/lib/wfdsl`, then
reconciled against the repo's own recorded histogram in
`platform/schema/WORKFLOW-DSL-VALIDATION.json`.

| defect | my independent count | repo-recorded | verdict |
|---|---|---|---|
| `output_schema` is a compound/prose value, not a single ref | **159** | `output_schema [not]` = 159, `[pattern]` = 159; and `SUBSTRATE-RESOLUTION-STATUS.json` → `path_plus_prose_annotation_refs: 159` | **CONFIRMED, three independent signals** |
| `output_schema` is `path#fragment` | **287** | `path_plus_json_pointer_refs: 287` | **CONFIRMED** |
| distinct `output_schema` paths after stripping the fragment | **305** | `strip_fragment_only: "305 / 2007"` | **CONFIRMED** |
| normalized distinct schema files that resolve | **234** | `normalized_distinct_SCHEMA_FILES: 234` | **CONFIRMED** |
| `assigned_model_vendor_role` is a bare string, not the `{vendor,model,role}` object | **128** | `assigned_model_vendor_role [type]` = 128 | **CONFIRMED** |
| `tests_required` is a string, not an array | **96** | `tests_required [type]` = 96 | **CONFIRMED** |
| `failure_classification` is a string, not an array | **96** | `failure_classification [type]` = 96 | **CONFIRMED** |
| dependency entry is a bare family prefix (`ARC` 19, `WFA` 17, `CC` 4, `IMP` 1) | **41 occurrences across 40 units** | `dependencies/0 [pattern]` 20 + `dependencies/1 [pattern]` 21 = **41** | **CONFIRMED, exact derivation** |
| "96 completion sentinels that do not name their own unit" (brief's wording) | **0 of 2,007.** 1,367 are exactly `SUCCESS:<id>`; 640 are verbose but still contain their own id; **none omits it** | `completion_sentinel [pattern]` = 96 | **the brief's PHRASING is REFUTED.** The recorded 96 is a *format-pattern* failure, not a naming failure. My detector fires on a synthetic bad unit (`detector_fires_on_synthetic_bad: true`), so the zero is a real zero, not a dead probe |

Profile totals, quoted from the repo's own record: structural **2007/2007**, normative **1790**
pass / 217 fail, strict **1679** pass / 328 fail, `strict_only_count: 111`,
`cascade_from_normative: 217`. The normative histogram sums to 159 + 41 + 18 = 218 against 217
distinct failing units, so at least one unit fails two categories — **the per-slice attribution of
the 217 `<root> [unevaluatedProperties]` strict failures is NOT-CHECKED**; the settling probe is
`cd platform/lib && python -m wfdsl --catalog-profile strict --emit-failing-ids` joined on
`_source_slice_file`.

Now the finding that decides this architecture. Grouping every defect by the authoring provenance
field `_source_slice_file` (22 slices, `_probe_ssot_defect_clustering_out.json`):

| defect | units hit | slices containing a hit | worst slice | hit rate **inside** that slice |
|---|---|---|---|---|
| `vendor_role_is_string` | 128 | **2 of 22** | `IMP-4.json` 96 · `WFA-2.json` 32 | **96/96 = 1.000** |
| `tests_required_is_string` | 96 | **1 of 22** | `IMP-4.json` | **96/96 = 1.000** |
| `failure_classification_is_string` | 96 | **1 of 22** | `IMP-4.json` | **96/96 = 1.000** |
| `output_schema_is_prose_compound` | 159 | **2 of 22** | `IMP-3.json` 118 · `IMP-1.json` 41 | **118/118 = 1.000** |
| `dependency_is_bare_family_prefix` | 40 | **2 of 22** | `TST-1.json` 23 · `WFA-2.json` 17 | 23/128 = 0.180 |
| `sentinel_not_exact_SUCCESS:<id>` | 640 | 7 of 22 | `ADV-1` 128 · `CNF-1` 128 · `RES-1` 128 · `AUD-1` 96 · `IMP-4` 96 · `SYN-1` 48 · `ADV-2` 16 | **1.000 in every one of the 7** |

**Five of six defect classes have a within-slice hit rate of exactly 1.000, and the three `type`
defects hit the same units**: `tests_required_str == failure_classification_str` (identical
96-unit set) and all 96 ⊂ the 128 `vendor_role_str` units (union 128). **The defect is a property
of who authored the slice, not of what the unit does.** A field that is wrong for 96 of 96 units
in one slice and 0 of 1,911 elsewhere was not a per-unit decision — it was one convention chosen
once and never reconciled. **Five slices — `IMP-1`, `IMP-3`, `IMP-4`, `TST-1`, `WFA-2` — carry
every one of the six measured defect classes.**

That is the exact class of defect a single emitter removes by construction, because there is only
one place the convention can be chosen.

### 1.3 The design

Three authored planes, four emitters, one verifier, one writer per path.

**AUTHORED (the only hand-edited files):**

1. **`platform/spec/unit-content.jsonl`** — 2,007 records carrying `id` plus the 7 CONTENT fields
   (`question_or_target`, `evidence_requirement`, `tests_required`, `inputs`, `title`, `mechanism`,
   `not_a_duplicate_because`). Measured at **2,265,388 B = 58.07%** of catalog field bytes. This is
   irreducible; the generator carries it verbatim and never rewrites it.
2. **`platform/spec/contract-policy.yaml`** — the CONTRACT vocabulary, keyed on
   `(phase, family, artifact_class, risk_tier)`: `retry_policy`, `reviewer_requirement`,
   `tool_permissions`, `timeout_seconds`, `execution_substrate`, `owner_approval_required`,
   `assigned_model_vendor_role`, `failure_classification`, plus the *derivation rules* for
   `output_path`, `completion_sentinel` and `output_schema`. Measured target: **1,532,770 B =
   39.29%** of catalog field bytes.
3. **`platform/spec/overrides.yaml`** — every measured exception, explicit and reviewable, each
   with a mandatory `why`. Measured size of this file is the architecture's real cost: **13,032
   overrides across 22,077 contract-field instances = a 59.03% override rate**
   (`_probe_ssot_contract_layer_out.json`). §7 is about that number.

**EMITTERS (pure, stdlib-only, deterministic, no network):**

| emitter | status | owns |
|---|---|---|
| `platform/lib/_gen_schema_substrate.py` | **EXISTS — reused unmodified** | `command-center/schema/**` (231 shims) |
| `tools/command-center/render.py` | **EXISTS — reused unmodified** (already has `--check`, already gated at `quality.yml:403`) | `command-center/STATUS.md`, `OWNER-DECISIONS.md`, `ARTIFACT-MANIFEST.json` |
| `platform/lib/ssot/emit_councilspecs.py` | **NEW** — replaces 4 of the 5 competing council writers | `platform/council/**/*.councilspec.json` (117) |
| `platform/lib/ssot/emit_catalog.py` | **NEW, and deliberately NOT enabled in Phase 1** (§5) | `command-center/WORK-UNIT-CATALOG.json` |

**VERIFIER — `platform/lib/ssot/verify.py --check`:** emit every artifact to a temp tree,
byte-compare against the committed tree, non-zero exit on any difference. It **never writes to the
repo**. `--apply` exists, is local-only, and refuses to run unless `--check` has printed the diff
first. This is the direct answer to the historical `install.py:146` defect
(`13-ARCHITECTURE-CANDIDATES.md:105` — replacing a whole config key silently dropped 21
registrations including both security guards): an emitter that can only ever be compared, never
blind-applied in CI, cannot commit that failure.

**CONTROL-PLANE SINGULARITY — `platform/spec/EMISSION-MAP.json`:** a total function from artifact
path → owning emitter. Two emitters claiming one path is a build error. The spec's own tournament
rule is that *"the winner may be a hybrid only when its control planes remain singular and
understandable"* (`_USER-PROMPTS.md:10796`); this file is that property made mechanical, and it is
precisely what `platform/council/` lacks today with its five writers for one artifact set.

**The Wave-1 schemas become the type system, not a side-check.** `work-unit.strict.schema.json` is
the emitter's *postcondition*: the build fails unless emitted output validates at the strict
profile, i.e. **2007/2007, up from the measured 1679/2007**. The schemas were authored before the
emitter and by a different unit, so they are an *independent* oracle — which matters, because a
generator that is its own oracle verifies nothing (§3, failure mode 3).

### 1.4 A detector defect in my own probes, disclosed

`_probe_ssot_derivability.py` reported `phase`, `bucket` and `execution_substrate` as "fully
determined by a small key". **That is wrong and I am flagging it rather than quietly dropping it.**
Its key set included `phase+id_prefix+substrate`, which *contains* the target field for those three
— a self-referencing key makes any field trivially determined. `_probe_ssot_contract_layer.py`
re-measures with self-reference removed; `execution_substrate` drops to **best purity 0.543**, not
1.0. Every derivability number quoted in this document comes from the corrected probe. The
uncorrected probe output is left on disk with this note attached so the error is auditable.

---

## 2. Cost and complexity analysis

### 2.1 New code

| item | estimate | basis |
|---|---|---|
| `verify.py` | ~150 loc | byte-compare + temp-tree emit; `tools/command-center/render.py --check` is the existing pattern to copy |
| `emit_councilspecs.py` | ~250 loc | replaces 5 scripts whose combined function is already written |
| `emit_catalog.py` | ~400 loc | Phase 3 only; not built in Phase 1 |
| `EMISSION-MAP.json` | ~350 lines | 348 artifact paths + owner |
| tests | ~600 loc | the T1-T7 battery in §6 |

Total ≈ **1,750 loc** against the Wave-1 `platform/lib` baseline of **10,797 loc across the 3
packages (29 py files) + 2,355 loc in the 3 loose validators = 13,152 loc → 13.3% growth**
(`_probe_ssot_doc_selfcheck.py`). That is the honest code cost and it is not the expensive part.

**Denominator caveat, measured mid-unit and worth recording.** That baseline is a *timestamped*
figure, not an invariant: between this probe's first and second run a concurrent sibling grew
`wfdsl` from 12 py/3,094 loc to 14 py/3,200 loc and added a whole new package
`platform/lib/workflows` (21 py / 16,405 loc). `platform/lib` currently shows 50 tracked and 31
untracked paths. So the self-check asserts a *band* (0.12-0.14) and reports the drift, rather than
pinning an equality that a peer's legitimate work falsifies — the same reason §6's invariants are
pinned counts of *emitted* artifacts rather than of the whole tree.

### 2.2 The expensive part is the spec, and I measured it

A generator is only cheap if the policy plane is small. Measured, it is not:

| field (CONTRACT layer) | bytes | distinct values | best non-circular key | best purity | units needing an override |
|---|---|---|---|---|---|
| `retry_policy` | 334,639 | 276 | `slice` | 0.624 | 755 |
| `reviewer_requirement` | 294,533 | 497 | `slice` | 0.433 | 1,138 |
| `completion_sentinel` | 180,783 | 2,007 | `phase+family` | 0.026 (0.544 **with `{id}` templating**) | 1,955 (915 with templating) |
| `assigned_model_vendor_role` | 176,638 | 529 | `phase+family` | 0.308 | 1,389 |
| `failure_classification` | 131,191 | 934 | `phase+family` | 0.180 | 1,645 |
| `tool_permissions` | 130,972 | 151 | `slice` | 0.532 | 939 |
| `output_schema` | 127,841 | 367 | `slice` | 0.412 | 1,181 |
| `output_path` | 104,202 | 2,007 | `phase+family` | 0.026 (0.421 **with templating**) | 1,955 (1,162 with templating) |
| `execution_substrate` | 34,004 | 4 | `phase+family` | 0.543 | 918 |
| `owner_approval_required` | 9,891 | 2 | `phase+family` | 0.930 | 140 |
| `timeout_seconds` | 8,076 | 12 | `slice` | 0.493 | 1,017 |

**No contract field is exactly determined by any of the five keys tried** (`exact_key: None` for
all 11). Byte-weighted best purity = **0.3756**; adding `{id}`-templating for the two
id-bearing fields lifts the byte-weighted figure to **≈0.464** — so a naive generator owns under
half the contract layer, and the contract layer is only 39.29% of the catalog. `overrides.yaml`
would carry **13,032 entries**; at ~80 B each that is roughly **1.04 MB of new authored YAML**
against a 5.34 MB catalog. **This is the single number that most damages my own case** and it is
why §5 does not generate the catalog in Phase 1.

Byte-cardinality check from the independent angle: fields whose distinct-value count is ≤5% of
units account for only **6.32%** of catalog field bytes (`_probe_ssot_defect_clustering_out.json`).
The catalog is genuinely mostly per-unit prose: `question_or_target` 652,207 B / 2,007 distinct,
`evidence_requirement` 487,217 B / 1,914 distinct, `tests_required` 482,794 B / 1,969 distinct,
`inputs` 457,742 B / 1,711 distinct.

### 2.3 Operational cost

- **CI wall-time of emit-348-artifacts + byte-compare: NOT-CHECKED.** The settling probe is
  `python platform/lib/ssot/verify.py --check --time` once the emitter exists; the closest existing
  proxy is that `_gen_schema_substrate.py` already produces 231 files in one local run.
- **Cognitive cost, and it is real.** The owner stops editing the effective file and starts editing
  a spec. `13-ARCHITECTURE-CANDIDATES.md:228-229` scores this candidate "user-control medium — the
  owner edits a spec, not the effective file — a real loss of directness". I do not dispute it.
  Mitigation is partial, not total: every emitted artifact carries `x-generated-by` naming the
  emitter *and* the file to edit instead, which is the pattern already working in the 231 shims.
- **Rollback is byte-exact** — check out the previous spec, re-emit, byte-compare. Hand-editing has
  no equivalent property.

---

## 3. Failure-mode analysis

| # | failure | mechanism | measured precedent | mitigation, and how it is proven |
|---|---|---|---|---|
| F1 | **Emitter silently drops units** | a filter bug emits 2,006 of 2,007 and the gate compares only files that exist | the estate's `install.py:146` dropped 21 registrations incl. 2 security guards (`13-ARCH:105`) | pinned-count invariants (T3): `work_units == 2007`, councilspecs `== 117`, shims `== 231`, protocols `== 48`, presets `== 69`, candidates `== 161`. A missing file is a gate failure, not a skipped comparison |
| F2 | **Emitter overwrites a hand edit** | `--apply` clobbers work that was never in the spec | the same `install.py` defect, from the other end (`H-b`) | `verify.py` in CI is `--check` only and cannot write; `--apply` is local and refuses without a printed diff first |
| F3 | **The generator is its own oracle** | emit + compare passes because artifact and emitter are both wrong | this is how a green suite hides a live defect | the postcondition is `work-unit.strict.schema.json`, authored by a different unit before the emitter existed, plus the 12-condition `completion_predicate.py`. Two mechanically independent oracles, neither derived from the emitter |
| F4 | **A `--check` gate over an untracked tree is vacuous** | nothing committed to diff against | **live now**: all 233 `command-center/schema` files are untracked | Phase 0 of §5 commits them *before* the gate is wired. A gate whose corpus is empty measures nothing — the same class as a benchmark that measured EMPTY inputs and returned a clean green |
| F5 | **Provenance rot** | a generated file without a stamp is indistinguishable from an authored one; the next agent edits it and the emitter silently reverts their work | **live now**: only **8 of 516** tracked JSON files carry any provenance stamp, and all **117 councilspecs carry none** despite being emitted | `x-generated-by` + `source_ref` + `built_at` mandatory on every emitted artifact; `verify.py` fails if an artifact in the EMISSION-MAP lacks its stamp. This is the **most likely** operational failure of this architecture (*likely*, 55-80%) because the repo has already committed it once |
| F6 | **Fifth-registration-surface** | the emitter becomes generator #42 instead of replacing 5 | 41 generators exist today; `platform/council/` alone has 5 writers for one artifact set | the EMISSION-MAP is a *total* function and Phase 1 **deletes** 4 council scripts. If the deletion does not happen, this architecture has not fixed anything — it has added a layer. That is a falsifiable acceptance criterion, not a hope |
| F7 | **Slice-shaped drift returns via the spec** | one author adds a per-slice default block with the wrong type | the measured 100%-within-slice defect pattern is exactly this shape | the strict schema is the postcondition, so a wrong type cannot be emitted at all — measured: strict already rejects the 128/96/159 type-and-format defects, so the mechanism demonstrably fires |

---

## 4. Security review

**Blast radius increases, and I will quantify it rather than assert it is fine.** Today a poisoned
hand edit corrupts **1** artifact. Under this architecture, a poisoned `contract-policy.yaml`
compiles into **348 artifacts** (231 shims + 117 councilspecs) in Phase 1-2, and 2,355 if Phase 3
ever lands. That is a **348× increase in single-edit blast radius** and it is the honest cost of a
single source of truth. `13-ARCHITECTURE-CANDIDATES.md:230` calls it out in the candidate's own
card: *"a poisoned spec now compiles into 40 handlers — single point of compromise."*

Controls, each grounded in something already true in this repo:

1. **Emitters are stdlib-only, no network, no `eval`.** The existing shim tree already demonstrates
   the discipline: every `$id` is `https://ast-integrate.invalid/command-center/schema/...` — a
   deliberately non-resolvable domain, so no validator can be induced to fetch a remote schema.
   Keep `.invalid`; a real domain in an emitted `$id` is a supply-chain hole.
2. **The strict schema is an injection barrier, and it is measured to fire.** `unevaluatedProperties:
   false` already rejects 217 units at the strict profile, so an injected extra field cannot pass
   the postcondition. This is not a claim about a control I hope works; it is a control whose
   rejection count is recorded in `WORKFLOW-DSL-VALIDATION.json`.
3. **`security:`-flagged spec entries the emitter may not drop.** The historical wipe took out both
   security guards; a field the emitter is forbidden to omit, checked by count, makes that
   unrepresentable.
4. **Provenance is a security control, not documentation.** With `x-generated-by` on every emitted
   file, an artifact that is in the EMISSION-MAP but carries no stamp is an unauthorized write.
   Today that check is impossible for 508 of 516 tracked JSON files.
5. **Untrusted-input boundary.** The spec is repo-authored. Emitters must never read from
   `platform/registry/` provenance URLs, a marketplace clone, or any fetched text at emit time —
   fetched content is data, never instructions, and a cloned repo can carry auto-loaded agent
   config. The EMISSION-MAP makes the input set finite and reviewable.
6. **Secrets must never enter the spec.** During this unit the repo's own sensitive-artifact sweep
   fired on one of my probe files (report-only, classification `POTENTIAL-CREDENTIAL`, id
   `sha256:8a9a00142eaa`); no value was emitted and **no credential was touched, rotated or
   inspected** — credential lifecycle is the owner's. Surfacing the id here is the required action.
   A 3-file authored plane that compiles into 348 artifacts is exactly the shape that would multiply
   a leaked secret 348×, so the existing sweep must gate `platform/spec/` specifically.

---

## 5. Migration design from today's state

Phased so that the cheap, measured wins land first and the contested part must earn its way in.
Each phase has a stop condition that can actually fail.

**Phase 0 — make a drift gate possible at all (precondition, no new code).**
Commit the 233 untracked files under `command-center/schema/`, plus `platform/lib/schema_resolver.py`
and `platform/schema/artifact-class-profiles.schema.json` (both untracked; note that
`platform/schema/SUBSTRATE-RESOLUTION-STATUS.json` **is** already in HEAD, so that tree is currently
inconsistent — the status record is versioned while the artifacts it describes are not).
**Stop condition:** until this lands, any `--check` gate on the shim tree is vacuous (F4).

**Phase 1 — the council layer. This is the clear win.**
1. Extract the spec **from the committed artifacts**, do not author it — the same both-states control
   the candidate mandates (`13-ARCH:279-282`).
2. Assert re-emission is **byte-identical** to all 117 committed councilspecs.
   **Stop condition, and it is a real one:** if the round-trip is not byte-exact, the spec is lossy
   and Phase 1 stops. The 117 files share only 5 distinct top-level keysets with a modal keyset
   covering 73 of 117, so I put this at *likely* (55-80%) to pass on the second attempt, not the
   first.
3. Delete `_build_p01_p12.py`, `_gen_protocols_37_48.py`, `_gen_skeletons.py`,
   `presets/_lane2_emit.py`; keep one emitter. Net **-4** scripts (F6's acceptance criterion).
4. Add `x-generated-by` / `source_ref` / `built_at` to all 117.
5. Wire **one** new step into `.github/workflows/quality.yml`. Note the existing four gates are
   split across two workflows (2 in `quality.yml`, 2 in `skill-dual-write.yml`) — put the SSOT gate
   in `quality.yml`, which is the required-context gate, so a drift cannot merge on a green
   `skill-dual-write` alone.

**Phase 2 — the shim tree. Nearly free.**
`_gen_schema_substrate.py` is already a correct emitter with correct in-band provenance. Add it to
the EMISSION-MAP and to `verify.py`. Zero changes to the generator. Zero changes to the 231
artifacts.

**Phase 3 — the catalog. My own measurement says: do NOT generate it yet.**
The round-trip is 5.18% and the override rate is 59.03%. Under this candidate's own stopping rule
that is a halt. **The cheaper fix strictly dominates:** make `work-unit.strict.schema.json` a
blocking gate and repair the 328 failures **at their source slices** — and the clustering says
that is a **5-slice** job (`IMP-1`, `IMP-3`, `IMP-4`, `TST-1`, `WFA-2`), not a 2,007-unit rewrite,
because 5 of the 6 defect classes are 100% homogeneous within a slice. `IMP-4.json` alone accounts
for three of the strict histogram's reason categories at exactly 96 each.
Catalog generation earns its cost **only** if slice-shaped drift *recurs* after that repair. That is
the falsifiable trigger; absent it, Phase 3 stays unbuilt.

**What this migration never does:** it does not rewrite `output_schema` across 2,007 units. That
would edit a committed Wave-1 artifact that ~20 concurrent agents share one git index over — the
same reasoning the substrate unit recorded for rejecting its own option (b).

---

## 6. Test design

Every gate below has a **known-broken control**, because a probe that is silent in both states
measures nothing.

| id | asserts | known-broken control that must go RED |
|---|---|---|
| **T1** | emit twice → byte-identical | inject a dict iteration order dependence; T1 must fail |
| **T2** | spec extracted from HEAD re-emits byte-identically to HEAD's artifacts | perturb one `contract-policy.yaml` value; T2 must fail. (My `_probe_ssot_roundtrip.py` already ships this control: right template reproduces `True`, wrong template reproduces `False`, `detector_valid: true`) |
| **T3** | pinned counts: units 2007 · councilspecs 117 · shims 231 · protocols 48 · presets 69 · candidates 161 | delete one emitted file; T3 must fail rather than skip it |
| **T4** | emitted catalog validates 2007/2007 at strict | re-inject the `IMP-4` string shape into one unit; T4 must fail. Baseline for the assertion is the recorded 1679/2007 |
| **T5** | EMISSION-MAP is a total function with no duplicate target | add a second writer for one path; T5 must fail |
| **T6** | **mutation battery** — one case per measured defect class: prose `output_schema`, string `vendor_role`, string `tests_required`, string `failure_classification`, bare-family dependency, non-pattern sentinel | each re-injected defect must turn the gate red. Six mutations, six required kills. This mirrors `_probe_substrate_bothstates.py`, already the repo's idiom, and the 12/12 predicate mutation kill already achieved in Wave 1 |
| **T7** | emitters make no network call | run with egress blocked and assert success — the hermetic-probe pattern that previously caught 14 tests silently downloading despite comments claiming they never did |
| **T8** | every artifact in the EMISSION-MAP carries its provenance stamp | strip `x-generated-by` from one shim; T8 must fail. Baseline: 8 of 516 tracked JSON pass today |

The 444 Wave-1 baseline tests (475 with the substrate unit's 31) are **reused unchanged**; T1-T8
are additive. No existing test is modified, so a green Wave-1 suite remains a valid signal.

---

## 7. The strongest adversarial refutation of my own architecture

### 7.1 The attack that lands: this candidate fails its own decisive test

`13-ARCHITECTURE-CANDIDATES.md:281-282` states the stopping rule in the candidate's own words:
*"assert re-emission is byte-identical to the current live files. That is the both-states control:
if round-trip is not byte-exact, the spec is lossy and migration stops."*

I ran it. On the catalog, the measured round-trip under a one-template-per-slice generator is
**5.18% byte-exact**; **98.77%** of catalog bytes must be carried as per-unit residue; **no**
contract field is exactly determined by any non-circular key tried; **13,032 of 22,077** contract
field instances need an explicit override, a **59.03%** override rate.

The refutation, stated as strongly as I can make it: *at a 59% override rate the "policy plane" is
not a policy. It is the catalog transcribed into a second syntax, plus a new generator, plus a new
verifier, plus a 1 MB override file, plus a 348× blast radius — in exchange for defects that the
already-committed `work-unit.strict.schema.json` **already detects**. The schema found all 328.
Generation does not find one additional defect. It only prevents future ones. So the entire value
proposition reduces to: is preventing future shape-drift in a catalog that is authored once and
then executed worth a whole new control plane? And the answer, for the catalog, is no — because the
alternative is "make strict blocking and fix 5 slices", which my own clustering measurement proves
is a 5-file job.*

**Does it kill the design? It kills the strong form. I am conceding that explicitly.** The strong
form — *one spec compiles the whole control plane, including the catalog* — is REFUTED by my own
measurement, and I would rather report that than defend it. Anyone advocating catalog generation on
"the same architecture, done correctly" is making the least falsifiable claim available, which is
the criticism the candidate doc itself levels at A2 (`:293-294`).

**What survives, and why it is not a retreat into vagueness.** The weak form is separately
measured and separately true:

- 41 generator scripts already exist; of the **36** that are not their own tests, **32 have no
  drift gate**. That is not a design proposal, it is an
  unguarded surface with a count.
- 117 councilspecs were machine-emitted by **5 competing writers**, carry **0** provenance keys, and
  have **no** gate. One emitter + one stamp + one gate fixes a measured, live condition. The strong
  form is not required to get there.
- 233 shim files are correctly generated and **untracked**, so their gate is currently vacuous.
  Committing them and adding one `--check` is nearly free.
- **Every one of the 6 measured defect classes is a shape/type/format defect, and 5 of 6 are 100%
  homogeneous within a source slice.** Zero measured defects live in the 58% CONTENT layer. So
  generation is aimed at exactly the right layer even where it is not worth paying for.

So my honest verdict on my own candidate: **it wins on the 348-file generated surface and loses on
the 2,007-unit catalog.** Phase 1-2 should ship; Phase 3 should not, until slice-drift recurs.

### 7.2 Second attack: this is the architecture that already burned this estate

`13-ARCH:291-297`: *"The estate has already been burned by exactly this shape. `registration.py`
**is** a generator; `install.py` **is** its applier; and together they are H-a and H-b."* H-a: an
event absent from the generator's tuple is unreachable. H-b: the applier replaced a whole config
key and dropped 21 registrations including both security guards.

**This attack is real and only partly answerable.** H-b is answerable structurally: an emitter that
cannot write in CI, plus pinned counts (T3), plus a forbidden-to-drop `security:` flag, cannot
commit that failure silently. H-a is answerable only by the *completeness* direction — the gate
must assert that every artifact the EMISSION-MAP knows about is emitted **and** that nothing under a
managed path is absent from the map. **I cannot claim H-a is eliminated, only that it becomes
detectable**; the residual is that a class no one thought to enumerate is still invisible, and the
settling experiment is T5 extended to a filesystem sweep of managed directories. Confidence that
the completeness gate closes H-a for the 348 Phase-1-2 artifacts: *likely* (55-80%).

### 7.3 Third attack: 41 → 42

If the council scripts are not actually deleted, this architecture is generator #42 and has made
the problem worse by one. `00-INVENTORY §5.1`'s four-registration-surface finding is the general
warning; `platform/council/`'s five writers are the local instance. I have made the deletion a
falsifiable acceptance criterion in Phase 1 step 3 and in F6 rather than a good intention — but
the honest position is that this risk is **organizational, not technical**, and no schema can
enforce it.

### 7.4 What would make a different candidate win

- **Config-first (A1) wins outright for the catalog.** My own numbers hand it that: strict is
  already authored, already detects all 328, and the fix is 5 slices. If the owner also rejects
  editing a spec instead of the effective artifact, A1 wins the whole board.
- **A gateway/router candidate wins** if the owner's binding constraint is directness of edit
  (`13-ARCH:301-302`).
- **This candidate wins** only on the narrow, measured claim of §7.1's second half — and it should
  be judged on that claim, not on the sweep it is named after.

---

## 8. Reuse vs replace — file counts

**REUSED UNCHANGED (0 deletions, 0 edits):**

| artifact set | count | role under this architecture |
|---|---|---|
| `platform/schema/*.schema.json` | **8** compiling schemas (+6 records; 32 tracked paths) | promoted to the emitter's type system and postcondition |
| `platform/lib` packages | **3** (`wfdsl`, `councilspec`, `council_protocols`) = 29 py files, 10,797 loc | validators, unchanged |
| `platform/lib` loose validators | **3** (`completion_predicate.py`, `receipt_schema_gate.py`, `schema_resolver.py`) = 2,355 loc | oracles, unchanged |
| `platform/lib/_gen_schema_substrate.py` | **1** | reused **as an emitter**, unmodified |
| `tools/command-center/render.py` | **1** | reused **as an emitter**, unmodified (already has `--check`) |
| `command-center/schema/**` | **233** (231 shims + 2 meta) | reused as emitted output; must be committed (Phase 0) |
| `platform/council/**/*.councilspec.json` | **117** (48 + 69) | **bytes preserved**; become emitted-and-stamped rather than authored |
| `platform/registry` candidates | **161** | spec input |
| `WORK-UNIT-CATALOG.json` | **2,007** units + **103** `items[]` | untouched in Phase 1-3; `items[]` is a different schema and is not merged |
| existing tests | **444** baseline (475 with substrate) | unchanged |

**REPLACED:** 4 council generator scripts (`_build_p01_p12.py`, `_gen_protocols_37_48.py`,
`_gen_skeletons.py`, `presets/_lane2_emit.py`) → 1 emitter. **Net −4 files.**

**ADDED:** `platform/spec/` (3 authored files + `EMISSION-MAP.json`) + `platform/lib/ssot/`
(`verify.py`, `emit_councilspecs.py`; `emit_catalog.py` deferred) + 1 CI step ≈ **7 new files**.

**DISCARDED FROM WAVE 1: zero files.** Not one schema, package, protocol, preset, candidate, unit
or test is deleted.

---

## 9. Verdict ledger

| claim | verdict | confidence | anchor |
|---|---|---|---|
| Generated-SSOT is already the repo's dominant pattern (41 scripts / 36 production emitters) but only 4 are CI-gated, leaving 32 ungated | **CONFIRMED** | almost-certain (90-99%) | `_probe_ssot_existing_generators_out.json` (detector control passed both directions) + the 4 CI invocations verified at `quality.yml:403,624,625` and `skill-dual-write.yml:72,79` |
| All 117 councilspecs were machine-emitted yet carry zero provenance and have no drift gate | **CONFIRMED** | almost-certain | 5 of 6 council scripts write `.councilspec.json`; 0 provenance keys across 117 |
| All 233 `command-center/schema` files are untracked, so a gate there is currently vacuous | **CONFIRMED** | almost-certain | `git ls-files` → 0 vs `git status -uall` → 233 |
| Every measured catalog defect is a shape/type/format defect; 5 of 6 are 100% homogeneous within one source slice | **CONFIRMED** | almost-certain | `_probe_ssot_defect_clustering_out.json`, hit rate 1.000 in the worst slice for 5 of 6 |
| Brief's "159 unloadable output_schema" and "128 non-canonical vendor_role" | **CONFIRMED** | almost-certain | three independent signals for 159; two for 128 |
| Brief's "41 unresolvable dependency refs" | **CONFIRMED** | almost-certain | exact derivation ARC 19 + WFA 17 + CC 4 + IMP 1 = 41 |
| Brief's "96 completion sentinels that do not name their own unit" | **REFUTED as phrased** — 0 of 2,007 omit their id; the recorded 96 is a format-pattern failure | almost-certain | 1,367 exact + 640 verbose-containing; detector fires on synthetic bad |
| Catalog generation passes this candidate's own byte-exact round-trip gate | **REFUTED** — 5.18% | almost-certain | `_probe_ssot_roundtrip_out.json` with a valid both-states control |
| Phase 1-2 (council + shims) is worth building | **PLAUSIBLE** | likely (55-80%) | measured live gaps; residual is the Phase-1 byte-exact round-trip, untested until built |
| Phase 3 (catalog generation) is worth building | **argued NO by its own advocate** | likely (55-80%) that the 5-slice strict-gate repair dominates | 59.03% override rate vs a 5-slice fix |
| CI wall-time of emit+verify | **NOT-CHECKED** | — | settling probe named in §2.3 |
| Per-slice attribution of the 217 strict `unevaluatedProperties` failures | **NOT-CHECKED** | — | settling probe named in §1.2 |
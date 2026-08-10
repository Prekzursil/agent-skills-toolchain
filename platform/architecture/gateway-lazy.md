# Architecture Candidate: Gateway / Lazy-Activation

**Tournament entry, PHASE 3 — ARCHITECTURE TOURNAMENT.** Advocate position, honest costs.
Spec: `C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10769-10796`.
Prior design consumed, not redesigned: `13-ARCHITECTURE-CANDIDATES.md:398-470` (candidate `A4`,
MECH namespace).

**Measured across a MOVING HEAD, and this must be disclosed rather than hidden.** Concurrent
sibling lanes are committing while this tournament runs. `HEAD` was `b68815fd` when my inventory
probe ran and `9f2dac7a` when I re-verified the load-bearing claims — 4 commits past the brief's pin
`dc90d64a`, which remains an ancestor `[M]`. The 4 commits are `36070a6f` (lint/format/render drift,
131 files, −37,174), `833fb1ea` (untrack 85 scratch probe scripts, −26,305), `b68815fd`
(LF-normalise manifest hashes, 2 files), `9f2dac7a` (SAST annotation, 1 file). Large deletion counts,
but all four are hygiene, not semantics — **UNVERIFIED** that none altered a value I cite; the
settling experiment is `git diff dc90d64a..HEAD -- <cited file>` per claim. Every load-bearing
correction in §0 was **re-verified at `9f2dac7a`** and still holds.

Per the policy `833fb1ea` established, my `_probe_gwlazy_*.py` scripts are deliberately left
untracked scratch; this document is the deliverable.

**Evidence classes.** `[M]` measured by me this pass, probe named · `[S]` measured by a sibling
lane, artifact named, **not** independently re-run by me · `UNVERIFIED` inline, with the settling
experiment. Bands: *almost certain* 90-99 · *likely* 55-80 · *roughly even* 40-60.

My probes, all with detector controls, all `SUCCESS:`-terminated:
`_probe_gwlazy_inventory.py` · `_probe_gwlazy_cost.py` · `_probe_gwlazy_eager.py` ·
`_probe_gwlazy_invariant.py` (both-states) · `_probe_gwlazy_doors.py` ·
`_probe_gwlazy_frontier.py` (both-shapes) · `_probe_gwlazy_depns.py` (artifact-vs-finding).

---

## 0. Verdict on Wave 1 — what this architecture REUSES vs REPLACES

**This architecture discards nothing from Wave 1. Zero Wave-1 files are replaced, rewritten, or
deleted.** It is a consolidation architecture: it reduces the number of *doors* into the platform
while leaving every artifact behind those doors byte-identical. The catalog is not edited. No
schema is edited. No protocol or preset is edited.

Counted against what is on disk `[M: _probe_gwlazy_inventory_out.json, _probe_gwlazy_cost_out.json]`:

| disposition | files | what |
|---|---:|---|
| **REUSE, byte-identical** | 9 | `platform/schema/*.schema.json` (workflow-dsl, work-unit ×3, work-unit-catalog, councilspec, receipt, completion-predicate-result, artifact-class-profiles) |
| **REUSE, byte-identical** | 232 | `command-center/schema/` generated `$ref` shims, 259,667 B, mean 1,119 B |
| **REUSE, byte-identical** | 28 | shippable `platform/lib/**.py` (562,404 B) across 4 packages (`wfdsl`, `councilspec`, `council_protocols`, + `workflows`) plus `completion_predicate.py`, `receipt_schema_gate.py`, `schema_resolver.py` |
| **REUSE, byte-identical** | 48 | `platform/council/protocols/*.councilspec.json`, 633,345 B |
| **REUSE, byte-identical** | 69 | `platform/council/presets/*.councilspec.json`, 822,378 B |
| **REUSE, byte-identical** | 7 | `platform/registry/workflow-candidates-*.json`, 863,779 B, 164 candidate rows |
| **REUSE, byte-identical** | 1 | `command-center/WORK-UNIT-CATALOG.json`, 5,343,710 B, `work_units[]`=2,007, `items[]`=103 (untouched, separate schema) |
| **REUSE, byte-identical** | 8 | `platform/lib/**/test_*.py`, 214 test functions, 148,918 B |
| **MODIFY (2 JSON files)** | 2 | `hooks/_dispatch/manifest.json` (add `wall_cap`, typed status, 15 more events) · `agent-self/config/settings.json` (41 registrations → 21) |
| **DEMOTE, not delete** | 1 | `agent-self/harness/dispatcher.py` (585 lines) stops being a *registered* entry; stays importable as a library |
| **NET-NEW shipped** | 3 | `platform/lib/unit_gateway.py` · `platform/lib/gateway_invariants.py` · `platform/schema/gateway-manifest.schema.json` |
| **NET-NEW tests** | 2 | `platform/lib/test_unit_gateway.py` · `platform/lib/test_gateway_invariants.py` |

**Reuse : new = 402 : 5.** The architecture's entire net-new surface is three shipped files, and
one of them is a schema.

**A correction the tournament must carry.** The brief states Wave 1 is "all committed and pushed"
and the SUBSTRATE block reports P1 closed. On disk, in this working tree, P1 *is* closed — but the
closure is **UNCOMMITTED**, on two mechanically independent signals `[M]`:
`git ls-files command-center/schema` → **0 files**, and `git status --porcelain -uall
command-center/schema` → **233 `??` entries**. Same for `platform/lib/schema_resolver.py`,
`platform/schema/artifact-class-profiles.schema.json`, `platform/schema/ARTIFACT-CLASS-REGISTRY.json`
and the 8 substrate example receipts. `git check-ignore` returns nothing, so these are simply not
staged, not ignored. **Re-verified at `9f2dac7a` after four intervening commits: still 0 tracked,
still 233 `??`.** **Consequence: a fresh clone at `HEAD` still resolves 0 of 234 declared schema
classes.** This does not weaken the architecture — GW-2 below is precisely the pattern those files
implement — but any judge treating "committed" as satisfied is reading the brief, not the tree.
Confidence *almost certain* (90-99).

---

## 1. Design

### 1.1 The thesis, stated so it can be falsified

The platform does not lack capability. It has **N admission doors per surface and no cost model
behind any door**, so nobody can answer "what does one more check cost?" or "which units may start
now?" without reading every file. Gateway/lazy-activation asserts exactly two invariants and
derives everything else from them:

- **INV-GW-1 — one door per surface.** For every host-observable surface (a hook event, a schema
  class, a work unit, a capability lookup) there is exactly **one** registered entry point. Every
  other participant becomes a *manifest row* carrying a matcher, a budget, an `emits` flag, and a
  typed status.
- **INV-GW-2 — no uncosted battery.** Every gateway declares a **numeric** `wall_cap` and that cap
  is `<=` the host's own timeout. A battery whose budget cannot be compared to its host timeout is
  not admitted.

**Lazy activation is the corollary, not a separate feature:** a row whose matcher misses is never
imported, never costed, never counted. That is why one door can host 27 checks without paying for 27.

### 1.2 Four surfaces, four gateways, named against real files

#### GW-1 — hook-event gateway · `hooks/_dispatch/dispatch.py` (437 lines) — EXTEND

Today, measured in `agent-self/config/settings.json` `[M: _probe_gwlazy_doors_out.json]`:

```
19 events · 41 registrations · 418 s of declared timeout in total
13 events already at exactly 1 registration  (INV-GW-1 satisfied)
 6 events violate INV-GW-1:  PreToolUse 12 · PostToolUse 5 · SessionStart 3 ·
                             Stop 3 · UserPromptSubmit 3 · PostToolUseFailure 2
```

**The finding that reframes this candidate: there are already TWO gateways, and they overlap.**
`hooks/_dispatch/dispatch.py` is registered on 4 events (SessionStart, Stop, PostToolUse,
PreToolUse). `harness/dispatcher.py` is registered on **16** events. The same 4 events carry
**both**. Three events (StopFailure, WorktreeCreate, WorktreeRemove) carry **neither**. The two
dispatchers are distinct files with distinct hashes: `hooks/_dispatch/dispatch.py` 437 lines
`e9db8e6ff0f7f372`, `agent-self/harness/dispatcher.py` 585 lines `16663ffb01b613c2`,
`ci/harness/dispatcher.py` 204 lines `bf6f9311f93f9d76` `[M]`.

This is the **duplicate control plane the spec forbids** (`_USER-PROMPTS.md:10490`, "do not create
duplicate control planes when an existing one can be extended"). GW-1's deliverable is therefore
**not** "add a gateway" — it is *merge the two that exist*. That materially changes the candidate's
value proposition and its risk: consolidation of a live duplicate, not new machinery.

`hooks/_dispatch/manifest.json` (repo copy) carries 4 events / 27 rows, and INV-GW-2 fails **4 of
4** `[M: _probe_gwlazy_invariant_out.json, detector-controlled]`:

| event | rows | budget sum | host timeout | oversubscription | `wall_cap` |
|---|---:|---:|---:|---:|---|
| Stop | 9 | 101 s | 35 s | **2.9×** | ABSENT |
| PreToolUse | 7 | 57 s | 15 s | **3.8×** | ABSENT |
| SessionStart | 6 | 48 s | 20 s | **2.4×** | ABSENT |
| PostToolUse | 5 | 29 s | 15 s | **1.9×** | ABSENT |

Oversubscription is *why a wall cap and not a sum is the right model* — the sum can legitimately
exceed the host timeout because rows run threaded and most miss their matcher. But with `wall_cap`
absent on all four, the model runs on a default nobody has costed. The live tree agrees and adds
one more defect: live `dispatch.py` is 501 lines / 20,378 B and **still contains the `or ""`
coercion** `[M: _probe_gwlazy_inventory_out.json:dispatch_py_has_or_empty_coercion=true]`, so a
JSON-numeric `wall_cap: 0` is silently discarded while the string `"0"` works — the manifest cannot
express the value that matters most. Fixing that coercion is a precondition of INV-GW-2, not an
optional cleanup.

Scale of what sits behind the door: `hooks/` holds **71** check directories against **27** manifest
rows `[M]`, so 44 check directories are outside the gateway entirely — registered directly, or dead.
Which of the 44 are live is **UNVERIFIED**; the settling experiment is to join the 71 directory
names against the 41 registration command strings and the 27 manifest rows and print the
three-way difference.

#### GW-2 — schema-class gateway · `platform/lib/schema_resolver.py` — REUSE UNCHANGED

**This gateway already exists and is the existence proof for the whole architecture.** A sibling
lane closed the substrate P1 by building exactly the pattern this candidate advocates: 234 logical
schema classes, named by 2,007 `output_schema` declarations, resolve through **one** door onto
**three** physical control-plane files `[S: platform/schema/SUBSTRATE-RESOLUTION-STATUS.json]`:

```
door:      schema_resolver.resolve() / validator_for() / validate_artifact() / audit()
index:     platform/schema/ARTIFACT-CLASS-REGISTRY.json   141,085 B · 234 entries   [M]
physical:  platform/schema/receipt.schema.json
           platform/schema/artifact-class-profiles.schema.json
           command-center/schema/_meta/json-schema-2020-12.json      230,206 B total [M]
lazy tier: 232 generated $ref shims                       259,667 B · mean 1,119 B  [M]
invariant: test_shims_carry_no_constraints — fails if any shim grows a keyword       [S]
```

Every shim is pure delegation; a shim defines no constraint. That is the *lazy* half done right:
the expensive artifact (the constraint set) is authored once and the cheap artifact (the 1,119-byte
pointer) is what multiplies. GW-2 needs **zero** further design work. Its one open action is
administrative: commit it (see §0).

#### GW-3 — work-unit admission gateway · `platform/lib/unit_gateway.py` — NET-NEW, the only real new machinery

This is the surface with **no** gateway today. Measured `[M: _probe_gwlazy_frontier_out.json,
_probe_gwlazy_depns_out.json]`:

```
2,007 units · 0 duplicate ids · 0 dependency cycles · 19 topological layers
3,689 dependency edges · 1,996 units declare >=1 dep · 11 declare none
frontier widths: [489, 250, 326, 277, 177, 104, 99, 62, 48, 54, 24, 26, 14, 27, 18, 5, 2, 4, 1]
21 distinct phases · 4 execution substrates · 529 distinct assigned_model_vendor_role values
declared budget: sum(timeout_seconds) = 8,247,600 s = 2,291.0 h · median 3,600 s · max 14,400 s
```

**Dependencies span three namespaces, and this is a real design requirement discovered by
measurement.** Of 1,007 distinct dependency tokens, **17 do not name a work unit**: thirteen
allocation-bucket ids `B01`…`B13` and four family prefixes `ARC`, `CC`, `IMP`, `WFA`. Splitting the
3,689 edges by namespace produces an **exact three-way reconciliation across three independent
sources** `[M]`:

```
unit-id edges    2,644   == the sibling A5-R lane's independently measured G1 edge count
bucket edges     1,004   == the sibling A5-R lane's independently measured bucket-level edge count
family edges        41   == THE BRIEF'S "41 unresolvable dependency refs"  (ARC 19 · WFA 17 · CC 4 · IMP 1)
                 -----
                 3,689   == my total dependency-edge count
```

Three sources, three different methods, one arithmetic identity. This **CONFIRMS** the brief's `41`
and, better, *identifies* what those 41 are: whole-family dependency references, not broken links.
`B01`…`B13` are declared in `command-center/PHASE-GRAPH.json:allocation_buckets.buckets[]`
(13 buckets, measured sum 2,048 = the spec floor) and appear as JSON strings in 19
`command-center/*.json` files, against a ghost-token control that hits 0 files
`[M: _probe_gwlazy_depns_out.json, detector_valid=true]`.

So `admit()` must resolve *unit → unit*, *unit → bucket*, and *unit → family* edges. A resolver that
knows only unit ids reports 1,045 phantom breakages — which is exactly what my first pass did before
the control caught it. Confidence in the reconciliation: *almost certain* (90-99), because the three
counts sum to the total exactly and were produced by three unrelated probes.

The door:

```python
# platform/lib/unit_gateway.py  — a PURE FUNCTION, no loop, no persistence, no supervision
def admit(catalog_path, receipts_root, *, substrate=None, phase=None, limit=None) -> AdmissionSet:
    """Return the units whose dependencies are satisfied by receipts already on disk.

    Dependency satisfaction is delegated, never reimplemented:
      - a unit is DONE iff completion_predicate.evaluate(receipt) returns 12/12
      - a receipt is schema-valid iff schema_resolver.validate_artifact(receipt, unit.output_schema)
      - a bucket/family dep is satisfied iff every member unit is DONE
    Materializes the full record for admitted ids ONLY. Never writes. Never spawns."""
```

That is the whole contract. It reuses `completion_predicate.py` (12 conditions, `Outcome`/`Verdict`
enums, 42 test functions) and `schema_resolver.py` rather than growing a second notion of "done".

#### GW-4 — capability gateway · `hooks/skill-router`, `semantic-router`, `capability-catalog` — REUSE

Lazy activation is **already the dominant pattern here, and it is measured, not asserted**
`[M: _probe_gwlazy_eager_out.json]`:

| plane | eager (always loaded) | lazy (loaded on match) | amplification |
|---|---:|---:|---:|
| `skills/` 338 SKILL.md | 99,699 B of `description:` | 2,357,745 B of body | **23.6×** |
| `.agents/skills/` 352 | 104,444 B | 2,414,073 B | 23.1× |
| `rules/` 88 files | 8 always-on, 62,849 B | 80 `paths:`-gated, 185,399 B | **2.95×** |
| council | — | 48 protocols + 69 presets, 1,455,723 B | **58×** vs one-of-each 25,112 B |
| catalog | — | 2,007 units, 5,343,710 B | **2,257×** vs one unit, 2,368 B |

The shipped indexes that make it work: `skill-router/_index.json` 488,629 B ·
`semantic-router/index/vecs.f32` 1,099,776 B + `meta.json` 98,650 B ·
`recall-inject/index/recall_index.json` 528,097 B / 621 notes · `capability-catalog/catalog.json`
4,569 B `[M]`. GW-4 contributes **one** new constraint, not new code: the marketplace manifest
`.claude-plugin/marketplace.json` eagerly enumerates **379 skill paths in 18,905 B** — a host
requirement that cannot be made lazy, so it must be *generated* from the vault and gate-checked, not
hand-maintained.

### 1.3 The typed-status contribution (this is the honesty half, not a nicety)

Every gateway returns, per row, one of `FINDING | CLEAN | NOT-CHECKED | RAISED`. `NOT-CHECKED` is
the load-bearing member: it is the only way a dropped row is distinguishable from a clean one. The
estate has measured the failure this prevents — a check that stopped *reporting* rather than
stopped *detecting*, where "found no problems" and "never ran" were byte-identical
(`13-ARCHITECTURE-CANDIDATES.md:106-118`, §0.1, two independent signals).

**Do not invent a second vocabulary.** `platform/lib/completion_predicate.py:118-136` already
defines `Outcome` and `Verdict` enums with 12 conditions and a `completion-predicate-result` schema.
The gateway status field is that enum, reused.

### 1.4 Source of truth, after

Four files, each singular and each with a cost model attached:

```
agent-self/config/settings.json        19 one-line registrations (was 41)
hooks/_dispatch/manifest.json          19 event rows, numeric wall_cap, typed status
platform/schema/ARTIFACT-CLASS-REGISTRY.json    234 class -> physical-target rows
command-center/WORK-UNIT-CATALOG.json  2,007 unit rows (UNCHANGED, read-only to the gateway)
```

---

## 2. Cost and complexity analysis

### 2.1 What it costs to build

| item | size | basis |
|---|---|---|
| `unit_gateway.py` | ~250-350 lines | mostly delegation; `admit()` + two-namespace resolution + `AdmissionSet` |
| `gateway_invariants.py` | ~120 lines | INV-GW-1 + INV-GW-2 are 30 lines total in my probe, measured |
| `gateway-manifest.schema.json` | ~150 lines | typed `wall_cap`, per-row `emits`, matcher, status enum |
| 2 test files | ~40 test functions | the repo's existing density is 214 functions → 475 tests, ratio 2.2× `[M]`/`[S]` |
| `manifest.json` edit | 4 rows → 19 rows | +15 event rows, +19 `wall_cap` values |
| `settings.json` edit | 41 → 21 registrations | 37 absorbed − 2 security carve-outs = 20 removed, gateway rows added |
| `dispatch.py` `or ""` fix | 1 line | precondition for INV-GW-2 |

Effort **M**. Ops complexity **reduced** (20 fewer host process spawns per session; PreToolUse
alone drops from 12 spawns to 2 on the hottest path). Reversibility **good**: the change is two JSON
files and one deleted registration; rollback is a file copy.

### 2.2 What it costs at run time

**The honest headline: the byte savings are real but small, and I will not lead with them.**
Peak resident for the widest layer is 489 × 2,368 B = 1,157,952 B against 5,343,710 B eager — a
**4.6× reduction on 5 MB** `[M]`. Nobody on this box is bound by 5 MB. Anyone selling GW-3 on
resident bytes is selling a rounding error.

**The cost that actually matters is admission correctness, and here the numbers are severe**
`[M: computed from `timeout_seconds`, all 2,007 units, int-typed]`:

```
whole program declared budget                              2,291.0 h
  of which execution_substrate == local-serialized           699.7 h   <- CANNOT be parallelised
layer 0 (489 ready units) declared budget                    590.6 h
  local-serialized  174 units                                211.6 h   <- serial floor for layer 0
  local-parallel    165 units                                187.6 h
  worktree-isolated  94 units                                125.6 h
  cloud-batch        56 units                                 65.8 h
ideal wall at concurrency 16                                 143.2 h
ideal wall at concurrency 32                                  71.6 h
```

So **699.7 h — 29 days — of the program is serial by substrate contract**, and no gateway
compresses it. That is a cost of the *program*, disclosed here because a candidate that hides it is
lying about what admission control can buy. What the gateway buys is that the 174 serialized units
in layer 0 are not launched concurrently in the first place — on a box with a measured
commit-exhaustion freeze mode, launching 489 units because they are topologically ready is the
failure, not the goal.

### 2.3 Complexity NOT added

- No new orchestration runtime. `admit()` is a pure function over on-disk receipts.
- No new memory store. The two indexes it reads (`ARTIFACT-CLASS-REGISTRY.json`, `PHASE-GRAPH.json`)
  are build-time data files that already exist.
- No new schema language. `gateway-manifest.schema.json` is draft-2020-12 like the other 9.
- No vendor coupling. The gateway never names a model; `assigned_model_vendor_role` stays a unit
  field (529 distinct values `[M]`).

### 2.4 Anchor compliance

`13-ARCHITECTURE-CANDIDATES.md:128` scores A4 **PASS** — rides the existing hook bus, reintroduces
none of the six rejected components. I concur **with one boundary made explicit that doc-13 left
implicit**, because it is where this candidate can silently become non-compliant: see §7.

---

## 3. Failure-mode analysis

| id | failure | measured basis | detection | mitigation |
|---|---|---|---|---|
| **F1** | **Gateway fails open: the door runs, reports success, and silently drops rows.** The estate has already lived this exact loss. | `13-ARCHITECTURE-CANDIDATES.md:106-118`: live `dup-guard/guard.py` byte-identical to the variant its own verifier recommended *against*; `NOT-CHECKED` token count **0**; a real symbol collision that fired 5/5 before now answers with silence, and the `DISARMED` banner that made it visible was removed. | Typed per-row status; a row that did not run is `NOT-CHECKED`, never absent. | §1.3. **This is the single most important mitigation in the design and it is currently unenforced by code** — see F1b. |
| **F1b** | The typed-status field exists but nothing asserts it is *emitted*. A gateway can regress to untyped silence with all tests green. | The 2026-08 precedent: the honest signal was removed and the suite stayed green. | A both-states test: run the gateway with a row forced to time out; the output MUST contain that row with `NOT-CHECKED`. | `test_gateway_invariants.py::test_dropped_row_is_reported_not_checked`. Mandatory, not optional. |
| **F2** | Budget starvation: one slow row consumes the wall cap and later rows are dropped every turn, deterministically, so a check is effectively uninstalled. | Stop is 2.9× oversubscribed, PreToolUse 3.8× `[M]`. Ordering is currently manifest order. | Per-row wall-time telemetry to the event ledger; a Stop-turn budget report. | Round-robin the drop victim across turns, and make repeated `NOT-CHECKED` for the same row a `RAISED`. |
| **F3** | Two-namespace dependency resolution silently under-admits (a bucket dep never satisfies → units never start) or over-admits (a bucket dep treated as absent → units start early). | My own first pass over-admitted: 489 roots vs the phase-graph's 248 `[M]`/`[S]`. | Cross-check `admit()` layer 0 against `PHASE-GRAPH.json:parallel_frontier.total_units_startable_today`. | Two mechanically independent frontier computations must agree within a stated tolerance; disagreement is a build failure, not a warning. |
| **F4** | `wall_cap` numeric value silently discarded by the `or ""` coercion → the cap is not the cap. | `dispatch_py_has_or_empty_coercion = true` in the LIVE file `[M]`. | A test that sets `wall_cap: 0` as a JSON number and asserts the gateway honours it. | Fix the coercion first; the test is the both-states control. |
| **F5** | Dual-gateway drift during migration: both dispatchers live on the same 4 events, each with its own matcher set, so a check can run twice or zero times. | 4 events carry both `dispatch.py` and `harness/dispatcher.py` `[M]`. | Count rows executed per event per turn; expect exactly the manifest row count. | Migrate event-by-event with the double-fire count asserted at each step; never both-on for a merged event. |
| **F6** | Manifest/registration divergence: a row exists in `manifest.json` but the event has no gateway registration, so the row is dead but *looks* configured. | 3 of 19 events carry neither dispatcher `[M]`; 44 of 71 check dirs are outside the manifest `[M]`. | INV-GW-1 checked in CI over `settings.json` × `manifest.json` × `hooks/*/`. | `gateway_invariants.py` as a required gate. |
| **F7** | Lazy activation hides a *permanently* missing capability: a matcher that never matches is indistinguishable from a check that is not installed. | The general shape of H-h (untyped silence). | Matcher-hit telemetry: a row with 0 hits over N sessions is `RAISED`, not silent. | A row must justify its existence with hits or be retired. |
| **F8** | Catalog read cost on every admission. 5,343,710 B parsed per `admit()` call. | `[M]` | Time `admit()`; if > 1 s, it is on a hot path it should not be on. | Cache keyed by catalog mtime+size; `admit()` is called per wave, not per unit. Confidence *likely* this is a non-issue at wave granularity. |
| **F9** | Skill-vault duplication defeats the capability gateway: two vaults, one index. `skills/` and `.agents/skills` share 1,714 paths of which **28 differ in bytes**; 83 files exist only in `skills/`, 201 only in `.agents/skills` `[M]`. | `_probe_gwlazy_eager_out.json:dup_skills_vs_agents` | Hash-diff the two trees in CI. | Out of scope for this candidate to *fix*, but the gateway must declare which tree is authoritative or it routes to the wrong copy. Disclosed, not solved. |

---

## 4. Security review

**The governing rule: the gateway must never be the reason a security check does not run.**

### 4.1 The carve-out, named against real registrations

Two guards must stay as their **own** `settings.json` entries and be explicitly *out* of the
battery, because a budget-droppable blocking guard is not a guard:

- `deny.py` — the credential-read denier. It is registered on **PreToolUse**, the event with **12**
  registrations and **116 s** of declared timeout `[M: _probe_gwlazy_doors_out.json]`. My probe's
  carve-out detector found exactly one matching leaf: `['deny.py']`.
- the force-push guard — `hooks/no-force-push/` exists as a check directory `[M]`; **UNVERIFIED**
  whether it is currently a `settings.json` registration or a manifest row. Settling experiment:
  grep the 41 registration command strings for `no-force-push`. If it is a manifest row today, it
  is already budget-droppable and that is a **live defect this candidate must not inherit**.

Absorbing either into the battery converts a blocking guard into an advisory. That is the one
change this architecture is forbidden to make, and it is testable:
`test_gateway_invariants.py::test_security_guards_are_not_manifest_rows`.

### 4.2 One door = one bypass

Concentrating 27 rows behind one entry point means one exploitable or crashing gateway disables 27
checks. Mitigations, in order of strength:

1. **Fail-closed on gateway error for blocking events.** If the gateway raises on PreToolUse, emit
   a deny-by-default `RAISED` status rather than exit 0. This inverts the estate's default
   (AGENTS.md §6 "any hook error exits 0, fail-open") **for the blocking subset only** — advisory
   events stay fail-open. This is a deliberate, narrow exception and must be called out to the
   owner, not slipped in. Confidence *likely* (55-80) that this is the right trade; it is a
   genuine value conflict, not a technical one.
2. **The carve-out (§4.1)** keeps the two credential/history guards outside the blast radius
   entirely.
3. **Typed status** makes a silent drop detectable within one turn (§1.3).

### 4.3 Supply-chain surface

Lazy activation *reduces* attack surface in one measurable way and *increases* a different one:

- Reduces: 9 of 99 `enabledPlugins` are `true` `[M: live settings.json]`, and
  `~/.claude/plugins` holds **1,532** `SKILL.md` files across 6 marketplace clones `[M]`. Only
  matched rows are imported, so an unmatched malicious skill body is never read. A cloned repo's
  `.claude/`, `.mcp.json` or hooks dir can auto-load config the moment an agent runs in it
  (CVE-2026-47751-class); a gateway that imports only on match narrows that window.
- Increases: the *index* becomes a high-value target. Poison `skill-router/_index.json` (488,629 B)
  or `ARTIFACT-CLASS-REGISTRY.json` (141,085 B) and you control routing without touching a single
  skill. Mitigation: both indexes are **generated**, and the generator's output must be
  byte-reproducible from the vault — a hash mismatch is a build failure. `ARTIFACT-CLASS-REGISTRY`
  already has this property by construction `[S]`.

### 4.4 No credential surface added

`admit()` reads: the catalog, receipts, `PHASE-GRAPH.json`, `ARTIFACT-CLASS-REGISTRY.json`. It
writes nothing and spawns nothing, so it cannot read, print, or egress a credential. Tool
permissions stay a *unit* field, enforced by the executor, not granted by the gateway. During this
pass a report-only sweep flagged one `POTENTIAL-CREDENTIAL` artifact id `sha256:c75f24b08919`; per
AGENTS.md §9 I did not inspect, print, rotate, or touch it — surfacing the id to the owner is the
whole of my action.

---

## 5. Migration design from today's state

Five stages, each independently revertible, each with its own gate. Ordering is forced by
dependencies, not preference.

**Stage 0 — commit Wave 1's substrate (blocking, 0 design work).** 233 `command-center/schema`
shims + `schema_resolver.py` + `artifact-class-profiles.schema.json` +
`ARTIFACT-CLASS-REGISTRY.json` + 8 example receipts are untracked (§0). GW-2 and GW-3 both depend
on `schema_resolver.resolve()`. Until this is committed, every downstream claim is working-tree-only.
Gate: `git ls-files command-center/schema | wc -l` = 233.

**Stage 1 — fix the `or ""` coercion in `dispatch.py`.** One line. Precondition for INV-GW-2, since
until it lands a numeric `wall_cap` cannot be expressed. Gate: a test setting `wall_cap: 0` as a
JSON number and asserting the cap is honoured (the both-states control is `"0"` as a string, which
already works).

**Stage 2 — arm INV-GW-1 and INV-GW-2 as an advisory gate, blocking nothing.** Ship
`gateway_invariants.py`. Expected first output, already measured: 6 INV-GW-1 violations, 4 INV-GW-2
violations `[M]`. Publishing the violation list *before* fixing anything is what makes the fix
falsifiable. Gate: the checker reproduces my probe's counts exactly.

**Stage 3 — declare `wall_cap` on the 4 existing gateway events.** Values must be `<=` host
timeout: Stop 30/35, PreToolUse 12/15, SessionStart 17/20, PostToolUse 12/15 (proposed; the owner
sets them). Add the typed-status field and re-arm `NOT-CHECKED`. Gate: INV-GW-2 goes 4 violations →
0, and F1b's forced-timeout test passes.

**Stage 4 — merge the dual gateway, one event at a time, 16 events.** For each event carrying
`harness/dispatcher.py`: move its checks into `manifest.json` rows, register `dispatch.py`, delete
the `dispatcher.py` registration, assert the executed-row count equals the manifest row count.
Order by risk ascending — start with the 3 events that carry *neither* dispatcher (StopFailure,
WorktreeCreate, WorktreeRemove: nothing to break), then the 12 single-registration events, then
UserPromptSubmit (3), then PostToolUse (5), then Stop (3), then SessionStart (3), and **PreToolUse
(12) last** because it is the hottest path and holds `deny.py`. Net: 37 registrations absorbed
minus 2 carve-outs = 41 → 21. Gate per event: row count matches; `deny.py` still its own entry.

**Stage 5 — ship `unit_gateway.py`.** Only after Stages 0-4, because `admit()` depends on
`schema_resolver` (Stage 0) and on the typed-status vocabulary (Stage 3). Gate: `admit()`'s layer-0
set cross-checks against `PHASE-GRAPH.json:parallel_frontier` (F3).

**Rollback.** Every stage is a file-content revert; no data migration, no state to unwind. Stage 4
is per-event, so a bad event reverts alone. Under PR-ONLY release mode, "release succeeds" is read
as *a merged PR plus a local rollback rehearsal* — I am stating that reading explicitly, per the
binding owner decision, and stop condition 13 is otherwise unsatisfiable as literally written.

---

## 6. Test design

### 6.1 Invariant tests (the architecture's contract)

Already prototyped and **detector-controlled** in `_probe_gwlazy_invariant.py`, which is why I can
state the expected outputs rather than hope for them:

```
INV_GW1  known-good synthetic  -> 0 violations      (must be 0)
INV_GW1  known-broken synthetic -> 2 violations     (Stop=2 regs, SessionEnd=0 regs)
INV_GW2  known-good synthetic  -> 0 violations
INV_GW2  known-broken synthetic -> 2 violations     (wall_cap "0" string; wall_cap 60 > timeout 15)
detector_valid = true on both
real repo -> INV_GW1 6 violations, INV_GW2 4 violations
```

A checker that is silent on the known-broken state measures nothing. Both controls fire.

### 6.2 Both-states tests (the ones that would have caught the 2026-08 regression)

- `test_dropped_row_is_reported_not_checked` — force a row to exceed its budget; the aggregated
  output MUST carry that row with `NOT-CHECKED`. Broken state: the row is absent. This is the
  literal test whose absence let "found no problems" and "never ran" become byte-identical.
- `test_wall_cap_numeric_zero_is_honoured` — `wall_cap: 0` as a JSON number. Broken state: the
  `or ""` coercion discards it and the default applies.
- `test_security_guards_are_not_manifest_rows` — `deny.py` and the force-push guard must appear in
  `settings.json`, never in `manifest.json`. Broken state: either is absorbed.
- `test_gateway_error_fails_closed_on_blocking_events` — inject an exception; PreToolUse must emit
  `RAISED`, not exit 0.

### 6.3 Differential / cross-check tests

- `test_admit_layer0_agrees_with_phase_graph` — `admit()`'s layer 0 vs
  `PHASE-GRAPH.json:parallel_frontier`. Two mechanically independent computations: mine layers
  unit-level `dependencies`; theirs walks phase-level HARD edges. Measured today: **489** (mine,
  bucket deps dropped) vs **248** today / **472** if the contested `1→2` edge downgrades to SOFT
  `[M]`/`[S]`. My 489 is within **17** of their contested-soft 472, and the residual is explained:
  I dropped bucket deps, which promotes bucket-gated units to roots. **This disagreement is the
  test.** With three-namespace resolution wired, the two must converge; if they do not, one of them
  is wrong and neither may be cited. *Corroborating signal:* the `A5-R` lane's independent probe
  measured layer-0 width **489** and depth **19** on unit-id edges alone — identical to mine, by a
  different implementation. That agreement is what makes the *residual* interpretable rather than
  noise.
- `test_three_namespace_resolution` — the 17 non-unit tokens must resolve: 13 buckets → 1,004 refs,
  4 family prefixes → 41 refs, and `2,644 + 1,004 + 41 == 3,689` must hold as an assertion, not a
  comment. A ghost token must not resolve; control measured: `B99ZZZ` hits 0 files.
- `test_shims_carry_no_constraints` — already shipped `[S]`; reused unchanged.

### 6.4 Mutation tests

Revert each of these and require the suite to go red:
(1) delete a `wall_cap` value; (2) add a second registration to one event; (3) move `deny.py` into
`manifest.json`; (4) drop the `NOT-CHECKED` emission; (5) make `admit()` ignore bucket deps;
(6) let a shim grow a `required` keyword. A suite that stays green on any of the six is not
protecting that behaviour. Precedent for why this is not optional: on the 6-mutation C1 battery,
**one survived** and exposed a genuine hole in tests that were 15/15 green.

### 6.5 Regression floor

Existing: **214 test functions** across 8 files in `platform/lib` `[M]`, reported as **475 passing
tests** after parametrization `[S]` — I did not re-run the suite, so I cite 214 functions as my
independent signal and mark 475 as the sibling's measurement (ratio 2.2×, consistent). New floor:
475 + ~40. Any drop is a build failure.

---

## 7. Strongest adversarial refutation of this architecture

Here is the argument I would use to kill this design if I were assigned to kill it. I am stating it
at full strength and then saying plainly how much of it lands.

### 7.1 The argument

> **"Gateway/lazy-activation is not an architecture. It is three config edits and one scheduler —
> and the scheduler is the component the program's own anchor forbids."**
>
> Take the four gateways in turn.
>
> **GW-2 is already built.** 234 classes, 232 shims, one resolver, shipped by a sibling lane before
> this tournament ran. The candidate claims it as REUSE, which is honest, but it means the
> flagship demonstration of "gateway/lazy-activation works" is *someone else's* deliverable. Strike
> it from the ledger and the candidate loses its only working example.
>
> **GW-4 is already built.** 80 of 88 rules are `paths:`-gated. 338 skill bodies are already lazy
> behind 99,699 B of descriptions. Four router indexes already ship. The candidate's own
> measurements prove lazy activation is the *status quo*, not a proposal. Its contribution here is
> one sentence about generating a manifest.
>
> **GW-1 is a config fix.** Every defect it names — `wall_cap` absent ×4, 41 registrations instead
> of 19, a dual dispatcher, the `or ""` coercion — is repaired by editing two JSON files, deleting
> twenty registration lines, and changing one line of Python. `A1 config-first` does exactly that
> and ships no new machinery at all. Dressing a JSON edit as an architecture inflates its scope,
> its review cost, and its blast radius for zero additional capability.
>
> **Which leaves GW-3, the only net-new thing — and GW-3 is a scheduler.** The moment `admit()`
> acquires the things a real program needs (retry on failure, backoff, a run ledger, "which wave
> am I in", process supervision, resumability across a crash) it *is* a durable-execution engine.
> The anchor explicitly rejects "a durable-execution engine" and the spec explicitly forbids
> creating a duplicate control plane. So the candidate's one original component is on a direct
> path to anchor rejection, and its stated benefit — 4.6× resident-byte reduction on a 5 MB file —
> is a rounding error that would embarrass anyone who cited it in a design review.
>
> **And the concentration risk is not theoretical here.** This estate has *measured* the exact
> failure a gateway makes cheaper: a check went silent for weeks; the only signal was a `DISARMED`
> banner; the banner was then removed; the test suite stayed green throughout. The candidate's
> answer is a typed status field — a field that the same organisation, on the same code, already
> deleted once. Putting 27 checks behind one door and trusting a convention that has already been
> broken is not a mitigation. It is the same bet at higher stakes.

### 7.2 Does it land? Partly — and I am revising the claim, not defending it

**It lands on the framing, and I concede that fully.** The three sub-claims are all factually
correct against my own measurements: GW-2 is a sibling's work (§0 says so), GW-4 is the status quo
(§1.2 measures it), and GW-1's defects are JSON-editable (§5 Stages 1-4 are literally file edits).
So the honest scope of this candidate is **not** "a new architecture". It is:

> **a formalization of a pattern the platform already runs in three places, plus two enforcement
> artifacts (`gateway_invariants.py`, the typed-status field) and one new pure function
> (`unit_gateway.admit`).**

That is a smaller claim than the candidate's own framing, and per the program's own standard an
overclaim is a defect even when the mechanism is sound. I am recording the wider wording as
**REFUTED** and the scoped wording as what should be judged. Confidence *almost certain* (90-99).

Two things follow that strengthen rather than weaken the entry. First, "it is already the pattern
in three of four places" is the best possible evidence that the pattern *works here* — the
tournament's job is to pick an architecture, and an architecture with three shipped instances and
one gap is a better bet than one with zero instances. Second, "the defects are JSON-editable" is
true of the *edits* and false of the *enforcement*: nothing today stops `settings.json` drifting
back to 41 registrations, and that is exactly what `gateway_invariants.py` is for. A1 config-first
fixes the values; this candidate fixes the values **and** makes the fix falsifiable. The
distinction is small and I will not inflate it.

**The scheduler objection lands hardest, and it does not kill the design — it fences it.** I accept
the boundary as a hard, testable constraint rather than an aspiration:

> `unit_gateway.admit()` is a **pure function**. It MUST NOT persist state, MUST NOT retry, MUST
> NOT spawn or supervise a process, MUST NOT own a loop, and MUST NOT write any file. Its only
> inputs are on-disk artifacts (catalog, receipts, two indexes) and its only output is a set of
> ids. Enforced by `test_admit_is_pure`: assert no writes (filesystem sentinel), no `subprocess`/
> `os.exec`/`threading` import in the module's transitive own-code closure, and that two calls with
> identical on-disk state return identical sets.

With that fence, `admit()` is an **index over receipts**, not a runtime — the same category as
`ARTIFACT-CLASS-REGISTRY.json`, which the anchor already accepts. Cross the fence and the objection
becomes correct and the candidate should lose. I would rather state the failure condition than argue
it away. **UNVERIFIED**: whether a real 2,007-unit program can be driven by a *pure* admission
function with the loop living in the existing workflow layer. Settling experiment: drive one
19-layer dry run where `admit()` is called once per wave by an existing `workflows/` script and
measure whether any state the loop needs is unavailable from receipts on disk. Confidence *roughly
even* (40-60) that no persistence sneaks in — and that honest uncertainty is the single biggest risk
in this entry.

**And I concede the byte number outright.** 4.6× on 5 MB is not a reason to build anything. §2.2
leads with admission correctness and the 699.7 h serial floor instead, because those are the real
stakes. Anyone who reads GW-3's value as memory savings has read it wrong, and the original framing
invited that misreading.

**The concentration/fail-open argument is the one I rate highest and can least fully answer.** It is
doc-13's own strongest-against (`:454-458`) and my §3-F1. The counter-evidence is uncomfortable:
the mitigation is a typed field, and this estate deleted that exact field once, with a green suite.
So the mitigation cannot be the field — it has to be the **test** that the field is emitted (F1b,
§6.2), plus fail-closed on the blocking subset (§4.2), plus keeping `deny.py` outside the door
entirely (§4.1). If the judge panel does not accept a test as sufficient protection for a
convention that has already been broken once, then `A10 falsification-plane` or `A7 security-first`
should beat this candidate on the safety axis, and I would not argue. Confidence *likely* (55-80)
that F1b + fail-closed + carve-out is adequate; the settling experiment is a deliberate regression:
delete the `NOT-CHECKED` emission on a branch and confirm the suite goes red.

### 7.3 Evidence that would make a different candidate win

- If per-row wall-time telemetry shows the batteries are nowhere near their caps — i.e. the
  uncostable-budget problem was a duplicate-guard problem only — GW-1's main benefit evaporates and
  **A1 config-first** wins on simplicity. This is doc-13's own stated kill condition and it remains
  unrun. **UNVERIFIED**; settling experiment: one session of per-row telemetry against the declared
  caps.
- If a dry run shows `admit()` cannot stay pure (§7.2), **A5-compliant distributed-runtime** owns
  that surface honestly and this candidate should cede GW-3 to it and shrink to GW-1 only.
- If the panel weights fail-open concentration above budget legibility, **A10** or a
  security-first entry wins the safety axis.

---

## 8. Residual, stated plainly

- Wave 1's substrate closure is **uncommitted** (233 + 4 files untracked, two independent signals).
  Stage 0 blocks everything.
- The force-push guard's current registration site is **UNVERIFIED** (§4.1). If it is a manifest
  row, that is a live defect predating this candidate.
- Which of the 44 non-manifest `hooks/` directories are live is **UNVERIFIED** (§1.2).
- `admit()` purity under real program load is **UNVERIFIED** and is this entry's largest risk (§7.2).
- I did not re-run the 475-test suite; I cite 214 test functions as my own signal (§6.5).
- **My own detector failed twice during this pass and the control caught it both times.** First: I
  counted `timeout` and got 0 numeric values, concluding the catalog declares no per-unit timeout —
  wrong; the field is `timeout_seconds`, present as an `int` on all 2,007 units, summing to 2,291.0 h.
  Second: I reported 1,045 "dangling" dependency refs before resolving them against
  `PHASE-GRAPH.json`, where 13 of the 17 tokens are declared allocation buckets and the remaining 4
  are family prefixes accounting for exactly the brief's 41. Both numbers would have been confident
  and false, and the second would have manufactured a P1 that does not exist. Every count in this
  document that a control did not cover should be read with that in mind.

**Independent corroboration ledger** — where my numbers were reproduced by a mechanically different
route, and where they were not:

| number | my probe | independent signal | verdict |
|---|---|---|---|
| 2,007 units, 4 substrates (784/565/456/202) | `_probe_gwlazy_inventory` | `A5-R` lane, same counts | CONFIRMED |
| layer-0 frontier 489, depth 19 | `_probe_gwlazy_frontier` | `A5-R` lane `_probe_dr_acyclic.py` G1: 489 / 19 | CONFIRMED |
| 2,644 unit-id edges | `_probe_gwlazy_depns` | `A5-R` lane G1 edge count 2,644 | CONFIRMED |
| 1,004 bucket edges | `_probe_gwlazy_depns` | `A5-R` lane bucket-edge count 1,004 | CONFIRMED |
| 41 family edges | `_probe_gwlazy_depns` | the spawn brief's "41 unresolvable dependency refs" | CONFIRMED, and now identified |
| 475 tests | not run by me | `A5-R` lane `pytest --collect-only` → 475 collected; my 214 test functions × 2.2 | CONFIRMED by two others, not by me |
| INV-GW-1 6 violations / INV-GW-2 4 violations | `_probe_gwlazy_invariant` (both-states controlled) | none | NOT-CHECKED by a second party |
| 699.7 h `local-serialized` serial floor | `timeout_seconds` sum by substrate | none | NOT-CHECKED by a second party |
| 233 + 4 untracked substrate files | `git ls-files` = 0 **and** `git status -uall` = 233 `??` | two independent git signals | CONFIRMED |

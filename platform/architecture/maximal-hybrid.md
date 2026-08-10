# Architecture Candidate: MAXIMAL HYBRID (A9)

**Advocate's brief.** Phase 3 architecture tournament. I argue for this one and I expose its real
costs. Spec: `_USER-PROMPTS.md:10769-10796`. Prior design consumed, not redesigned:
`13-ARCHITECTURE-CANDIDATES.md:763-833` (A9), `:117-139` (anchor gate), `:1005-1336` (MECH-NN).

**Measured at**: working tree of `C:/Users/Prekzursil/source/ast-integrate`, HEAD `edcf9f5b`.
The brief pinned `dc90d64a`; the tree has advanced 3+ commits since (`edcf9f5b`, `9f2dac7a`,
`b68815fd`). Every number below is re-measured at `edcf9f5b`, not inherited.

---

## 0. What this architecture discards from Wave 1: NOTHING. Counted.

The spec requires an architecture that silently discards Wave 1 to say so in its first paragraph.
This one discards nothing, and here is the count rather than the assurance.

| | files | disposition |
|---|---|---|
| `platform/` tracked | **272** | REUSE unmodified |
| `command-center/` tracked | **75** | REUSE unmodified |
| **Wave 1 total tracked** | **347** | **REPLACE: 0. DELETE: 0.** |
| whole repo tracked | **8,244** | untouched outside the 347 |
| `command-center/schema/` (233 shims + `_meta`) | **233, all untracked** | RE-CLASSIFIED as derived, not replaced |

`git ls-files platform command-center | wc -l` → 347. The architecture adds a spec file, three
emitters and one gate (§5); it rewrites none of the 347. Its *only* destructive act is a
reclassification: the 233-file shim tree stops being an artifact and becomes declared build output.
Zero bytes are deleted by that change — the files stay, their *status* changes.

Reuse in detail, all re-measured: **9** schema documents in `platform/schema/` of which **9**
declare `$schema` and **9** compile under `jsonschema.Draft202012Validator.check_schema`
(the brief said 8; the 9th is `artifact-class-profiles.schema.json`, added by the substrate unit) ·
**4** lib packages (`wfdsl` 14 py, `councilspec` 10, `council_protocols` 7, `workflows` 26) plus
**3** top-level modules (`completion_predicate.py`, `receipt_schema_gate.py`, `schema_resolver.py`) ·
**48** protocol + **69** preset `.councilspec.json` · **164** registry candidates across 5 slice
files (the brief said 161 — see §8-D) · **2,007** catalogued work units.

---

## 1. Design

### 1.1 The one idea, stated once

**Many logical names, few physical definitions, exactly one writer per projection.**

That is not an aspiration in this repo — it is already running, and it is the only Wave 1 mechanism
that closed a P1. `platform/lib/schema_resolver.py --audit` reports today:

```
"references_resolving": 2007,  "references_unresolved": 0,
"distinct_logical_files": 234, "distinct_logical_files_resolving": 234,
"physical_control_plane": [
  "command-center/schema/_meta/json-schema-2020-12.json",
  "platform/schema/artifact-class-profiles.schema.json",
  "platform/schema/receipt.schema.json" ]
```

**234 logical names → 3 physical definitions.** A 78:1 collapse. I measured the projection layer
independently: 233 JSON files under `command-center/schema/`, of which **229 are byte-shaped
identically** (top-key set `$comment|$id|$ref|$schema|title|x-artifact-class|
x-catalog-reference-count|x-catalog-sample-units|x-generated-by|x-physical-definition`), median
**1,057 B**, and **276 of their `$ref`s point at one file** (`artifact-class-profiles.schema.json`).
They are pure aliases: `platform/lib/test_schema_resolver.py:209-228`
(`test_shims_carry_no_constraints`) enforces that a shim may only `$ref`, with the comment *"A
constraint in a shim is a second control plane."*

The maximal hybrid is that pattern **generalised from schemas to every remaining control plane in
this repo**, and nothing more exotic than that.

### 1.2 The control planes as they actually exist today

Not generic boxes. These are the real files, with their real writers as measured.

| # | plane | authored artifact (real path) | reader | genuine writers | derived output committed? |
|---|---|---|---|---|---|
| P1 | receipt/artifact contracts | `platform/schema/receipt.schema.json` (39 `$defs`), `artifact-class-profiles.schema.json` (**295** `$defs`) | `schema_resolver.py` | **1** — `platform/lib/_gen_schema_substrate.py` | **NO** — 233 untracked |
| P2 | work units | `command-center/WORK-UNIT-CATALOG.json` (2,007 units, 25 keys/unit) | `wfdsl/`, `completion_predicate.py` | hand-authored, **0** generators | tracked |
| P3 | councils | `platform/council/protocols/*` (48) + `presets/*` (69) | `platform/lib/councilspec/validate.py` | **4** — `_build_p01_p12.py:4581`, `_gen_protocols_37_48.py:4280`, `_gen_skeletons.py:71`, `build_protocols.py:4478` | **YES** — 52+90 tracked |
| P4 | workflow DSL / blueprints | `platform/schema/workflow-dsl.schema.json` + `platform/workflows/*.json` | `platform/lib/wfdsl/` | several (`_gen_bp3_b.py`, `_gen_bp3_c.py`, `bp1_build.py`, …) | **BOTH** — some tracked, 112 untracked |
| P5 | hook registrations | `hooks/_dispatch/manifest.json` | `hooks/_dispatch/dispatch.py` | hand-authored, **0** generators; `ci/emit_hook_manifest.py` is a **read-only** projector (stdout + `--check`) | tracked |
| P6 | completion gate | `platform/lib/completion_predicate.py` (12 conditions) | `receipt_schema_gate.py` | 1 | code |

**The genuine defect is not "too many writers". It is that the repo answers the same question three
different ways.** P1 generates 233 files and commits **none**. P3 generates 117 files and commits
**all**. P4 does both at once. Same repo, same week, three incompatible policies on whether derived
state is tracked — and *that* is what fails the spec's "singular and understandable" test, far more
than any writer count. A consumer cannot tell by looking at a file whether it is authored or derived.

**P1 is solved. P2 and P5 are hand-authored with no generator. P3 is the multi-writer plane.** A
hybrid is the only candidate shaped to address planes at *different maturities* simultaneously — A1
(config-first) would have to *delete* P1's win to reach its minimalism, and A2 (pure generated-SSOT)
would have to re-derive the 2,007 hand-authored units it cannot yet express.

*(Correction, disclosed: an earlier draft of this table claimed P5 had "12 non-test writers" and
called it "the disaster". That was my own use-vs-mention detector failure — see §8-D item 3. The
figure is withdrawn; P5 has zero generators.)*

### 1.3 What gets built

The architecture is **one policy plus one gate**, not a new spec language. Concretely:

**A single derived-state policy, applied to all six planes.** Every generated path is either
(a) untracked + regenerated by CI, or (b) tracked + guarded by an `emit --check` gate. Pick one per
plane, declare it in one file, and make the choice *visible in the file itself* via the
`x-generated-by` marker the 229 shims already carry. Today P1 is (a)-without-CI, P3 is
(b)-without-a-gate, P4 is neither.

**One projector per plane, in the shape that already exists twice.** The pattern is not hypothetical:
- `platform/lib/_gen_schema_substrate.py` — the single writer of 233 projections, verified to revert
  hand-edits (§3-F1).
- `ci/emit_hook_manifest.py` — **already read-only by design**: `--emit` renders to stdout, `--check`
  compares a source file against its canonical rendering after normalising line endings
  (`ci/emit_hook_manifest.py:7, :117, :144`), with a test at `ci/tests/test_emit_hook_manifest.py`.
  This is precisely the `--check` discipline the architecture needs, already built for one plane.

So the build is: **lift `emit_hook_manifest.py`'s `--check` contract into a shared helper and give it
to P1, P3 and P4.** P3's four emitters consolidate to one behind it; P1 gains the CI regeneration it
lacks; P4 gains a policy at all.

**One read path per plane**, already the shape of `schema_resolver.py`: no consumer opens a
projection directly; it asks the resolver for a logical name. This is what makes the 78:1 collapse
invisible to 2,007 callers.

**One falsification plane** (A10, folded in as the acceptance criterion rather than a component):
every projection has a `--check` mode that regenerates into a temp tree and byte-diffs against
disk. Non-zero exit = drift. This is the single gate the whole architecture stands on, and §8 is
about the fact that it does not exist yet.

**Councils and verification stay in the skill layer** (A7), invoked on demand, never on the hook
path — so they add no control plane. `platform/lib/councilspec/` (112 tests) and the 117 specs are
consumed as *data*, not wired as runtime.

**A5/A6 stay strictly offline.** The foundry and the resume convention never touch `dispatch.py`.
This is the clause that keeps the anchor gate at PASS: no second orchestration runtime, no
durable-execution engine, no vector store, no trained critic, no observability SaaS
(`13-ARCHITECTURE-CANDIDATES.md:117-139`).

### 1.4 The invariant, stated so it can be falsified

> For every generated path G, exactly one tracked script writes G, `G ∉ git ls-files`, and
> `emit --check` exits non-zero if G on disk differs from a fresh emission.

Three clauses, each mechanically checkable. §8 is my argument that clause 3 is the only thing
standing between this architecture and the four-control-plane estate it claims to prevent.

---

## 2. Cost and complexity analysis

**Net new code**: 1 shared `--check` helper + 1 CI gate + 1 policy declaration. The projectors already
exist (`_gen_schema_substrate.py`, `ci/emit_hook_manifest.py`, `ci/gen_hooks.py`), and one of them
already implements the exact contract to be generalised. Order **10²** lines, not 10⁴. This is the
cheapest candidate in the tournament *because* it refuses to author a new spec language.

**Net deleted code**: consolidating P3's 4 genuine emitters → 1 is a real reduction. I measured **46
writer-candidate scripts** repo-wide matching `gen_*|emit_*|sync*|install*|deploy*|build*`; the
architecture does not add to that number. It does **not** claim a reduction at P5, which has zero
generators to consolidate.

**The real cost is a new critical path.** Today a bug in `_gen_schema_substrate.py` corrupts 233
files in one run. I verified the blast radius empirically rather than asserting it: I hand-edited
`command-center/schema/adjudication-record.schema.json`, ran the generator, and it reverted the file
to canonical bytes (`generator_reverted_to_canonical: true`). That is the mechanism working — and it
is *also* the failure mode, because the same authority that heals drift can propagate a defect to
233 files with no per-file review. Extending this to P5 puts hook registrations behind the same
single point.

**Complexity that is genuinely added**, honestly:

1. **A build step becomes mandatory before the tree is usable.** Measured: `git ls-files
   command-center/schema | wc -l` → **0**; `git status --porcelain -uall` → **233 `??`**;
   `git cat-file -e HEAD:command-center/schema/adjudication-record.schema.json` → *"exists on disk,
   but not in 'HEAD'"*; `git check-ignore` → not ignored. So a fresh clone has **0 of 234** logical
   schemas and **2,007 references resolve to nothing** until someone runs the generator. That is the
   cost of derived state, and it is currently unpaid and undeclared.
2. **Two `$id` namespaces already in use** across the 9 schemas —
   `https://ast-integrate.invalid/platform/schema/...` (artifact-class-profiles,
   completion-predicate-result, receipt) vs `https://schema.ast-integrate.local/...` (councilspec,
   work-unit ×3, work-unit-catalog). A resolver keyed on `$id` inherits that split. Unifying it is
   cheap now and expensive after more consumers bind.
3. **Understandability cost, which the spec explicitly prices.** The admission criterion is that
   control planes stay *"singular and understandable"*. 3 physical planes is singular. But a
   newcomer reading `command-center/schema/adjudication-record.schema.json` sees a 1 KB file whose
   real content lives in a 190 KB file behind a `$ref` — and 229 files share that shape. The
   indirection is cheap for machines and not free for humans.

**Cost NOT incurred**: no new runtime, no daemon, no service, no network dependency. The resolver
already refuses egress and path escape — `test_retrieval_refuses_the_network`,
`test_retrieval_refuses_path_escape` (`test_schema_resolver.py:129,134`).

---

## 3. Failure-mode analysis

Each mode below is measured, with the probe named. I ran a both-states probe
(`platform/architecture/_mh_probe_drift.py`, output `_mh_probe_drift.out.json`) that restored every
byte it touched and proved restoration via `git status` before exiting (`restored_clean: true`).

**F1 — CONFIRMED, and it is the worst one: a hand-edit that adds no constraint is neither caught
nor reported, and the test suite silently destroys the evidence.**
I set `x-catalog-reference-count: 999999` in a shim — a value that is *wrong* but violates no
allowed-key rule — then ran four resolver tests including `test_generator_is_deterministic`:

```
state=BROKEN-silent-annotation-edit   exit=0   fired=false
file_reverted_by_suite_side_effect: true
```

Exit 0, no failure, **and the file came back canonical** because the test invokes the generator,
which rewrote it. So running the suite *repaired the tree and reported nothing*. A drifted
projection is indistinguishable from a clean one, which is precisely the untyped-silence class
`13-ARCHITECTURE-CANDIDATES.md:§0.1` names as the estate's dominant failure. Detector control: the
same probe in the GOOD state passed (exit 0), and a *constraint*-bearing edit (`minProperties`) DID
fire (`exit=1`, `constraint_edit_CAUGHT: true`) — so the detector is live, and its silence on the
annotation case is a real gap, not a broken probe.

**F2 — CONFIRMED: the determinism gate samples 4 of 235 generated artifacts.**
`test_generator_is_deterministic` (`test_schema_resolver.py:281-301`) snapshots exactly four paths
(`artifact-class-profiles.schema.json`, `ARTIFACT-CLASS-REGISTRY.json`,
`command-center/schema/receipt.schema.json`, `audit-finding.schema.json`), runs the generator, and
asserts none changed. Coverage: **4/235 = 1.7%**. My target file was deliberately not one of the
four (`target_is_one_of_the_4_sampled: false`). The gate is the right shape and the wrong size.

**F3 — CONFIRMED: derived state is untracked, so the P1 closure exists only in this working tree.**
Four independent signals in §2.1. This is not a defect in the substrate unit's work — derived state
*should not* be committed under this architecture — but it is currently neither committed nor
declared nor regenerated by CI, which is the one combination that is strictly worse than either
choice.

**F4 — CONFIRMED: the test suite's own collection set is not stable, so no test-count claim about
this tree is citable.** Three consecutive runs of the identical command
(`cd platform/lib && python -m pytest -q --no-header`):

| run | collected | passed | failed | skipped |
|---|---|---|---|---|
| 1 | 818 | 816 | 2 | 0 |
| 2 | 1,254 | 1,251 | 3 | 0 |
| 3 | 1,912 | 1,885 | 13 | 14 |

*Attribution, stated as a band rather than asserted*: **likely (55-80%) concurrent sibling agents
writing into this shared tree**, not the suite mutating its own collection. Supporting evidence —
307 untracked files under `platform/`, 112 untracked `.json` in `platform/workflows/`, and the
newest of them are blueprint workflow documents of exactly the kind a sibling unit emits; three
named agents are active in this session. **UNVERIFIED** which agent wrote them; the settling
experiment is a `git stash`-free snapshot of `platform/workflows/` mtimes taken twice 60 s apart
with no local run in between — growth with my process idle proves external authorship. I did not
run it because it costs a minute of wall-clock during which siblings are mid-write, and the
architectural consequence is identical either way (§6.4).

The consequence is load-bearing and I will state it plainly: **the substrate sibling's "475 passed"
and my own "816/1251/1885" are measurements of different suites.** None is wrong; none is a stable
gate. A shared mutable tree cannot produce a reproducible test verdict.

**F5 — CONFIRMED, and it is a fixer committing its own defect class.** `dependencies` carries three
namespaces with no discriminator, over 3,689 total refs: **2,644** resolve to a unit id, **1,004**
are bucket labels `Bnn`, **41** are bare family tokens. The catalog's own
`work_units_meta.known_defects_at_merge.unknown_form_dependency_refs` says **41** — my independent
count agrees exactly. But `post_merge_fixes_20260809.unknown_token_forms_normalised` claims those 41
tokens were *normalised* from `BKT-ARC, BKT-CMD, BKT-IMP, WFA-1of2`, and my probe finds the residue
is `ARC, CC, IMP, WFA` — bare prefixes. **The normalisation stripped the `BKT-` namespace marker and
left a token that resolves to nothing, where the original at least declared which namespace it
meant.** The fix made the reference strictly less resolvable while the defect count stayed at 41.
Also measured: `bucket_labels_covered_by_meta: 0` — the 1,004 `Bnn` labels are not defined in
`work_units_meta`.

**F6 — CONFIRMED: `spec_anchor` is required by the receipt but present on 160 of 2,007 units.**
`receipt.schema.json` `$defs.receipt_core.required` includes `spec_anchor`, with
`additionalProperties: false`. The catalog supplies it on **160** units (**7.97%**). So 1,847 units
must synthesise a value at receipt-emission time from a source the catalog does not name. One of the
160 is itself compound: `_USER-PROMPTS.md:10836, 11347`.

**F7 — the shared-directory allocation failure, and it reproduced in all three runs.** The only test
that failed in every one of my three runs is
`workflows/test_bp5_slice.py::test_flagship_blueprints_each_have_a_dedicated_test_file` — 7 flagship
blueprints declared with no dedicated test file. Runs 2 and 3 add
`test_bp4_blueprint_set.py::test_no_id_collides_with_another_range_in_the_shared_directory`. Both
failures are the same shape: **many writers into one shared directory with no allocation authority.**
That is the argument for this architecture, produced by the repo itself, unprompted.

---

## 4. Security review

**S1 — the untracked derived tree is an unsigned, unreviewed supply chain.** 233 files that every
receipt validation depends on are absent from git, so they carry no blame, no review, no signature,
and no diff. An edit to one of them is invisible to `git status` at directory granularity
(`?? command-center/schema/` — one line for 233 files; only `-uall` reveals the count, the exact
collapsed-untracked trap). Under this architecture the mitigation is structural: derived files are
regenerated in CI from a tracked generator and never trusted from disk.

**S2 — deny-by-default is present and I did not have to add it.** Units carry a `tool_permissions`
field, and `workflows/test_bp5_slice.py::test_deny_by_default_tool_policy_and_no_secret_values`
exists and **passes in isolation** (`1 passed in 0.91s`). It appeared as a failure in run 1 and not
in runs 2-3 — consistent with F4's shared-tree instability, so I record it as **NOT-CHECKED under
concurrency** rather than claiming either verdict.

**S3 — the resolver's egress and traversal refusals are real, tested, and must be inherited by every
new emitter.** `test_retrieval_refuses_the_network` and `test_retrieval_refuses_path_escape` exist
today (`test_schema_resolver.py:129,134`), and `meta_schema_url_is_offline_and_real` (`:139`) proves
the one `https://json-schema.org/...` reference in the catalog is served from a committed local
mirror rather than fetched. That is the correct pattern and the architecture's `--check` modes must
not regress it by shelling out.

**S4 — 21 units declare an `output_schema` that is a bare URL.** Measured: `is_url: 21`. One is
handled by the offline meta-schema alias. The other 20 are a fetch-shaped instruction sitting in a
data field, and per AGENTS.md §9 fetched content is untrusted data. The architecture forbids a
URL-shaped `output_schema` in the spec grammar: it must be a logical name the resolver can pin to a
committed byte range.

**S5 — the security-bearing plane is safer than I first claimed, and the residual risk is different.**
`hooks/_dispatch/manifest.json` is **tracked** and has **zero** generators, so no script can silently
drop a guard; a dropped registration shows up as a reviewable diff. (My earlier "12 writers" figure
was a detector failure — §8-D item 3.) The real residual is that **nothing makes a `security: true`
registration structurally undroppable by a *human* edit**: there is no schema requiring its presence.
So the architecture's A9 clause survives, restated correctly — enforce the security registrations as a
`required`/`minContains` constraint in a manifest schema, so a hand-edit that removes one fails a
gate rather than merely looking wrong in review. That is a smaller and cheaper fix than consolidating
writers, because there are no writers to consolidate.

**No credential was read, printed, or modified in producing this document.**

---

## 5. Migration design from today's measured state

Staged, each stage gated on the previous stage's both-states test going green. Stage names follow
A9 (`13-ARCHITECTURE-CANDIDATES.md:797-806`); the content is re-derived for this repo.

**S0 — declare the derived tree (hours, 0 new control planes).** Add `command-center/schema/` to
`.gitignore` *and* add `emit --check` to CI. Both, or neither: ignoring without regenerating turns
F3 from "undeclared" into "silently absent". Known-broken state its gate must fire on: a fresh clone
with no generator run must FAIL the schema audit, loudly, instead of reporting 2,007 unresolved as a
crash. **Rollback**: delete two lines.

**S1 — widen the determinism gate from 4 files to all 235 (hours).** Replace the four-path snapshot
in `test_generator_is_deterministic` with a full-tree hash-manifest compare, and make it *report*
before it *repairs* — the F1 finding is that the current order silently heals. Known-broken state:
the exact `x-catalog-reference-count: 999999` edit my probe used, which today exits 0.
**This is the single highest-value stage in the whole plan and it is a few hours of work.**

**S2 — one derived-state policy across P1/P3/P4, and a manifest schema for P5 (days). This is the gate
for everything else.** Two sub-steps: (i) declare per plane whether generated output is tracked, and
make P3's 117 tracked specs and P1's 233 untracked shims obey the *same* rule; (ii) add a schema for
`hooks/_dispatch/manifest.json` that makes `security: true` registrations structurally required.
Known-broken state for (i): a tracked generated file that differs from a fresh emission must fail.
For (ii): a manifest with a security registration deleted must fail. **Note the re-scope** — an
earlier draft made this stage "reduce 12 manifest writers to 1"; there are no such writers, so the
stage is smaller and lower-risk than I originally costed it.

**S3 — unify the two `$id` namespaces (hours).** Mechanical, and cheapest now.

**S4 — P2 typing: give `dependencies` a namespace discriminator and `output_schema` a grammar
(days).** Fixes F5 and S4. Known-broken state: the bare token `ARC` must be rejected, and `BKT-ARC`
must resolve — i.e. the *un*-normalisation is part of the fix.

**S5 — councils 4 emitters → 1 (days).** Lowest risk, lowest urgency; 117 specs already validate on
both layers.

**Explicitly deferred**: P4 workflow-DSL consolidation, and any marketplace/plugin layout (A3 stays
a later option, never a prerequisite — A9's loader-agnostic clause). Release mode is PR-ONLY per the
binding owner decision, so "canary" here means a merged PR plus a local rollback rehearsal, and I
say so rather than claiming a release gate I cannot run.

---

## 6. Test design

**6.1 Every gate must fire in the known-broken state before its silence counts.** Not a slogan — my
own probe found the live gate silent in one of two broken states. Each stage in §5 names its
known-broken state above; the test that ships with it must be shown red on that state first.

**6.2 Replace sampling with a manifest.** The 4/235 sample (F2) becomes: emit to a temp tree, hash
every file, compare the sorted `(path, sha256)` list to disk. One assertion, total coverage, and it
cannot silently repair because it never writes to the real tree.

**6.3 Mechanical questions get algorithms, not judgement.** All four defect classes in this document
are set-membership and counting problems. I re-derived each with an exact algorithm and my first
attempt at one of them was wrong (§8-D) — the fix was a better algorithm, never an opinion.

**6.4 Isolation is a test-design requirement, not a nicety.** F4 shows a shared mutable tree yielding
818/1254/1912 collected from one command. Under this architecture the projection gate runs against a
temp tree, so its verdict is independent of sibling writes. That property is why I can still cite the
resolver audit (it reads 3 physical files) while refusing to cite any total test count.

**6.5 Mutation-test the completion predicate against the *new* planes.** `completion_predicate.py`
has a 12-condition gate with a 12/12-killed mutation battery. Extending the architecture to P5 means
the predicate now sees registration receipts; the battery must be re-run against those, not assumed
to transfer.

**6.6 What I did not test.** I ran no end-to-end emission for P5 or P3 — those emitters do not have
`--check` modes yet, so there is nothing to run. **NOT-CHECKED**, and the settling experiment is
stage S1's manifest gate applied to a P5 dry run.

---

## 7. Anchor compliance

`13-ARCHITECTURE-CANDIDATES.md:117-139` gates every candidate on (a) riding the existing
hook/skill/MCP bus and (b) reintroducing none of six rejected components.

Rides the existing bus: yes — `hooks/_dispatch/dispatch.py` stays the only runtime entry; councils
are skill-layer data; the resolver is a library, not a service. Reintroduces: no second orchestration
runtime (A5/A6 are offline-only by the §1.3 clause), no vector-DB/KG memory (the resolver is a
build-time index with no runtime store), no durable-execution engine, no trained critic (councils are
prompt-shaped + a deterministic gate), no observability SaaS, no guardrail framework. **PASS**, on
the same reading that gave A9 PASS in the source document.

---

## 8. The strongest adversarial refutation of my own architecture

This is the section that matters. Below is the argument I would use to kill this design, made as
well as I can make it, followed by whether it succeeds.

### 8-A. The argument that would kill it

**"Maximal hybrid" is not a design. It is a description of the estate's present accumulated state
with a promise stapled to the front, and this program has already measured the promise failing.**

The architecture rests on exactly one load-bearing clause: *exactly one thing may write a
projection*. Strip that clause and A9 is indistinguishable from the four-control-plane drift that
`00-INVENTORY §5.1` counts and that this program exists to clean up. So the whole candidate reduces
to: **is that clause enforceable here?** The evidence I gathered says no, and worse, it says the
clause is *already violated* in the plane that matters most, by the very unit that most recently
succeeded:

1. **~~The clause is false today, 12 ways, in the security-bearing plane.~~ WITHDRAWN — this was my
   strongest point and it was false.** I measured 12 non-test writers of `hooks/_dispatch/manifest.json`
   with a detector that counted docstring mentions (§8-D item 3). The truth: the manifest is tracked,
   has **zero** generators, and `ci/emit_hook_manifest.py` is read-only by design. Losing this point
   weakens the attack — and it also removes a chunk of the architecture's original justification, so
   it cuts both ways and I am recording both directions. What survives in its place is narrower and
   still real: **no schema makes a `security: true` registration undroppable by a hand-edit.**
2. **The clause was violated inside this program, days ago, by a successful unit.** The substrate
   sibling closed P1 correctly and left 233 untracked derived files with no `.gitignore` entry and no
   CI regeneration. Nobody chose that; it is what happens by default.
3. **The only gate that could enforce the clause covers 1.7% of the surface and silently repairs the
   drift it fails to report.** I measured this directly. A gate that heals-without-reporting is worse
   than no gate, because it manufactures a clean tree that never existed and erases the evidence.
4. **The estate's own history says hybrids are how this happened.** A9's source text concedes it:
   *"Hybrid plans are how estates acquire five control surfaces — `00-INVENTORY §5.1` already counts
   four registration channels, and every one of them arrived as a reasonable stage of some earlier
   hybrid"* (`13-ARCHITECTURE-CANDIDATES.md:825-829`). Every one of those four was somebody's
   defensible S3.
5. **And the killer generalisation**: the spec admits a hybrid winner *only when its control planes
   remain singular and understandable*. "Singular" is a property of the **write** surface, not the
   read surface. My 78:1 collapse is a *read*-side triumph and says nothing about writers. I have
   been quoting my strongest number as though it answered the admission criterion, **and it does
   not.** On the criterion actually written, this architecture is currently **not admissible**, and I
   should say so before a judge panel says it for me.

### 8-B. Does it succeed? Partially — and I am revising the claim, not defending it.

**It kills the "maximal" framing. It does not kill the mechanism.** Specifically:

- **CONCEDED, fully**: this architecture is *not admissible as written today*. Clause 3 of my own
  §1.4 invariant does not exist. Until the S1 manifest gate ships, "maximal hybrid" describes an
  aspiration, and presenting it as a design would be exactly the overclaim pattern that accounted
  for 5 of 8 refutations in this program's prior waves.
- **CONCEDED**: my headline 234→3 collapse is read-side and does not speak to the admission
  criterion. I led with it in §1.1 and that was the wrong emphasis. The honest headline is: *one
  plane out of six has a single writer; the architecture's job is the other five.*
- **CONCEDED, and this one hurts**: withdrawing point 1 also withdraws part of the architecture's
  *justification*. "Consolidate 12 writers" was a headline benefit and it does not exist. The honest
  benefit is smaller: one derived-state policy where there are currently three, plus one
  `--check` contract generalised from a plane that already has it. That is a real but modest win, and
  a judge should price it as modest.
- **NOT conceded**: the mechanism is proven in-repo, not hypothesised. 2,007 references, 0
  unresolved, 3 physical files, and a generator that demonstrably reverts hand-edits
  (`generator_reverted_to_canonical: true`). No other candidate in this tournament has a closed P1
  behind it. A1 would have to delete that; A2 would have to re-derive 2,007 hand-authored units it
  cannot express.
- **NOT conceded**: the strongest *surviving* evidence is the three-policies finding (§1.2), which is
  not a writer-count claim at all and is therefore untouched by my detector failure. P1 commits 0 of
  233 generated files; P3 commits 117 of 117; P4 does both. That is measured, reproducible from
  `git ls-files`, and it is exactly the "not understandable" failure the admission criterion names.
- **NOT conceded**: the refutation's own force argues *for* staging, not against it. Points 2-3 are
  discovered by the same class of gate that S1 builds — and S1 is **hours**, not a quarter. An
  argument whose evidence is "the gate is too small" is not an argument against the gate.

**The revised claim I will defend**: this is admissible **if and only if S0+S1 land before anything
else**, and it should be judged on that conditional, not on the full staged vision. If S1 cannot be
made to fire on the annotation-edit case, then per A9's own exit criterion
(`13-ARCHITECTURE-CANDIDATES.md:831-833`) this candidate should be **declared** as A2+A10 and the
hybrid abandoned — not carried forward as a partially-built hybrid, which is the precise state this
program was created to clean up. I am pre-committing to that declaration rather than leaving myself
room to relabel a failure as progress.

### 8-C. The second-strongest argument, which I think is wrong

*"3 physical planes is not singular; singular means 1."* I reject this. `_meta/json-schema-2020-12.json`
is a vendored upstream mirror, not an authored plane, and `receipt.schema.json` vs
`artifact-class-profiles.schema.json` is a genuine kind boundary (the receipt envelope vs the
per-artifact-class payload). Collapsing them would produce one 228 KB file with 334 `$defs` — worse
on the *understandable* half of the criterion. Two authored planes plus a vendored mirror is the
honest floor.

### 8-D. Where I was wrong while writing this, disclosed

**Three** of my own detectors failed, and all three would have produced confident false findings. Two
were caught by an independent tool disagreeing with me; the third was caught by a control I had built
into the replacement detector. None was caught by re-reading my own output:

1. **I invented 71 phantom missing schema files.** My first path probe split `output_schema` on `#`
   and treated the remainder as a path, so compound prose values like
   `"command-center/schema/receipt.schema.json (receipt) + tools/plugin/schema/payload-allowlist.schema.json
   (artifact authored here)"` became one nonexistent filename. It reported 305 distinct logical paths
   and 71 missing. `schema_resolver.py --audit` — a mechanically independent tool — reported 234 and
   0. **The resolver was right and I was wrong**; I rebuilt the probe with an explicit
   five-case detector control (`_mh_measure3.py`, `detector_control_all_ok: true`) before trusting any
   further count. Had I published the first number I would have "refuted" a P1 closure that is real.
2. **I briefly disagreed with the brief on 3 of its 4 defect counts, and the brief was right.** My
   counts (41 compound / 1,045 unresolvable deps / 0 sentinel / 448 vendor-role) looked like
   refutations. They were **definitional artifacts**. Once I measured each number under multiple
   candidate definitions (`_mh_measure5.py`), every brief figure reproduced exactly: **159** =
   `output_schema` containing `+`/`,`/`and`; **41** = dependency tokens of unknown *form* (matching
   the catalog's own `unknown_form_dependency_refs: 41`); **96** = sentinels not *starting with*
   `SUCCESS:<id>`; **128** = `assigned_model_vendor_role` values that are not dicts. All four
   **CONFIRMED**. The disagreement was mine.

3. **I fabricated a 12-writer crisis in the plane I called "the disaster", and it was the load-bearing
   evidence for my own strongest counterargument.** My writer detector asked: does this file contain
   the substring `_dispatch/manifest.json` *anywhere* AND a write verb *anywhere*? Three spot-checks
   killed it — `hooks/dark-surface/check.py:14`, `hooks/todo-surfacer/hook.py:6` and
   `hooks/journey-coverage/check.py:430` all mention the manifest **in a docstring** and separately
   call `json.dumps` for their own unrelated output. Use-vs-mention, in my own measuring tool, for the
   third time in this program's recorded history. I rebuilt it (`_mh_measure6.py`) requiring the write
   verb and the path to be co-located within 4 lines, with comment/docstring lines blanked, and
   **guarded it with a positive control** — and the rebuilt detector *refused to report counts* because
   its positive control (`ci/emit_hook_manifest.py`) did not fire. Chasing that refusal is what
   revealed the actual finding: that file is **read-only by design**, so it was never a valid positive
   control. The guard did its job; had I omitted it I would have shipped a second wrong number.
   Ground truth, established by direct inspection instead: the manifest is tracked
   (`git ls-files hooks/_dispatch/manifest.json`), and every non-test reference to it in the repo is
   prose. **Zero generators.**

The one number I do still report differently: **164 registry candidates, not 161** — 32+32+35+33+32
across the five slice files, excluding two `.COVERAGE`/`.METHOD` sidecars. My first attempt here also
failed (it read only dict-shaped files and reported 32, missing four bare-list files), so this count
is the *second* version. **Confidence: likely (55-80%)**, not certain — the residual is whether the
pinned 161 excludes three entries on a criterion I have not found. The settling experiment is a
diff of candidate `id`s against whatever produced the 161.

---

## 9. Verdict as advocate

**Recommend: admit conditionally, ranked on the conditional, and priced lower than my first draft
priced it.** The mechanism is the only one in this tournament with a measured P1 closure behind it
(2,007 refs, 0 unresolved, 234→3 collapse), and it discards none of Wave 1's 347 files. On the spec's
actual admission criterion — *singular and understandable* control planes — it is **not admissible
today**, for one reason that survived my own attack: the repo applies **three different derived-state
policies** across P1/P3/P4, so no reader can tell an authored file from a generated one. The enforcing
gate covers **4 of 235** artifacts and silently repairs rather than reports. S0+S1 are hours of work
and convert this from a promise into a checkable invariant. Judge it on whether those two stages land
first; if S1 cannot be made to fire on the annotation-edit case, declare this A2+A10 and drop the
hybrid.

**What I got wrong, stated where a judge will see it**: my first draft's headline justification
("consolidate 12 manifest writers") was a use-vs-mention detector artifact. P5 has zero generators.
The architecture is cheaper and less urgent than I first argued, and its benefit is narrower.

**Dissent to preserve**: the shared-tree instability in F4 (818→1254→1912 collected from one command)
means *no* candidate in this tournament can currently be evaluated on a test-count basis, mine
included. Any judge panel comparing candidates by suite health is comparing measurement noise.

---

### Artifacts backing this document

| probe | output | what it settles |
|---|---|---|
| `platform/architecture/_mh_measure.py` | `_mh_measure.out.json` | platform inventory, 9/9 schemas compile |
| `_mh_measure2.py` | `_mh_measure2.out.json` | registry list-shape fix; catalog surface |
| `_mh_measure3.py` | `_mh_measure3.out.json` | field-shape counts **with a 5-case detector control** |
| `_mh_measure4.py` | `_mh_measure4.out.json` | 46 writer candidates — **its "12 manifest writers" is REFUTED, do not cite** |
| `_mh_measure5.py` | `_mh_measure5.out.json` | reconciles all 4 brief defect numbers to their definitions |
| `_mh_measure6.py` | `_mh_measure6.out.json` | co-located writer detector; **withheld its own counts when its positive control failed** (exit 1) |
| `_mh_probe_drift.py` | `_mh_probe_drift.out.json` | **both-states** drift probe; `restored_clean: true` |

Reproduce the load-bearing claim:
`cd C:/Users/Prekzursil/source/ast-integrate && python platform/lib/schema_resolver.py --audit`
→ `references_unresolved: 0`, `distinct_logical_files: 234`, 3-entry `physical_control_plane`,
`SUCCESS:schema-resolver-audit`.

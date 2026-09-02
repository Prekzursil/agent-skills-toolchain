# DEFECT D1 — false green in completion-predicate condition 9 (cross-vendor reviewer)

Unit: `defect/d1-cross-vendor`. Baseline pinned by the program: platform suite 2,767 passed /
14 skipped / 0 failed — **that pin is STALE, see Q6.**

STATUS: **fix landed and measured.** Both layers changed, 63-pair table green, mutation proof
valid, full suite 3067 passed / 14 skipped / **0 failed**. Every claim below carries its own
verdict. If a claim reads `UNKNOWN - not yet measured`, the unit died before measuring it and that
claim may not be cited.

COVERAGE: Q1–Q12 all measured. Residual, disclosed inline: the suite count is a snapshot of a tree
under concurrent write by ~20 agents (Q6), and `cc-render drift=1` is a sibling's in-flight catalog
edit left deliberately unrepaired (Q12).

---

## Q1 — is the defect real, and how wide? CONFIRMED

Pre-fix probe, run against the tree before any edit:

```
$ python platform/architecture/_probe_crossvendor_alias_hole.py
"control_known_broken_identical_vendor": {"input": ["anthropic","anthropic"], "accepted": false, "control_passes": true}
"control_known_good_distinct_vendor":    {"input": ["anthropic","openai"],    "accepted": true,  "control_passes": true}
"detector_validated_both_states": true
"alias_pairs_tested": 10
"alias_pairs_that_DEFEAT_the_gate": 10
"alias_pairs_gate_held": []
"VERDICT": "CONFIRMED HOLE: 10/10 same-vendor alias pairs are accepted as cross-vendor.
            The gate is string-equality over an unvalidated free-text field."
```

The detector was valid in BOTH states before the finding was read, so the 10/10 is a measurement,
not an inference.

Cause, both layers:

| layer | site | pre-fix state |
|---|---|---|
| predicate | `platform/lib/completion_predicate.py:935` | `if rev_vendor == exec_vendor:` over `str(... or "")` free text |
| schema | `platform/schema/receipt.schema.json:261` (`reviewer.vendor`) and `:471` (`produced_by.vendor`) | `{ "type": "string", "maxLength": 64 }` — no enum, no pattern, no normalization |

## Q2 — a SECOND live instance sits inside the shipped reference example. CONFIRMED

`platform/schema/examples/receipt.valid.example.json:103` declares
`produced_by.vendor = "unassigned"` while `:151` declares `reviewer.vendor = "anthropic"`.
`"unassigned" != "anthropic"`, so under the pre-fix gate the platform's own canonical example
receipt read as CROSS-VENDOR. The same pair appears in all four
`platform/schema/examples/substrate/*.receipt.valid.json` fixtures. A placeholder is not an
identity; that pair is now `NOT-CHECKED`.

## Q3 — fix, layer 1 (predicate). CONFIRMED

New `platform/lib/vendor_identity.py` resolves a free-text vendor to a canonical identity from
`platform/registry/VENDOR-REGISTRY.json` and returns a THREE-valued comparison —
`SAME-VENDOR` / `CROSS-VENDOR` / `NOT-COMPUTABLE`. `completion_predicate.py:_c9_reviewer` now
calls it:

* `SAME-VENDOR`   → `UNSATISFIED`
* `CROSS-VENDOR`  → falls through to `SATISFIED`
* `NOT-COMPUTABLE`→ `NOT-CHECKED`, which BLOCKS completion

The third state is the substance of the fix. Pre-fix there were only two, so "not byte-equal"
was silently promoted to "different vendor".

**The other direction of wrongness is guarded too.** `bedrock`, `vertex`, `azure` and
`openrouter` each serve SEVERAL vendors' models. Folding them into one vendor would make the gate
report a genuinely cross-vendor review as same-vendor and BLOCK a valid completion. They are
registered as `kind: hosting_substrate`, `establishes_distinctness: false`, and resolve to
NOT-COMPUTABLE. `test_hosting_planes_are_not_folded_into_any_vendor` and
`test_registry_documents_the_exclusion_rule` pin that.

## Q4 — fix, layer 2 (schema). CONFIRMED

`receipt.schema.json` gained `$defs.vendor_id` (recognized tokens: canonical ids + aliases) and
`$defs.vendor_id_canonical` (canonical ids only). Both vendor fields are now
`{"$ref": "#/$defs/vendor_id"}`. The enum is **generated** from the registry by
`platform/lib/vendor_schema_sync.py`, never hand-typed, because two hand-kept copies of one
vocabulary drift.

Read off disk after the edit:

```
$ python platform/lib/vendor_schema_sync.py --check
SUCCESS:vendor-schema-sync (receipt schema matches the vendor registry)
```

Design choice stated so it is not over-read: the edit was a **text splice**, not a
`json.dumps` rewrite. `receipt.schema.json` is the declared `output_schema` of 674 catalogue
units and is hand-formatted; re-emitting the whole file would have buried a two-field change in
~500 lines of reformatting. `check()` therefore compares PARSED structure and is indifferent to
formatting.

Prior art found rather than invented: `platform/schema/councilspec.schema.json:442-444` already
constrained participant vendor to a 9-value enum
`[anthropic, openai, google, meta, mistral, xai, local, human, other]`. The registry is a strict
SUPERSET of it, so the council plane, the receipt plane and the predicate now share ONE identity
plane; `test_councilspec_vendor_enum_is_a_subset_of_the_registry` fails if that stops being true.

## Q5 — the ≥20-pair proof table. CONFIRMED (63 rows)

`platform/lib/test_vendor_identity.py` holds the matrix as DATA (`PAIRS`, each row carrying its
own expectation and rationale), parametrized twice — once against condition 9 and once against
the resolver — so predicate and resolver cannot disagree.

Composition read off disk, not hand-counted (an earlier draft of this file said 57 rows and
"15 REJECTED" from a hand-count and was WRONG on both):

```
$ python -c "import sys;sys.path.insert(0,'platform/lib');import test_vendor_identity as t;\
from collections import Counter;print(len(t.PAIRS), dict(Counter(p[2] for p in t.PAIRS)))"
63 {'SAME': 29, 'CROSS': 13, 'REJECTED': 21}
```

```
$ python -m pytest platform/lib/test_vendor_identity.py -q
173 passed in 1.48s
```

Representative rows (full table in the test file):

| executor | reviewer | expected | now |
|---|---|---|---|
| `anthropic` | `Anthropic` | SAME → UNSATISFIED | UNSATISFIED |
| `anthropic` | `anthropic ` | SAME → UNSATISFIED | UNSATISFIED |
| `anthropic` | `anthropic\x00` | SAME → UNSATISFIED | UNSATISFIED |
| `anthropic` | `claude` | SAME → UNSATISFIED | UNSATISFIED |
| `anthropic` | `opus` | SAME → UNSATISFIED | UNSATISFIED |
| `anthropic` | `anthropic.com` | SAME → UNSATISFIED | UNSATISFIED |
| `openai` | `codex` | SAME → UNSATISFIED | UNSATISFIED |
| `codex` | `openai` | SAME → UNSATISFIED | UNSATISFIED |
| `google` | `gemini` | SAME → UNSATISFIED | UNSATISFIED |
| `xai` | `x.ai` | SAME → UNSATISFIED | UNSATISFIED |
| `anthropic` | `openai` | CROSS → SATISFIED | SATISFIED |
| `claude` | `codex` | CROSS → SATISFIED | SATISFIED |
| `anthropic ` | ` codex` | CROSS → SATISFIED | SATISFIED |
| `opus` | `gpt-5` | CROSS → SATISFIED | SATISFIED |
| `anthropic` | `human` | CROSS → SATISFIED | SATISFIED |
| `anthropic` | `acme-ai` | REJECTED → NOT-CHECKED | NOT-CHECKED |
| `anthropic` | `!!!` | REJECTED → NOT-CHECKED | NOT-CHECKED |
| `anthropic` | `bedrock` | REJECTED → NOT-CHECKED | NOT-CHECKED |
| `unassigned` | `anthropic` | REJECTED → NOT-CHECKED | NOT-CHECKED |
| `other` | `other` | REJECTED → NOT-CHECKED | NOT-CHECKED |

## Q5b — the SAME instrument, before and after. CONFIRMED

The strongest single signal, because the instrument is the panel's own probe and I did not touch
it — only the code under it changed:

| | `alias_pairs_that_DEFEAT_the_gate` | identical-spelling control | distinct-vendor control | `detector_validated_both_states` |
|---|---|---|---|---|
| before | **10 / 10** | rejected (correct) | accepted (correct) | true |
| after | **0 / 10** | rejected (correct) | accepted (correct) | true |

```
$ python platform/architecture/_probe_crossvendor_alias_hole.py
alias_pairs_tested: 10
alias_pairs_that_DEFEAT_the_gate: 0
VERDICT: REFUTED: the gate normalizes vendor identity already
```

Both controls still pass AFTER the fix, which is what rules out the cheap failure mode — a gate
that now rejects everything would also show 0 leaks, but its distinct-vendor control would have
flipped to `accepted: false`. It did not.

## Q6 — suite baseline. See the pin correction

**The pinned 2,767 is stale.** Measured off disk at `0aa6f8fa` BEFORE any edit of mine:

```
$ python -m pytest platform -q
2812 passed, 14 skipped in 188.26s (0:03:08)
```

Corroborated independently: sibling unit D3's own baseline capture,
`platform/_d3_baseline_suite.txt`, ends `2812 passed, 14 skipped in 198.89s` — a second,
separately-run measurement agreeing to the test. So the number not to regress is **2812**, and
2,767 would have been a false floor (a 45-test regression could have hidden under it).

After the fix, measured last (after every edit, including the two guard rewrites in Q10 and the
blast-radius repairs in Q8b):

```
$ python -m pytest platform -q
3067 passed, 14 skipped in 210.62s (0:03:30)
```

**0 failed.** 2812 -> 3067 is +255, and that delta is NOT all mine: ~20 agents are writing this
tree concurrently. Two direct measurements of that movement: the catalog grew
5,244,176 -> 5,356,178 bytes between two probes minutes apart, and an intermediate full run 20
minutes earlier read 3064 with the identical source on my side. Attributable to this unit: **+173**
(`test_vendor_identity.py`, collected count read off disk) and **+3 net** in
`test_schema_resolver.py` (one test replaced by four).

The load-bearing figures are therefore **0 failed** and the resolution of the one test that WAS
red mid-unit (`test_schema_resolver.py::test_wave1_files_are_untouched`, Q10) — not the total.

Honest scope limit: a suite count taken from a tree under concurrent write is a snapshot, not a
reproducible constant. The settling measurement is a re-run after the orchestrator commits the
wave and the tree is quiet.

## Q10 — two shared guards had to be rewritten, and why that is not gate-weakening. CONFIRMED

`platform/lib/test_schema_resolver.py::test_wave1_files_are_untouched` asserted that
`receipt.schema.json` AND `command-center/WORK-UNIT-CATALOG.json` are byte-identical to committed
HEAD, with the docstring rationale *"this unit claims it modified neither"*. It went red because
this unit was INSTRUCTED to modify `receipt.schema.json`.

That invariant is the self-falsifying shape `rules/common/single-signal-verification.md` already
records: equality to a pinned blob cannot distinguish an unauthorized edit from legitimate
authorized work, and the rule notes it raised three false alarms against legitimate commits. It
was NOT deleted or relaxed to a pass. Each half was replaced by an invariant that survives
authorized concurrent work and still fails on everything else, each with its own both-states
control:

| replacement | asserts | control |
|---|---|---|
| `test_receipt_schema_differs_from_head_ONLY_by_the_authorized_d1_delta` | strip the 2 generated `$defs` + restore the 2 vendor fields to their pre-D1 declaration -> result must still equal HEAD; and the D1 `$defs` must be PRESENT (so a reverted fix cannot pass silently) | `test_the_authorized_delta_guard_fires_on_an_unauthorized_edit` — 4 mutations (extra `$def`, relaxed `sha256` pattern, popped `required` entry, changed top-level description) must each break it, and the good state must stay silent |
| `test_catalog_contract_this_unit_depends_on_is_unchanged` | the surface the RESOLVER reads: 2,007 units, ordered ids, ordered `output_schema` values, 103 `items[]` | `test_catalog_contract_guard_fires_on_a_destructive_edit` — 5 mutations (deleted unit, renamed id, rewritten `output_schema`, dropped `items[]` entry) must break it, AND an unrelated `tool_policy` field addition must NOT |

Scope limit stated inline in the test: the schema comparison is on PARSED structure, so a pure
reformat or key reorder would pass. Deliberate — formatting is not a soundness property — while
every semantic addition, removal or value change anywhere in the document is still caught.

## Q11 — a SECOND divergence was hidden behind the first. CONFIRMED (not mine)

The original guard looped `receipt.schema.json` first and asserted, so it never reached the
catalog. Splitting it exposed that `WORK-UNIT-CATALOG.json` was ALREADY diverging from HEAD —
842 insertions / 173 deletions of `tool_policy` blocks from sibling unit D2 (`command-center/
D2-WORKUNIT-AUTHZ.md`). A job stops at its first failing assertion, so one red hid two causes.

Measured impact of D2's edit on the substrate: **none.** Units 2007 -> 2007, unit ids identical,
`output_schema` values identical, `items[]` 103 -> 103, no key added or removed at unit level.
Reported for attribution, not as a defect.

## Q12 — cc-validate and cc-render. cc-render drift is NOT this unit's

```
$ python tools/command-center/validate.py
SUCCESS:cc-validate items=103 open=69 reachable=all                       (exit 0)

$ python tools/command-center/render.py --check
  ARTIFACT-MANIFEST.json does not match the files on disk
FAILED:cc-render drift=1                                                  (exit 1)
```

Attributed to a single row, with two mechanically independent signals that it is not mine:

1. The only differing manifest entry is `command-center/WORK-UNIT-CATALOG.json`
   (`349773cff3837d52` on disk vs the current file's hash). `ARTIFACT-MANIFEST.json` is itself
   UNMODIFIED per `git status` and still carries the exact HEAD blob sha of the catalog
   (`349773cff3837d52`, 5,244,176 B) — so the manifest is pristine and the catalog moved under it.
2. The manifest tracks 14 artifacts and **none of them is under `platform/`**;
   `receipt.schema.json` is not tracked at all, so no edit of mine can enter this computation.

Left unrepaired on purpose: regenerating `ARTIFACT-MANIFEST.json` would stamp sibling D2's
in-flight catalog into a shared committed artifact. That is the orchestrator's between-waves
action, not this unit's.

## Q7 — both-states controls. CONFIRMED

A green matrix proves nothing unless it can go red. Four controls, each asserting the POSITIVE:

1. `test_prefix_gate_leaks_every_alias_pair` reimplements the pre-fix comparison verbatim and
   requires it to ACCEPT ≥10 of the SAME rows, and requires the ONLY row it caught to be exactly
   `("anthropic","anthropic")` — which is why the panel's controls looked valid while the gate
   was permissive.
2. `test_prefix_gate_would_also_have_passed_the_rejected_rows` requires the pre-fix gate to have
   promoted ≥10 REJECTED rows to SATISFIED.
3. `test_prefix_schema_would_have_accepted_the_garbage` requires the pre-fix
   `{"type":"string","maxLength":64}` to accept `acme-ai`, `Anthropic`, `anthropic `, `!!!` and
   `anthropic\x00`.
4. `test_sync_check_detects_drift` mutates the schema two ways (revert a vendor field to the bare
   string; add an unregistered enum member), requires `check()` to FIRE on both, and requires it
   to be SILENT on the unmutated file — so it is not a detector that fires in every state.

`test_matrix_covers_every_expectation_and_meets_the_floor` additionally asserts the row counts per
class, so a matrix that silently lost the whole REJECTED class cannot still read "all green".

### Q7b — the decisive control: the matrix run against the PRE-FIX code

The four controls above are analytic (they reimplement the old rule). This one reverts the real
`_c9_reviewer` and runs the real matrix against it, in a THROWAWAY COPY of
`platform/{lib,registry,schema}` — never the shared tree, because ~20 agents run this suite and an
in-place mutation would show them spurious failures.

```
$ python platform/lib/_d1_mutation_proof.py
"control_unmutated_copy": { "exit": 0, "tail": "126 passed, 47 deselected in 1.32s", "green": true }
"mutated_copy":           { "exit": 1, "tail": "46 failed, 80 passed, 47 deselected in 2.65s", "red": true }
"VERDICT": "BOTH-STATES VALID: the matrix is green on the fixed code and RED on the pre-fix code"
SUCCESS:d1-mutation-proof
```

The 46 is arithmetically consistent with the pre-fix semantics rather than just "some number went
red", which is what makes it a detector and not a coincidence:

* 28 failures = the 29 `SAME` rows minus the one byte-equal pair `("anthropic","anthropic")`, which
  the pre-fix `==` already caught (exactly why the panel's controls looked valid);
* 18 failures = the 21 `REJECTED` rows minus the 3 the pre-fix path happened to get right for the
  wrong reason (`""`, `""` on the executor side, and `None`, all of which hit its
  undeclared-vendor branch);
* 28 + 18 = 46 failed, and 1 + 13 `CROSS` + 3 = 17 passed of the 63 predicate rows;
* the other 63 selected tests are `test_pair_matrix_resolver_comparison`, which all pass because
  the resolver was not mutated — so the mutant is localized to the code under test.

First attempt at this proof was INVALID and is recorded rather than deleted: the mutant also wrote
`detail["vendor_comparison"] = "PREFIX-MUTANT"`, so all 63 predicate rows failed on a bookkeeping
assertion instead of on the semantics — a detector that fires everywhere measures nothing. The
mutant now translates the pre-fix semantics faithfully into the new detail vocabulary so it differs
ONLY where the two disagree about identity.

## Q8 — the twin reducer does NOT carry this hole, and does NOT carry the rule either. CONFIRMED

`platform/lib/receipt_schema_gate.py` also implements the 12 conditions (`evaluate_gate_a`). Its
condition 9 (`:489-502`) checks verdict / independent / reviewer_id-vs-role and **never reads
`vendor` at all**. So it never had the alias bug — and it cannot enforce cross-vendor review
either. Two reducers, one rule, one implementation: a caller that routes through
`receipt_schema_gate` gets no cross-vendor enforcement whatsoever. Out of scope for D1 (D1 is the
false green, not the missing feature) and NOT fixed here; reported so it is not mistaken for
covered.

## Q8b — BLAST RADIUS: the fix broke two mutation tools, and both are repaired. CONFIRMED

Adding a module-level `from vendor_identity import ...` to `completion_predicate.py` gave it a
sibling dependency, and two verification tools stage `completion_predicate.py` into a temp tree by
copying a NAMED LIST of files. Both would have failed at import — and both fail SILENTLY in the
worst way: their own `importable` probe would read False for every mutant, so a broken battery
would print as "nothing killed" rather than as an error.

Failure mode proven directly, not assumed:

```
$ T=$(mktemp -d); cp platform/lib/completion_predicate.py "$T/"; cd "$T" && python -c "import completion_predicate"
  File ".../completion_predicate.py", line 47, in <module>
    from vendor_identity import Comparison
ModuleNotFoundError: No module named 'vendor_identity'
```

Both consumers now also copy `vendor_identity.py` and `platform/registry/VENDOR-REGISTRY.json`,
and both were re-run to green:

```
$ python platform/lib/_mutation_selfcheck.py
SUCCESS:predicate-mutation-selfcheck 12/12 mutants killed        ("mutant_importable": true)

$ python command-center/_wave1_mutation_control.py
"verdict": "CONFIRMED"      (stubbed_node_killed: true, other_node_unaffected: true)
```

Search scope for this sweep, stated so the absence claim is bounded: `grep -rln completion_predicate
--include=*.py .` over the whole repo (excluding `__pycache__`), then filtered to files containing
`shutil`/`copyfile`/`copytree`. Two hits, both fixed; the remaining importers
(`test_completion_predicate.py`, `_predicate_*.py`, `_judge_verify.py`,
`_probe_crossvendor_alias_hole.py`) all put the real `platform/lib` on `sys.path`, so the sibling
resolves — each was exercised by the suite or re-run by hand above.

## Q9 — ruff under CI's pin. CONFIRMED

```
$ uvx ruff@0.15.17 check platform/lib/vendor_identity.py platform/lib/vendor_schema_sync.py platform/lib/test_vendor_identity.py platform/lib/completion_predicate.py
All checks passed!
$ uvx ruff@0.15.17 format --check <same four>
4 files already formatted
```

All **9** files this unit touched are clean. Local ruff is NOT used: CI pins `0.15.17`
(`.github/workflows/quality.yml:89`) and versions format differently. The three new `.py` files are
written LF-only (measured: 0 CRLF), so working-tree bytes and the stored blob agree and this green
is not measured against the wrong bytes. `receipt.schema.json` kept its original CRLF consistently
(measured: 975 CRLF, 0 bare LF, parses OK).

Pre-existing and NOT mine, reported for the orchestrator: `uvx ruff@0.15.17 check platform/
command-center/` finds **19 errors**, all in sibling scratch probes under
`platform/architecture/_mh_*.py`, `_probe_gwlazy_inventory.py`, `_secfirst_measure2.py`,
`_uxpf_measure.py` (E401/E741/F401). They are untracked so CI cannot see them today, but
`ruff.toml` does not exclude `_*.py` — committing any of them reds `gate-lint-format`.

---

## Files

| path | change |
|---|---|
| `platform/registry/VENDOR-REGISTRY.json` | NEW — the alias table as auditable data. Measured through the loader, not by hand: 21 identities (11 `model_vendor`, 1 `human`, 5 `hosting_substrate`, 4 `placeholder`), **12 distinctness-capable** (`anthropic openai google meta mistral xai deepseek alibaba cohere amazon microsoft human`), **123** recognized tokens in the alias index |
| `platform/lib/vendor_identity.py` | NEW — resolver + three-valued `compare()` |
| `platform/lib/vendor_schema_sync.py` | NEW — generates the schema enum from the registry; `--check` is the drift gate |
| `platform/lib/test_vendor_identity.py` | NEW — 57-row matrix + 4 both-states controls (173 tests) |
| `platform/lib/completion_predicate.py` | MODIFIED — c9 compares canonical identity; adds the NOT-COMPUTABLE path |
| `platform/schema/receipt.schema.json` | MODIFIED additively — `$defs.vendor_id`, `$defs.vendor_id_canonical`, two fields now `$ref` |
| `platform/lib/test_schema_resolver.py` | MODIFIED — the self-falsifying byte-equality guard replaced by two scoped invariants + two both-states controls (see Q10) |
| `platform/DEFECT-D1-CROSS-VENDOR.md` | NEW — this record |
| `platform/lib/_mutation_selfcheck.py` | MODIFIED — stages `vendor_identity.py` + the registry, or every mutant fails to import (Q8b) |
| `command-center/_wave1_mutation_control.py` | MODIFIED — same staging fix (Q8b) |
| `platform/lib/_d1_insert_vendor_defs.py` | SCRATCH (`_` prefix = untracked) — the one-time schema text splice |
| `platform/lib/_d1_mutation_proof.py` | SCRATCH (`_` prefix = untracked) — the isolated-copy mutation proof of Q7b |

No file was deleted and no field was removed, so the 674 units declaring the receipt schema keep
resolving.

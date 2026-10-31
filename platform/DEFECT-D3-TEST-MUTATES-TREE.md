---
title: DEFECT-D3-TEST-MUTATES-TREE
type: note
permalink: dqverify-repo-20261013/platform/defect-d3-test-mutates-tree
---

# DEFECT D3 — a test that silently repaired the real tree, and sampled 1.7%

Unit `defect/d3-test-mutates-tree` · baseline main `0aa6f8fa` · measured 2026-08-10.

Source anchor: `platform/architecture/TOURNAMENT-VERDICT.md:66` (D3 row).
All numbers below are read OFF DISK by a probe whose output is quoted, never self-reported.

## A. Defect anatomy — two defects in one test

`test_generator_is_deterministic(tmp_path)` at `platform/lib/test_schema_resolver.py:313-335`
(HEAD `0aa6f8fa`) did this:

```python
p = subprocess.run(
    [sys.executable, str(REPO / "platform" / "lib" / "_gen_schema_substrate.py")],
    capture_output=True, text=True, cwd=str(REPO),
)
```

1. **It regenerated the real tree.** Every run of the suite rewrote all 236 generator
   outputs in place, so a hand-edit to any of them was silently reverted.
2. **The determinism claim rested on 1.7% coverage** — 4 snapshotted paths against 236
   outputs.

### A third finding the spec did not anticipate: `cwd` was never the seam

The prompt's proposed fix — *"run the generator in `tmp_path`, that is what the fixture is
for"* — would **not have worked**. Measured:

| probe | value |
|---|---|
| `REPO` in the generator @ HEAD | `"C:/Users/Prekzursil/source/ast-integrate"` (hardcoded literal) |
| generator reads `os.getcwd` / `Path.cwd` / `os.environ` anywhere | **False** |
| `os.path.join(REPO, ...)` sites | 4 (one of them `write_json`) |

The generator is entirely cwd-independent: `cwd=str(REPO)` was **decorative**, and
`cwd=tmp_path` would have redirected **zero** writes while still repairing the tree. The
fixture was unused (`tmp_path` appears 0 times in the old body after the signature).
So the fix required adding a real output seam, not just changing the `cwd` argument.

## B. BEFORE numbers, read off disk

Probe `platform/lib/_d3_measure_before.py` (non-mutating: `write_json` replaced by a
counter, and it asserts `probe_itself_mutated_tree == []` so it cannot commit the defect
it measures — that assertion returned `[]`).

| measurement | value |
|---|---|
| files the generator writes | **236** |
| — `command-center/schema/*.json` shims | 231 |
| — `command-center/schema/{_meta,meta}` mirrors | 2 |
| — `command-center/wfa/schema/wfa-schema-pack.json` | 1 |
| — `platform/schema/{artifact-class-profiles,ARTIFACT-CLASS-REGISTRY}` | 2 |
| paths the old test snapshotted | **4** |
| **old coverage** | **1.69 %** |
| outputs left unsampled | **232** |
| duplicate writes | 0 (236 unique) |
| `command-center/schema` git-tracked | 232 of 233 |

## C. The fix

### C1. `platform/lib/_gen_schema_substrate.py` — an output seam

- `REPO` is now **derived from `__file__`** instead of a hardcoded absolute path
  (verified: `os.path.realpath` equal to the old literal, `CATALOG` still resolves).
- New module global `OUT_ROOT`, defaulting to `REPO`; **`write_json` is the only writer**
  and now joins on `OUT_ROOT`.
- New `--out-root` flag (argparse) redirects every write and only writes; inputs are
  always read from `REPO`.
- Fail-closed: an absent catalog returns exit 2 with `FAILED:gen-substrate`, so the
  generator can never "succeed" by generating nothing. **Executably verified with a
  both-states control** (`platform/lib/_d3_verify_failclosed.py`): the generator copied
  into a catalog-less temp tree gives `exit 2`, `FAILED:gen-substrate catalog absent at
  …`, **0 files written**; the same copy with a catalog restored gives `exit 0` and
  **236** files. The control is what makes the exit 2 meaningful — without it, an exit 2
  could have been an unrelated import failure. This also proves the `__file__`-derived
  `REPO` works from an arbitrary location, which the old hardcoded literal did not.
- Default behaviour is unchanged, so the one other caller
  (`platform/architecture/_mh_probe_drift.py`, untracked scratch, invokes it bare) still works.

### C2. `platform/lib/test_schema_resolver.py` — 4 paths → 236, and no tree writes

`test_generator_is_deterministic` (1 test, 4 paths) was replaced by **5** tests:

| test | what it asserts |
|---|---|
| `test_generator_output_matches_every_committed_file` | all **236** outputs, generated into `tmp_path`, equal the committed tree |
| `test_generator_emits_lf_only` | the generator's own LF contract (0 CRLF in output) |
| `test_generator_is_deterministic` | two runs into two temp dirs are byte-identical — determinism measured **without** the tree as oracle |
| `test_running_the_generator_under_test_leaves_the_real_tree_untouched` | the D3 regression guard: ≥234 tracked digests, asserted **all unchanged** (positive assertion, not "nothing looked broken") |
| `test_no_platform_test_invokes_the_generator_against_the_real_tree` | AST guard: every generator spawn in `platform/**/test_*.py` passes `--out-root` |

Comparison is **LF-normalised**: a CRLF checkout is a legal working-tree state, not a
defect, and the LF contract is asserted separately. Measured today: raw-byte differences
`0`, LF-normalised differences `0`, CRLF files `0` in both tmp and worktree — so
normalisation is currently a no-op and purely defensive.

### C3. Two detector bugs in my own guard, caught by its own control

The AST guard in C2 was wrong twice before it was right. Both were caught by the
both-states control **inside the test**, not by review:

1. `ast.walk` descended into the nested `str(REPO / ... / "_gen_schema_substrate.py")`
   call, so the broken fixture reported `[2, 2]` instead of `[2]` — a detector
   disagreeing with itself.
2. After gating on the outermost call, the checker flagged **its own source line**
   `s.endswith("_gen_schema_substrate.py")` — a *mention* of the path read as a *use* of
   it. Fixed by gating on the callee being a subprocess spawner.
3. The fail-closed `spawns >= 1` assertion then fired with `0`, because the real
   invocation hoists the path into a module constant (`GENERATOR`). Fixed by resolving
   module-level `NAME = "str"` bindings. The control now covers both spellings and a
   bare mention.

## D. Both-states control — the edit SURVIVES where it previously did not

Target: `command-center/schema/abstraction-leak.schema.json`, an output the old test did
**not** sample. Same planted edit in both states. Both probes restore the file and assert
the restore.

| | BROKEN state (HEAD) | FIXED state |
|---|---|---|
| probe | `platform/lib/_d3_control_bothstates.py` | `platform/lib/_d3_control_after.py` |
| sha planted | `3f4cc56ab422b071…` | `3f4cc56ab422b071…` |
| sha after run | `502247b350950d31…` (= pristine) | `3f4cc56ab422b071…` (= planted) |
| hand edit | **REVERTED** | **SURVIVED** |
| suite verdict | `1 passed`, **exit 0** | `test_generator_output_matches_every_committed_file` **FAILED** |
| net effect | defect silently repaired, reported green | defect detected, tree left alone |

The BROKEN row is the load-bearing one: the old test **passed while erasing the edit**.

## E. Same-shape sweep — every test invoking a subprocess/generator with cwd at the repo

Scope: all 100+ `test_*.py` under `platform/` (`rglob`), plus a write-call sweep
(`write_text|write_bytes|open(...,"w")|makedirs|mkdir|shutil.copy*|rmtree|remove|unlink`).

| file:line | call | verdict |
|---|---|---|
| `platform/lib/test_schema_resolver.py:331` | `_gen_schema_substrate.py`, `cwd=str(REPO)` | **THE DEFECT — fixed** |
| `platform/lib/test_schema_resolver.py:268` | `git cat-file -p HEAD:<rel>`, `cwd=str(REPO)` | **not a defect** — read-only; `cwd` is required for git to find the repo |
| `platform/lib/test_completion_predicate.py:943` | `_predicate_differential.py` / `_predicate_real_units.py`, `cwd=str(REPO_ROOT)` | **not a defect** — both probes write only via `--out`, which the test points at `tmp_path` (verified: their only write sites are `Path(ns.out).write_text` at `:231` and `:302`) |
| `platform/lib/councilspec/test_councilspec.py:665-709` | mutates councilspec examples | **exemplary** — `shutil.copytree(EXAMPLES_DIR, tmp_path)` first, then mutates the copy |
| all other write calls | under `tmp_path` / a `Case.root` fixture | clean |

**Only one occurrence of the shape existed.** The new AST guard makes a recurrence red.

## F. Suite numbers

Command: `python -m pytest platform -q -p no:randomly`

| run | result | artifact |
|---|---|---|
| baseline, 06:28, before any edit of mine | **2812 passed, 14 skipped, 0 failed** in 198.89s | `platform/_d3_baseline_suite.txt` |
| after the fix, 06:51 | **2996 passed, 14 skipped, 1 failed** in 170.41s | `platform/_d3_after_suite.txt` |
| final, 07:0x | **3064 passed, 14 skipped, 3 failed** in 210.82s | `platform/_d3_final_suite.txt` |
| my module alone, final | **38 passed, 0 failed** | — |

The passed count climbed 2812 → 2996 → 3064 across three runs of the *same* command
because ~20 agents are adding tests to this tree concurrently. My own contribution to that
is **+4** (−1 rewritten, +5 new). No run of mine regressed a previously-passing test.

The 3 final failures are all in `platform/lib/wfdsl/test_work_unit_authorization.py`,
which is **untracked and did not exist at `0aa6f8fa`** — a sibling lane authoring it live
(`git cat-file -e HEAD:…` fails; its companion `wfdsl/authz_census.py` is also untracked).
It imports only `wfdsl.{authz_census, schemas, semantics, validate}` — nothing this unit
touched. `test_wave1_files_are_untouched`, the failure in the middle run, is gone because
the D1 sibling replaced it with their own guard.

**The pinned "2,767 passed / 14 skipped" could not be reproduced: the measured baseline at
`0aa6f8fa` was 2812.** I did not investigate the 45-test gap — it predates my edit and is
outside this unit. Anyone citing 2,767 should re-measure. `UNVERIFIED` — settled by running
the command above on a clean checkout of `0aa6f8fa`.

My own delta to the module: **−1 test, +5 tests** (`test_generator_is_deterministic` was
rewritten in place; the other four are new).

Post-run hygiene check: after every probe, the substrate is byte-at-HEAD
(`git status --porcelain command-center/schema command-center/wfa platform/schema/artifact-class-*`
= empty) and the control target `command-center/schema/abstraction-leak.schema.json` hashes
identically to `HEAD` with no sentinel left behind. **No probe in this unit left the tree
dirty** — which is the minimum bar for a unit whose whole subject is a probe that did.

### The middle run's failure was NOT mine, and a sibling has since fixed it

`test_wave1_files_are_untouched` failed because a **concurrent sibling lane (DEFECT D1,
cross-vendor)** added a `vendor_id` enum to `platform/schema/receipt.schema.json` at
06:41:11 — after my 06:28 baseline. Attribution evidence, four independent signals:

1. My baseline at 06:28 had **0 failures**; the file matched HEAD then.
2. `git status` shows **20** modified tracked files; exactly **one**
   (`platform/lib/test_schema_resolver.py`) is mine.
3. The added text names `platform/lib/vendor_schema_sync.py` and
   `platform/registry/VENDOR-REGISTRY.json` — sibling files I never touched (mtimes
   06:47 / 06:33).
4. My control probe recorded the identical single failure with the tree clean of my edit
   (`clean_tree_failed_nodes`), so it is independent of anything I planted.

That sibling then replaced `test_wave1_files_are_untouched` with their own
`test_receipt_schema_differs_from_head_ONLY_by_the_authorized_d1_delta` **in this same
file, while I was working in it**. My 5 tests and 3 helpers survived byte-intact
(verified by AST name check) and the file is still clean under pinned ruff 0.15.17.

### The sibling's catalog edit cannot destabilise my new test

`command-center/WORK-UNIT-CATALOG.json` is also modified by a sibling. It is the
generator's **input**, so this mattered. Measured: **0** of 2007 `output_schema` values
changed, 0 ids added or removed, and the whole substrate is byte-at-HEAD. So
`test_generator_output_matches_every_committed_file` is green for the right reason.

## G. Adjacent finding — the generator is UNTRACKED (owner decision)

`platform/lib/_gen_schema_substrate.py` is **untracked** (`git ls-files --error-unmatch`
fails), while **232** of the files it writes are tracked. It was almost certainly swept up
by `0aa6f8fa` *"chore(platform): untrack Wave 2 probe scripts"* because of its `_` prefix —
but it is not a probe, it is the single writer of the substrate and the emitter the
architecture docs build on (`platform/architecture/generated-ssot.md:168,491`).

Consequences:

- A fresh clone **cannot regenerate** the substrate.
- The platform suite is **not** currently gated in CI (0 `pytest platform` steps in
  `.github/workflows/quality.yml`), so this is not red today. The moment it is gated, the
  5 generator tests fail on a fresh checkout for want of the generator. This was already
  true of the 1 old test; my change raises the exposure from 1 test to 5.

**Recommended (orchestrator action — I am forbidden from `git add`):** track the generator,
and rename it off the `_` scratch prefix (e.g. `gen_schema_substrate.py`). The rename is
deliberately **not** done here: the name is stamped into all 231 shims
(`x-generated-by`) plus the registry and several architecture docs, so it is a ~236-file
regeneration and belongs in its own unit, not smuggled into a test fix.

## H. Ruff, pinned to CI's version

`uvx ruff@0.15.17` (not the ambient one — versions format differently).

- `ruff check` → `All checks passed!`
- `ruff format --check` → `2 files already formatted`
- Both files are **LF-only** on disk, so the local bytes are the CI bytes.
- Control: the HEAD blob of `test_schema_resolver.py`
  (`git cat-file -p`, never `git archive`) was `1 file already formatted`, so the format
  drift I fixed was **100% introduced by my own edit** — clean attribution.
- Note: `ruff format` also normalised pre-existing lines in the untracked
  `_gen_schema_substrate.py`. That widens its diff but cannot regress CI (CI never sees an
  untracked file) and makes it gate-clean for whenever it is tracked.

## I. Residual / not checked

- `NOT-CHECKED`: the 2,767-vs-2812 baseline gap (§F).
- `NOT-CHECKED`: whether every one of the 236 outputs is *semantically* correct. These
  tests prove reproducibility, tree-equality and non-mutation — not that the emitted
  schemas are the right schemas. That is `test_every_logical_id_compiles` and the
  discrimination census, which already existed.
- The fail-closed path is verified by a probe (§C1) but is **not** covered by a committed
  pytest case, so nothing keeps it from regressing. Cheapest closure: promote
  `platform/lib/_d3_verify_failclosed.py` into a test in `test_schema_resolver.py`.
- Concurrency: 20 tracked files are dirty from ~20 agents sharing one index. Every number
  in this document is timestamped because none of them is stable under that load.
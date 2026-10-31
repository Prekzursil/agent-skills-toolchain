---
title: SLOP-REPORT
type: note
permalink: dqverify-repo-20261013/command-center/slop-report/slop-report
---

# SLOP REPORT -- dead scratch, orphaned artifacts, parallel non-SSOT folders

LANE: SLOP (grounding -- measure only, no production code, no destructive execution)
REPO: `C:/Users/Prekzursil/source/ast-integrate` @ `ae8205a4` (worktree of agent-skills-toolchain, main)
GENERATED: 2026-08-12 ~19:55 local
STATUS: MEASURED. All buckets classified. Zero deletions executed -- see "Why nothing was deleted".

## COVERAGE

| section | state |
|---|---|
| tracked / untracked / ignored census | MEASURED (disjointness control passed) |
| ruff format+lint on untracked py | MEASURED (both-states control passed) |
| bucket (a) committed evidence | MEASURED |
| bucket (b) uncommitted evidence | MEASURED -- this is the big one |
| bucket (c) reproducible scratch | MEASURED + regeneration PROVEN by execution |
| bucket (d) dead | MEASURED |
| reference detector | MEASURED (positive + negative control passed) |
| parallel/duplicate directory census | MEASURED |
| frozen-evidence dirs untouched | MEASURED (0 dirty, sha manifest recorded) |
| `command-center/harvest/` | MEASURED (all 4 tracked -> bucket a) |
| `_advver_M14` 77-file claim | MEASURED -- brief's premise CORRECTED |
| identity of the process writing `NUL` | **UNVERIFIED** -- see R10 |

MOVING TARGET: untracked count went 163 -> 215 during this lane's ~25-minute run. Sibling
lanes are writing right now (mtimes 3-9 min). Every count below is a timestamped snapshot.

## HEADLINE CENSUS

| set | files | bytes |
|---|---|---|
| tracked | 10,196 | -- |
| untracked, NOT ignored | 215 (198 pre-existing + 17 mine) | ~1.5 MB |
| ignored (on disk, git-invisible) | 7,193 | 101.4 MB |
| of which caches (`__pycache__`/`.pytest_cache`/`.ruff_cache`) | 2,997 | 48.9 MB |

Control: `untracked ∩ ignored = 0`, `tracked ∩ untracked = 0`. The three sets are disjoint.

---

## RANKED FINDINGS

### R0 -- DO NOT RUN `git clean -Xdf`. It destroys all 45 cited probe scripts. STOP-SHIP.

The standard, obvious way to "clean ignored files" is catastrophic in this repo. Measured with
the dry run `git clean -ndX`:

| what it would remove | entries |
|---|---|
| total | **554** |
| `command-center/_*.py` probe scripts | **123** (including all 45 cited by committed artifacts, R1) |
| `tools/mcp/...` vendored entries | 20 |

Because R1's evidence is *ignored rather than tracked*, the normal hygiene command treats it as
disposable. Anyone reaching for `git clean -Xdf`, `-xdf`, or a "delete everything gitignored"
sweep silently deletes the provenance behind 45 committed receipts. This is the highest-severity
item in this report precisely because the destructive action looks routine.

Safe substitute is the scoped sweep in R8, which names only the three cache directory types and
touches nothing else. Confidence: **almost certain (97%)** -- git's own dry-run enumerates it.

### R1 -- 45 COMMITTED artifacts cite a probe script git can NEVER carry. Bucket (b). HIGHEST.

`.gitignore:76` is `command-center/_*.py`. Measured: **123 of 123** probe scripts in
`command-center/` root are ignored; **0 are tracked**; 1,269,072 bytes exist only on this disk.
**45 of them (403,870 B) are named inside a COMMITTED artifact.** On a fresh clone those
citations dangle -- the receipt survives, the thing that produced the number does not.

Most-cited: `_sub1_normalize_probe.py` (6 committed citations), `_catalog_integrity.py` (5),
`_wave1_mutation_control.py` (3), `_proto3_probe_sem001_vs_sem012.py` (3),
`_p14_manifest_verify.py` (3), `_b2_m09_probe.py` / `_b2_m09_probe2.py` (3 each).

The rule contradicts its own header. `.gitignore` line ~72 reads *"agent probe outputs --
regenerable; the probe SCRIPTS are kept as provenance"*, then the very next lines ignore the
scripts. Self-evidencing.

**Two precedents already in this repo -- follow them, do not invent a third:**
1. Commit `d53485ce` (2026-08-11) *"chore: commit six root-level probes a TRACKED audit cites
   but a clone [lacks]"* -- the identical defect, fixed once, at repo root. Those six
   (`_refute_f1_codex_stubs.py`, `_refute_f4_atomicity.py`, `_refute_f6_probe{,2,3}.py`,
   `_f7_syncskills_probe.py`) are tracked today.
2. `.gitignore` already carries a negation with a written rationale --
   `!platform/lib/_gen_schema_substrate.py`, justified as *"A generator that a committed test
   executes is SOURCE, not scratch."*

ACTION: commit the 45 cited scripts via per-path negations (or `git add -f`), mirroring the
`_gen_schema_substrate.py` comment style. Leave the 78 uncited ones ignored.
Confidence: **almost certain (95%)** -- two independent signals (`git check-ignore -v` naming
the rule and line, plus `git ls-files` showing 0 tracked).

### R2 -- 31 of 32 untracked outputs are regenerable ONLY on this disk. Bucket (b), not (c).

Every one of the 32 untracked `*.out.json` / `*.err.txt` outputs has its producing `.py` on
disk -- but **31 of 32 producers are themselves untracked or ignored**. Only
`command-center/p2-wave/_i3_blobfmt.out.json` has a TRACKED producer
(`command-center/p2-wave/_i3_blobfmt.py`) and therefore genuinely satisfies bucket (c)'s
"a committed script regenerates it".

So the four-bucket scheme has a trap: these *look* like bucket (c) and are actually bucket (b).
Deleting them is safe only AFTER R1 lands. Sequence matters: **commit producers, then the
outputs become truly reproducible.**

### R3 -- committing the untracked scratch as-is turns main RED. 31 files, repo-wide gate.

Measured with pinned `ruff@0.15.17` (CI's pin), excluding my own files, on 103 untracked `.py`:

* `ruff format --check` -> **31 files** would reformat
* `ruff check` -> **11 violations across 7 files** (9x `E741` ambiguous `l`, 1x `F841`, 1x `F401`)

`.github/workflows/quality.yml` runs `ruff check .` and `ruff format --check .` -- **repo-wide,
not diff-scoped** (86 `- name:` steps total in that file). The brief said 16 format / 9 lint;
measured now it is 31 / 11 across 7. The format count roughly doubled during this session as
sibling lanes wrote -- it is a moving target, not a stable defect count.

Detector control (both states): a deliberately-broken file made both `ruff format --check` and
`ruff check` exit 1; a clean file left both silent at exit 0. The detector distinguishes.

### R4 -- the ignore rules are asymmetric, and neither side matches the stated intent.

* `command-center/` **over-ignores**: `command-center/_*.py` swallows every script (R1).
* `platform/` **under-ignores**: only 5 prefixes (`_probe_*`, `_patch_*`, `_gen_*`, `_lane*`,
  `_build_*`). Anything named `_measure_*`, `_mh_*`, `_d3_*`, `_bp*`, `_judge_*`, `_secfirst_*`,
  `_mkt_*` slips through -- **102 untracked files under `platform/`** (47 in `platform/lib`,
  47 in `platform/architecture`). Verified: `git check-ignore platform/lib/_d3_measure_before.py`
  -> NOT IGNORED, vs `command-center/_a3_probe.py` -> `.gitignore:76`.

### R5 -- naming-convention gap: `_x.out.json` is not covered by `**/_*_out.json`.

The rules match the underscore form (`_foo_out.json`, 80 files correctly ignored). Files using
the dot form (`_foo.out.json`) are NOT matched -- **31 untracked files** slip through purely on
a punctuation difference. Both conventions are in live use in the same directories.

### R6 -- NEAR MISS: 15 "zero-reference" files are LIVE sibling-lane deliverables, not dead.

A naive "nothing references it => dead" verdict would have proposed deleting active work.
mtimes, against a control:

| file | age at measure |
|---|---|
| `docs/_lane_docs_detector.py` | 3.5 min |
| `command-center/hook-audit/H1-INVENTORY.json` | 4.6 min |
| `docs/rule-audit/_rule-inventory.json` | 4.7 min |
| `command-center/ssot/clone-measurements.json` | 5.5 min |
| `docs/ssot/SSOT-CLONE-INVENTORY.md` | 8.7 min |
| ... 10 more in the 3-9 min band | |
| **CONTROL** `README.md` | **4,490 min** |
| **CONTROL** `QUALITY-CHARTER.md` | **4,490 min** |

Only 2 of the 17 zero-ref files are genuinely stale: `command-center/_synthrev_commitmsg.txt`
(223 min) and `command-center/p2-wave/_i3_blobfmt.out.json` (362 min).
Scope note: mtime proves "written recently", nothing more -- it is used here only to establish
LIVENESS, never staleness-vs-completion.

### R7 -- HAZARD: a `*/control/` glob protects 1 of 8 frozen fixtures.

The frozen-evidence convention is stated as `p2-wave/probes/*/control/`. Measured, exactly
**one** such directory exists. The other seven control/fixture artifacts are FILES a directory
glob cannot see:

```
command-center/p2-wave/probes/AUD-0006/control                          <- dir (the only one)
command-center/p2-wave/probes/AUD-0020/control-out-of-range-pin.json
command-center/p2-wave/probes/AUD-0021/fixture-lock-corrupt.json
command-center/p2-wave/probes/AUD-0021/fixture-lock-desync.json
command-center/p2-wave/probes/AUD-0021/fixture-lock-good.json
command-center/p2-wave/probes/AUD-0030/control-scc.json
command-center/p2-wave/probes/AUD-0041/control-matrix-expansion.json
command-center/p2-wave/probes/AUD-0051/control-not-checked-extractor.json
```

Any future cleaner MUST match `control*` and `fixture*` as a NAME PREFIX on both files and
directories, not `*/control/`. Ranked high because the failure is silent and destroys
deliberately-broken detector fixtures that cannot be regenerated from a formatter.

### R8 -- bucket (c), PROVEN: 48.9 MB / 2,997 files of caches.

| cache | files | bytes | regenerating command (executed, verified) |
|---|---|---|---|
| `__pycache__` | 1,640 | 46,630,944 | any `import` of the module |
| `.pytest_cache` | 69 | 1,923,240 | `python -m pytest` |
| `.ruff_cache` | 1,288 | 376,353 | `ruff check` |

Regeneration was PROVEN by execution in a throwaway sandbox, each with a both-states control:

* `__pycache__`: absent -> `python -c "import mod"` -> present -> deleted -> re-imported ->
  **byte-identical** (sha16 `166b25d927ab4d19` both times).
* `.ruff_cache`: absent -> `ruff check --cache-dir ...` -> present (3 files).
* `.pytest_cache`: control `pytest -p no:cacheprovider` -> **NOT created** (proves the probe
  distinguishes); normal `pytest` -> created.

Safety precondition, measured: **no cache directory lives inside a frozen-evidence path**
(`caches_inside_frozen == []`), so a cache sweep cannot touch frozen bytes.
All three are already in `.gitignore`, and `.github/workflows/no-runtime-junk.yml` already
fails the build if any of them is ever TRACKED -- so this is disk hygiene only, zero CI risk.

### R9 -- bucket (d): 13 empty directories, including a literal `~` directory.

```
apktool_mcp_server_workspace                      <- repo root, empty
platform/dist/stage/{bin,commands,hooks,lib/astplugin,schema}
platform/~/.adv0041-amp/out/stage/{bin,commands,hooks,lib/astplugin,schema}
tools/omniaudit-mcp/{data/reports,unused}
```

`platform/~/` is a Windows path-bug artifact -- a script wrote to `~/...` and Windows created a
directory literally named `~`. Measured: **0 files, 0 bytes**, NOT ignored, git-invisible
(git does not track empty dirs). It is the residue of adversarial probe `runtime_amplify.py`,
and the defect is already documented in the tracked
`command-center/adversarial/ADV-0041-path-and-identity-disclosure.json`.

DO NOT TOUCH YET: ADV-0041 is currently `M` (modified) in git status -- a sibling lane owns it.

### R10 -- `NUL` is a live 3,440-byte JSON log, not dead cruft.

Two independent signals: `os.path.isfile` on the plain path says False (Windows resolves `NUL`
to the null device) while the extended-length path `\\?\...\NUL` reports a real **3,440-byte**
file; `git check-ignore -v` confirms `.gitignore:6:NUL`. It grew 3,043 -> 3,440 B between two
measurements minutes apart, mtime 3.2 min old, then held steady.

Structure (classified, never printed): 26 records, LF-only, JSON with keys
`{hostname, level, msg, pid, time}` -- a **pino/bunyan-shaped Node.js logger**. No secret-shaped
tokens detected. `git grep "> *NUL"` over `scripts ci hooks tools platform` returns **0 hits**,
so the writer is not in tracked repo source.

**UNVERIFIED: which process writes it.** Settling experiment: run `handle64.exe NUL` (or
`Get-Process`-plus-openfile enumeration) while it grows, and inspect the `pid` field in the
records. Do not delete while a handle is open; deletion needs the `\\?\` prefix.

### R11 -- `skills/` vs `.agents/skills/` is SANCTIONED. Not slop. Do not "consolidate".

Guard executed read-only: `python ci/check_skill_dual_write.py` -> **rc=0**,
*"OK: no skills/ change lacks a .agents/skills/ counterpart."*

The architecture is documented in three tracked places: `AGENTS.md` (`.agents/skills/` is
authoritative, `skills/` a compatibility projection), `ci/check_skill_deploy_drift.py`
(vault->live reporter that deliberately REFUSES to copy, because 34 of 79 shared skills were
measured diverged and 8 live-ahead), and `tools/d001-dual-write/README.md` (filter-safe applier
that avoids a git-crypt smudge corruption path).

Residual, disclosed and NOT a defect: excluding `.pyc`, 1,764 files are shared, 21 exist only
under `skills/`, 179 only under `.agents/skills/`. The guard is change-scoped, not full-parity,
so this asymmetry is inside its envelope. Top-level entries present in one root only:

* only `skills/`: `harness-module-authoring`, `patent-fto-search`, `social-corpus-extraction`
  (+ the root manifests `.gitignore`, `DEPLOYED-MANIFEST.json`, `SKILLS-MANIFEST.md`)
* only `.agents/skills/`: `claim-verify-gate`, `qdx-rush`, `README.md`, and nine 210-231-byte
  `codex-*` stubs (`codex-audit`, `-brainstorm`, `-coordinate`, `-curate`, `-discuss`, `-fix`,
  `-governance`, `-review`, `-triage`).

The nine `codex-*` stubs each contain only frontmatter plus one line pointing at a
`codex_*` orchestration tool, and the live skill catalogue describes `codex-orchestrate`
(present in BOTH roots) as replacing exactly these nine. They are therefore **candidates** for
retirement -- but they carry no tombstone marker, and superseded-by-a-router is a product
decision, not slop. FLAG, do not delete.

### R12 -- the brief's "`_advver_M14` orphans, 77 files / 735 KB" is CORRECTED prior art.

Measured: **0** `advver`/`M14` paths exist anywhere inside this repo. The number comes from
tracked commit `18798852` (2026-08-11), which measured two NO-REMOTE working copies that live
OUTSIDE the repo at `C:/Users/Prekzursil/source/_advver_M14/`:

| clone | files | bytes | VARIANT | ORPHAN |
|---|---|---|---|---|
| `chk` | 7,770 | 84,269,383 | 350 | 77 |
| `scratch` | 7,802 | 84,569,164 | 348 | 77 |

Confirmed still on disk: 15,572 files / 168.8 MB total. "77 files" is the ORPHAN count *inside
each clone*, not an orphan set inside this repo, and 735 KB is those orphans' size -- not a
repo artifact. The work is DONE and COMMITTED as `command-center/OWNER-PACKET-2026-08-11.md`
plus `command-center/triage_noremote.py`, and the commit records the owner's standing decision:
**TRIAGE FIRST -- do not create remotes, do not push.** Out of this lane's file scope.
**The build lane must not redo this.**

### R13 -- `clean_markdown.py` is a 3-way divergence, NOT a deletable duplicate.

| path | bytes | sha256-16 (LF-normalised) |
|---|---|---|
| `clean_markdown.py` (repo root) | 3,285 | `a696ed32091ae6cefbcc` |
| `skills/consensus-tooluniverse-research/scripts/clean_markdown.py` | 4,606 | `e4396625042b012ea673` |
| `.agents/skills/.../scripts/clean_markdown.py` | 4,606 | `e4396625042b012ea673` |

The two skill copies are identical to each other (correct dual-write). The **root copy is a
different, smaller third variant** -- and it is specifically cataloged by a committed corpus
doc, `harness-sota-2026-07-18-corpus/P1B12.md:132` (`clean_markdown.py | 1 | 3,285 | Markdown
normalization helper`). Contents differ, so "they look similar" is not evidence. Needs a real
reconcile decision by an owner, not a deletion.

---

## BUCKET SUMMARY

| bucket | what | count | disposition |
|---|---|---|---|
| (a) evidence, already committed | `command-center/harvest/` (4 files, 1.04 MB, all tracked); all `command-center/*.md`/`*.json` reports; the 6 root `_refute_*`/`_f7_*` probes | -- | keep, no action |
| **(b) evidence, NOT committed** | 45 cited-but-ignored probe scripts (403,870 B) + 31 outputs whose producer is not in git + 198 pre-existing untracked files | 45 + 31 | **COMMIT (R1, R2). Do not delete.** |
| (c) reproducible scratch | 2,997 cache files, 48.9 MB, regeneration proven by execution | 2,997 | safe to sweep at a quiesce point (R8) |
| (d) dead | 13 empty dirs incl. the literal `~` tree; 2 stale outputs (223 / 362 min) | 15 | propose (R9); ADV-0041 blocked |

## WHY NOTHING WAS DELETED

Deliberate scoping decision, not an omission. Three measured reasons:

1. **Sibling lanes are live in this tree.** Untracked went 163 -> 215 during this run; 15 files
   carry 3-9 minute mtimes against a 4,490-minute control. A sweep now races concurrent writers.
2. **The bucket-(c) set is smaller than it looks.** 31 of 32 candidate outputs fail the
   definition's own test ("a COMMITTED script regenerates it"). Deleting before R1 lands
   converts recoverable evidence into loss.
3. **ADV-0041 is mid-edit by another lane**, and it is the artifact that documents `platform/~`.

The 48.9 MB cache sweep (R8) is the only genuinely unambiguous deletion, it is fully proven,
and it is worth ~0 to do tonight -- disk is not the constraint. Commands, for a quiesce point:

```powershell
# bucket (c) -- regeneration proven above; run only when no lane is executing python
Get-ChildItem -Path . -Filter __pycache__   -Recurse -Directory -Force |
  Where-Object FullName -notmatch '\\\.git\\' | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Filter .pytest_cache -Recurse -Directory -Force | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Filter .ruff_cache   -Recurse -Directory -Force | Remove-Item -Recurse -Force
```

## FROZEN EVIDENCE -- UNTOUCHED (verified twice)

`git status --porcelain` over `command-center/casualty/probes` and
`command-center/p2-wave/probes` returned **0 lines** at lane start and again at lane end.
A sha256-16 manifest of `casualty/probes` (7 files) and `p2-wave/probes/AUD-0006/control`
(2 files) is recorded in `_slop_measure6.out.json` for future comparison. No file under either
path was opened for write by this lane.

## ARTIFACTS

All under `command-center/slop-report/` (untracked; this lane's own scratch, itself bucket (b)):
`_slop_measure{,2,3,4,5,6,7}.py` + matching `.out.json`, `_slop_verify_regen.py` + `.out.json`.
Per R1's own logic, if this report is committed these producers should be committed with it.
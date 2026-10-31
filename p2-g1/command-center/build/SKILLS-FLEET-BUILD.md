# SKILLS FLEET — BUILD LANE (round 1) — FINAL ARTIFACT

> The skeleton sentinel ("If it still reads this way, the unit died before measuring anything")
> has been REPLACED. Every section below is either MEASURED with a command and its real output,
> or explicitly marked NOT DONE. Nothing here is `UNKNOWN - not yet measured` any more.

COVERAGE: A–G measured. H states exactly what is still open.

Lane: `skills` — consolidate, upgrade to SOTA, close the gaps.
Declared file scope: `.agents/skills/**` and `C:/Users/Prekzursil/.claude/skills.daily/**`.
Scope expansions taken (both judged correct, both load-bearing — see H3 for the one refused):
`skills/` (forced by the D-001 dual-write gate), `scripts/` + `ci/`-read (the missing deploy hop),
`.gitignore` (the vendored-clone mirror hole the reconcile itself would have fallen into).

## DoD ledger

| # | DoD item | verdict |
|---|---|---|
| D1 | harvested audit findings read and acted on | **PASS** — A |
| D2 | nothing merged/retired without both bodies read + landing place stated | **PASS** — nothing was merged or retired; the one merge performed (C3) had both bodies read line by line and its landing place is both repo roots |
| D3 | live-ahead drift reconciled into the repo before any redeploy | **PASS** — C |
| D4 | the 110 drifted files classified by a deterministic differ with its output shown | **PASS** — B |
| D5 | measured lessons encoded into the relevant skill bodies | **PASS (4 of 5 targets)** — E; the 5th was refused to avoid a live collision, H3 |

## A. Harvest + prior work read (D1)

Read as input: the five-lens harvest and the grounding lane's `SKILLS-FLEET-GROUNDING.md`.

**Correction to both the brief and the grounding lane: the sixth (overlap) lens is NOT missing.**
Both say it never completed. Commit `4d421333` recovered it from `~/.claude/_lens_overlap_*.json`
into `command-center/RECOVERED-OVERLAP-LENS.md`. Over 57 candidate pairs: body token Jaccard
**max 0.185, median 0.006** against a 0.30 merge floor — **0 pairs clear it** — while 34 of 57
score ≥0.35 on DESCRIPTION similarity. That inversion is the finding: apparent duplicates share
domain vocabulary in the always-loaded description and diverge almost completely in body.

Two mechanically independent measurements agree (this lens's token Jaccard on 57 candidate pairs;
the grounding lane's word-set Jaccard + 5-gram containment on all 53,628 pairs, max 0.560). So
"the fleet holds no textual near-duplicate cluster" is almost certain (90–99%). Neither measures
FUNCTIONAL redundancy — the settling experiment is reading both bodies, which the destructive
default already requires and which was not done fleet-wide. Likely (55–80%) that no pair is
functionally redundant either.

## B. Deterministic drift classification (D4) — MEASURED

Instrument: `ci/check_skill_deploy_drift.py`, already in-repo and never being run. LF-normalises
before comparing, never consults mtime, refuses to copy, emits `safe_to_deploy` only on a strict
superset.

```
$ python ci/check_skill_deploy_drift.py --left ~/.claude/skills.daily --right ~/.agents/skills
LEFT  ...\.claude\skills.daily (328 skills)   RIGHT ...\.agents\skills (328 skills)
  IDENTICAL 291   RIGHT-AHEAD 0   LEFT-AHEAD 4   DIVERGED 33
SAFE TO DEPLOY right->left (0 files)
NEEDS A HUMAN MERGE (110 files) -- never blind-copy these
```

That reproduces the briefed **110**. The axis this lane owns is the REPO, and it is 4.5x larger:

```
$ ... --left ~/.claude/skills.daily --right <repo>/.agents/skills     # BEFORE
  IDENTICAL 225  RIGHT-AHEAD 0  LEFT-AHEAD 2  DIVERGED 101
  needs_merge 490 files   safe_to_deploy 95
  file level: DIVERGED 192 | LEFT-ONLY-FILE 261 (+3 binary) | RIGHT-ONLY-FILE 93
              LEFT-AHEAD 3 | RIGHT-AHEAD 2
```

**RIGHT-AHEAD = 0 at skill level on both axes.** No bulk sync is provably safe in either
direction, on either axis.

## C. Live-ahead reconciliation into the repo (D3) — MEASURED AND APPLIED

### C1. The ui-audit green-no-op — CONFIRMED BY EXECUTION, then closed

A destructive claim settled by running it, not reading it (`_b6_guard_bothstates.ps1`):

```
--- through a JUNCTION (the documented ~/.claude/skills invocation) ---
REPO copy  (known-BROKEN)  exit=0 SILENT-NO-OP  out=
LIVE copy  (known-FIXED)   exit=1 MAIN-RAN      out=[axe_scan] ERROR: --url <url> required
--- CONTROL: direct real path, no junction (both must run) ---
REPO copy  direct          exit=1 MAIN-RAN      LIVE copy direct  exit=1 MAIN-RAN
```

Cause: `~/.claude/skills` is a junction to `skills.daily`; Node resolves symlinks for ESM so
`import.meta.url` reports the REAL path while `resolve(argv[1])` stays lexical, so the compare
never matches and `main()` never runs. After reconciling, the repo copy runs through the junction
(`exit=1 MAIN-RAN`). Any "ui-audit passed" produced from the old repo bytes was vacuous.

### C2. What was copied (59 files) and why each class cannot lose repo content

| class | n | why safe |
|---|---|---|
| LEFT-ONLY-FILE | 50 | the repo has no bytes at that path |
| LEFT-AHEAD | 3 | the live line-set strictly contains the repo's |
| ui-audit entry points (DIVERGED, hand-audited) | 6 | see below |

Two-directional differ (`_b4_uiaudit_diff.py`): 5 of the 6 have exactly **1** repo-unique line —
the buggy lexical guard the fix replaces — against 12 live-unique (329 − 1 + 12 = 340, and the
same arithmetic closes on all five). `critique.mjs` has 19 repo-unique lines, each with a verified
live superseding equivalent (nine dimensions not eight, `reconcile` mode, personas, expanded
usage); the one dropped import symbol `basename` has **0** uses in the live file. `node --check`
passes on all six.

### C3. UNION MERGE where the divergence was genuinely two-directional

`schrodinger-maestro-driver/SKILL.md`, the only file the mechanical rule refused:

| tree | lines | content |
|---|---|---|
| repo `skills/` (projection) | 111 | 67-tool surface, 2026-2, toolchain path — **no** Multi-GPU section |
| repo `.agents/skills` @HEAD | 81 | 12-tool, 2022-4, old `source/repos` path |
| live `skills.daily` | 89 | stale text **plus** a unique `## Multi-GPU pool … jobserverd` section |

`grep -c 'Multi-GPU pool'` → 0 / 1 / 1. Neither side is a superset. `_b8_schrod_union.py --apply`
grafts the 8-line live-unique block into the newer body ahead of `## Common Mistakes`. Both roots,
byte-identical, 12,395 B, `67Tools=1 MultiGPU=1 jobserverd=1 2026-2=4`.

### C4. Deliberately NOT copied — 211 files

* **199 files / 4.97 MB `crypto-ctf/RsaCtfTool/`**, a vendored third-party checkout. `.gitignore`
  already excluded it under `skills/` — but `git check-ignore` returned **NOT-IGNORED** for the
  `.agents/skills/` dual-write mirror and **IGNORED** for the `skills/` twin *in the same run*.
  The live→repo reconcile this DoD mandates would have swept a third-party clone into git through
  the mirror. Ignore now covers both roots; re-checked → both IGNORED.
* **12 files `cv-studio/cv-studio/**`**, the skill nested inside itself. The prior audit says DROP;
  dropping is destructive and this lane defaults hard to KEEP, so it is reported, not removed.

### C5. Dual-write parity, and how the refusal earned its keep

`_b7_dualwrite_mirror.py`'s precondition (projection must be ABSENT or byte-identical to
canonical@HEAD) **refused exactly 1 of 59**, and that one file was the genuine three-way split in
C3. A precondition that never refuses is not a precondition. 58 mirrored, 0 byte-mismatches,
`ci/check_skill_dual_write.py --staged --strict-parity` → OK.

### C6. Post-reconcile drift

```
needs_merge 490 -> 431 files (-59, exactly the files copied);  LEFT-AHEAD (file level) 3 -> 0
remaining 245 LEFT-ONLY-FILE = 199 vendored + 12 nested + 31 .bak- snapshot + 3 binaries
```
(Fully accounted — no unexplained residue.)

## D. Consolidation decisions (D2)

**NOTHING MERGED, NOTHING RETIRED.** Two independent overlap measurements put the fleet far below
any merge floor (A), adversarial clearance never ran, and the owner condition was "no ability
lost". The single merge performed (C3) is additive in both directions.

Not attempted: the description-budget lever (de-curating the 23 `source-command-*`; deploying the
committed 75-skill description cap). See H2 — and note E/C where I nearly shipped that cap by
accident.

## E. Lessons encoded into skill bodies (D5) — 4 of 5 targets

Rationale for editing BODIES and not descriptions: descriptions are always-loaded (the scarce
resource, and 26 skills are already dark for want of it); bodies load only on invocation.

1. **two-tier-verify** — new section "Three ways a green OUTER loop still lies": working-tree
   green ≠ clone green (3,910 in-tree passes vs 31 collection errors cold), local formatter green
   ≠ CI formatter green with the blob recipe, and a green suite ≠ a green detector. Also routes
   the two dark instruments: `tools/detector-self-test/` had **ZERO** references outside its own
   directory before this and grep now returns exactly one — that count IS the routing fix.
2. **rubric-verifier** — coverage is necessary, not sufficient; explicit ordering rubric-rank
   (advisory) → coverage (may BLOCK) → held-out golden journey against the packaged artifact
   (may DECLARE DONE).
3. **devtu/modes/fix-tool** — the `grep -c` doubled-zero trap, with a hit-case control.
4. **The blob recipe was re-measured, not quoted** (`_b9_blob_recipe.py`), two files, control
   requiring all routes byte-identical after LF-normalisation:
   `git show`/`git cat-file -p` → 7,487 B / **0 CRLF**; `git archive`+`tar -x` and worktree →
   7,627 B / **140 CRLF**. Confirms the program's correction: `git show <rev>:<path>` is a valid
   blob check; only `git archive` is the trap.
5. **NOT DONE** — the same correction at `workflow-authoring/templates/governed-run-orchestrator.md:1145`.
   See H3.

**An overclaim I caught in my own text before shipping it:** I wrote that `blobread` was CI-wired
alongside its measure-guard siblings. It is not — grep returns ONE hit in the workflows,
`quality.yml:416`, and that line is a *comment*. `suitefloor`/`refcheck`/`wudeps`/`jsonparse`/
`vendordrift` genuinely execute (`:114`, `:439-443`). The sentence was corrected to say so, and to
say why: count the step, not the mention.

## F. The missing deploy hop, and its gate (root cause)

`scripts/deploy-skills-daily.py` — the hop no script in `scripts/` or `ci/` performed. Four
properties, each enforced and self-tested: P1 copies only `safe_to_deploy`; P2 never resurrects a
skill (**18** repo-only skills measured, including the **9** retired `codex-*` wrappers); P3 never
deletes (`microsoft-foundry` + `qdx-rush` are the measured prune casualties); P4 dry-run by
default and `--apply` runs `--self-test` first, so the gate re-proves itself on every real use.

**My self-test was partly a no-op and my own mutation harness caught it.** Three mutants; two
died; **P2 SURVIVED** — because `safe_to_deploy` is built from SHARED skills only, a repo-only
skill never reaches the P2 guard, so "no repo-only skill was copied" stayed true with the guard
deleted. That assertion was measuring the drift reporter, not the tool. Fixed by extracting a
callable `deployable()` seam and testing it directly, plus a control that it still ACCEPTS a
present skill. Now `SUCCESS:deploy-gate-mutation survivors=0/3`.

Deployed **3** skills (the ones this wave edited), not the available 98 — a full live deploy is
owner-gated. Verified in the tree Claude Code reads.

**The deploy exposed a trap I had walked into.** two-tier-verify and rubric-verifier came back
DIVERGED for one reason: live holds the LONGER `description:` and the repo holds a shortened one
(the never-deployed cap). Deploying my body edit would have silently shortened two descriptions by
**282** and **307** characters as a side effect of a docs commit — precisely the wrong direction
on a fleet whose recall surface is already over budget. Union taken the safe way: keep the LIVE
description, keep the NEW body. Both roots now 671 / 714 chars, identical to live.

## G. Detector controls (both-states) — what proves each probe fires when broken

| probe | evidence it fires in the BROKEN state |
|---|---|
| `_b6_guard_bothstates.ps1` | REPO-through-junction `exit=0 SILENT-NO-OP` vs LIVE `exit=1 MAIN-RAN`, **plus** a direct-path control where BOTH run — so it measures the guard, not "the repo file is broken" |
| `_b10_deploy_mutation.py` | 3 mutants (guard deleted / safe-list widened / prune added) all turn the self-test RED; it found a SURVIVOR first and that survivor was a real hole |
| `_b7` mirror precondition | refused 1 of 59, and that one was the genuine three-way split |
| `git check-ignore` | IGNORED and NOT-IGNORED printed for the two roots in the same run |
| `_b9_blob_recipe.py` | control requires all four routes byte-identical after LF-normalisation, so a CRLF delta cannot be a content delta. **Its first revision printed `CRLF=7488` for a 7,487-byte file** — a count larger than the payload is a self-contradicting output, so it was fixed as a detector failure before being read |
| `grep -c` trap | verified with BOTH a miss (`"0\n0"`, 2 lines) and a hit control (`"1"`, 1 line) |

## H. Residual — what is NOT done, honestly scoped

1. **431 files still need a human merge on the repo axis** (was 490). Every one is genuinely
   two-directional; none is safe to bulk-copy. This is a read-both-sides backlog, not a bug.
2. **The description-budget lever was not pulled.** De-curating the 23 `source-command-*` and
   deploying the committed 75-skill cap are the grounding lane's R1. NOT DONE deliberately: the
   26-dark set is usage-dependent so a before/after cannot be controlled from inside a subagent,
   the startup truncation warning is not readable from here, and the trade (trigger vocabulary for
   index budget) is exactly the kind of destructive-ish call the missing adversarial lens was
   supposed to clear. Section F shows I would have made this change *by accident* on two skills —
   which is the argument for doing it deliberately or not at all.
3. **`workflow-authoring/templates/governed-run-orchestrator.md:1145` still teaches the wrong blob
   recipe.** I made the edit and REVERTED it: the `skills/` projection of that exact file had been
   modified by a concurrent agent **55 seconds** earlier (an H6 timeout/heartbeat barrier block,
   since landed as `1f05e805`). Landing my canonical-side edit would either break D-001 byte parity
   or drag their uncommitted work into my commit. Ready-to-apply replacement: swap
   `git archive <final-sha> | tar -x -C <fresh-temp>` for
   `git show <final-sha>:<path>` and keep the `git archive` at ~:2173 (legitimate packaging).
4. **`cv-studio/cv-studio/**` nested self-copy** left in place in both trees (KEEP default).
5. **`ci/check_skill_deploy_drift.py` has a minor noise-filter gap**: `is_noise()` tests the
   `.bak-` infix only on the LEAF, so a `.bak-<tag>` *directory* leaks through and inflates
   needs_merge by 31 files. Not fixed here — changing the shared differ mid-wave would move
   numbers other lanes are quoting. One-line fix: test every path part, not just the leaf.
6. **`--only` and the deploy tool have no pytest suite.** `ci/tests/` has NO tree-wide CI step
   (`quality.yml:599` says so explicitly), and `quality.yml` was dirty under a concurrent edit, so
   adding a test file there would have been a suite that never runs — the exact no-op-gate class
   this lane is arguing against. Mitigated by making `--self-test` a precondition of `--apply`
   instead, which executes on every real use.

## I. Commits

| commit | content |
|---|---|
| `3678417c` | the C reconciliation — 122 files, +13,502 / −83 |
| `40917d77` | the E lesson encodings — 8 files, +289 |
| `772159ce` | **carries my F work but is a sibling's commit.** A concurrent agent's blanket `git add` swept my staged deploy tool, mutation harness, description union and `_commit3.txt` into their commit while I was verifying. Nothing was lost and nothing of theirs was taken by me — but the reasoning for that change is in `command-center/build/_commit3.txt`, not in the log message above it. Recording it here because a silent mismatch between a commit message and its contents is worse than an awkward one. My own foreign-path check caught 26 of THEIR paths in my staging area in the same window and unstaged them, which is why this is a message problem and not a contamination problem. |

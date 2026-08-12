# SKILLS FLEET — BUILD LANE (round 1) — LIVE ARTIFACT

> **If it still reads this way, the unit died before measuring anything and no verdict here may be cited.**
> (That sentence is the skeleton sentinel. Sections below that still say `UNKNOWN - not yet measured`
> are genuinely unmeasured; sections marked MEASURED carry a command and its real output.)

COVERAGE at this rewrite: A, B, C MEASURED. D partially measured. E, F, G in progress.

Lane: `skills` — "Skill fleet: consolidate, upgrade to SOTA, and close the gaps".
File scope owned: `.agents/skills/**` and `C:/Users/Prekzursil/.claude/skills.daily/**`.

## DoD ledger

| # | DoD item | state |
|---|---|---|
| D1 | harvested audit findings read and acted on | MEASURED — see A |
| D2 | nothing merged or retired without both bodies read + landing place stated | MEASURED — see D; **nothing was merged or retired** |
| D3 | live-ahead drift reconciled into the repo before any redeploy | MEASURED — see C |
| D4 | the 110 drifted files classified by a deterministic differ with its output shown | MEASURED — see B |
| D5 | measured lessons encoded into the relevant skill bodies | IN PROGRESS — see E |

## A. Harvest + prior work read (D1)

The five-lens harvest and the grounding lane's `SKILLS-FLEET-GROUNDING.md` were read as input.
**The sixth (overlap) lens is NOT missing** — the brief and the grounding lane both say it never
completed, but commit `4d421333` recovered it from `~/.claude/_lens_overlap_*.json` and committed
`command-center/RECOVERED-OVERLAP-LENS.md`. Its verdict over 57 candidate pairs: body token
Jaccard **max 0.185, median 0.006**, merge floor 0.30, **0 pairs clear it**, while 34 of 57 pairs
score >= 0.35 on DESCRIPTION similarity. That inversion is the finding: the pairs that look like
duplicates share domain vocabulary in the always-loaded description and diverge almost completely
in body. Two mechanically independent measurements (that lens's token Jaccard on 57 candidate
pairs; the grounding lane's word-set Jaccard + 5-gram containment on all 53,628 pairs, max 0.560)
agree. Confidence almost certain (90-99%) that no textual near-duplicate cluster exists.

## B. Deterministic drift classification (D4) — MEASURED

Instrument: `ci/check_skill_deploy_drift.py` (already in-repo; LF-normalises before comparing,
never consults mtime, refuses to copy, emits `safe_to_deploy` only on a strict superset).

```
$ python ci/check_skill_deploy_drift.py --left ~/.claude/skills.daily --right ~/.agents/skills
LEFT  C:\Users\Prekzursil\.claude\skills.daily  (328 skills)
RIGHT C:\Users\Prekzursil\.agents\skills        (328 skills)
shared: 328
  IDENTICAL 291   RIGHT-AHEAD 0   LEFT-AHEAD 4   DIVERGED 33   REORDER-ONLY 0
SAFE TO DEPLOY right->left (0 files):
NEEDS A HUMAN MERGE (110 files) -- never blind-copy these
```

That reproduces the briefed **110**. But the axis this lane owns is the REPO, not the vault:

```
$ python ci/check_skill_deploy_drift.py --left ~/.claude/skills.daily \
      --right <repo>/.agents/skills            # BEFORE this lane's work
IDENTICAL 225  RIGHT-AHEAD 0  LEFT-AHEAD 2  DIVERGED 101
needs_merge 490 files   safe_to_deploy 95 files
file-level: DIVERGED 192  LEFT-ONLY-FILE 261+3 binary  RIGHT-ONLY-FILE 93  LEFT-AHEAD 3  RIGHT-AHEAD 2
```

**RIGHT-AHEAD = 0 on both axes**: there is no file anywhere for which a vault->live or repo->live
copy is provably safe. Confirms the grounding lane; a bulk sync in either direction destroys
unique content.

## C. Live-ahead reconciliation into the repo (D3) — MEASURED, APPLIED

### C1. The ui-audit green-no-op destruction path — CONFIRMED BY EXECUTION, then closed

The prior audit claimed a repo->live redeploy reverts ui-audit to a silent green no-op. That is a
destructive claim, so it was settled by running it, not by reading it
(`command-center/build/_b6_guard_bothstates.ps1`, a junction + a direct-path control):

```
--- through a JUNCTION (the documented ~/.claude/skills invocation) ---
REPO copy  (known-BROKEN)    exit=0 SILENT-NO-OP  out=
LIVE copy  (known-FIXED)     exit=1 MAIN-RAN      out=[axe_scan] ERROR: --url <url> required
--- CONTROL: direct real path, no junction (both must run) ---
REPO copy  direct            exit=1 MAIN-RAN      out=[axe_scan] ERROR: --url <url> required
LIVE copy  direct            exit=1 MAIN-RAN      out=[axe_scan] ERROR: --url <url> required
```

The probe DIFFERS in the broken state and the control proves the difference is junction-specific
(both copies run when invoked directly), so the instrument measures the guard and not "the repo
file is simply broken". Root cause, from the live comment: `~/.claude/skills` is a junction to
`skills.daily`, Node resolves symlinks for ESM so `import.meta.url` reports the REAL path while
`resolve(argv[1])` stays lexical — the compare never matches and `main()` never runs.

Reconciled into the repo and re-run: `REPO copy exit=1 MAIN-RAN`. The destruction path is closed.

### C2. What was copied, and why each class is non-destructive

`command-center/build/_b5_reconcile.py --apply` — 59 files:

| class | n | why safe |
|---|---|---|
| LEFT-ONLY-FILE | 50 | the repo has no bytes at that path; nothing can be lost |
| LEFT-AHEAD | 3 | live line-set strictly contains the repo's |
| ui-audit entry points (DIVERGED, hand-audited) | 6 | read line-by-line, see below |

The 6 DIVERGED ui-audit files were read with a two-directional differ (`_b4_uiaudit_diff.py`):
5 of them have exactly **1** repo-unique line — the buggy lexical guard the fix replaces — against
12 live-unique lines (arithmetic checks: 329 − 1 + 12 = 340). `critique.mjs` has 19 repo-unique
lines and every one has a verified live superseding equivalent (nine dimensions not eight,
`reconcile` mode, personas, expanded usage strings); the single dropped import symbol `basename`
has **0** uses in the live file. `node --check` passes on all six after the copy.

### C3. UNION MERGE where the divergence was genuinely two-directional

`schrodinger-maestro-driver/SKILL.md` is a real three-way split and the ONLY file where the
mechanical rule was refused by its own precondition:

| tree | lines | content |
|---|---|---|
| repo `skills/` (projection) | 111 | 67-tool surface, 2026-2, toolchain server path — **no** Multi-GPU section |
| repo `.agents/skills` @HEAD | 81 | 12-tool surface, 2022-4, old `source/repos` path |
| live `skills.daily` | 89 | same stale text **plus** a unique `## Multi-GPU pool … jobserverd` section |

`grep -c 'Multi-GPU pool'` → projection 0, canonical 1, live 1. Neither side is a superset, so
either one-directional copy loses content. `_b8_schrod_union.py --apply` grafts the 8-line
live-unique block into the newer projection body ahead of `## Common Mistakes`. Result, both
roots, byte-identical (12,395 B): `67Tools=1 MultiGPU=1 jobserverd=1 2026-2=4`.

### C4. Deliberately NOT copied — 211 files

* **199 files / 4.97 MB `crypto-ctf/RsaCtfTool/`** — a vendored third-party checkout.
  `.gitignore:41` already excluded it under `skills/`, but **`git check-ignore` proved the
  `.agents/skills/` DUAL-WRITE MIRROR was NOT ignored**, so the live->repo reconcile this DoD
  mandates would have swept a third-party clone into git through the mirror path. `.gitignore`
  now covers both roots; re-checked → both IGNORED.
* **12 files `cv-studio/cv-studio/**`** — the skill nested inside itself. The prior audit says
  DROP; dropping is destructive to the live tree and this lane defaults hard to KEEP, so it is
  reported and left untouched in both trees.

### C5. Dual-write parity (D-001)

`ci/check_skill_dual_write.py --strict-parity` requires a changed path to have a byte-identical
counterpart in the other root, so `_b7_dualwrite_mirror.py` mirrored the reconcile into `skills/`.
Its safety precondition — the projection must be ABSENT or byte-identical to canonical@HEAD —
**refused exactly one file** (`schrodinger-maestro-driver/SKILL.md`), which is how the three-way
divergence in C3 was discovered rather than silently overwritten. 58 mirrored, 0 byte-mismatches.

### C6. Post-reconcile drift

```
needs_merge 490 -> 431 files   (-59, exactly the files copied)
LEFT-AHEAD (file level) 3 -> 0
remaining LEFT-ONLY-FILE 245 = 199 crypto-ctf vendored + 12 cv-studio nested
                              + 31 .bak- snapshot dir + 3 binaries   (fully accounted)
```

## D. Consolidation decisions (D2)

**NOTHING WAS MERGED AND NOTHING WAS RETIRED.** Two independent overlap measurements (A) put the
whole fleet far below any merge floor, the adversarial clearance stage never ran, and the owner
condition was "no ability lost". The only structural change is the C3 union merge, which is
additive in both directions.

UNKNOWN - not yet measured: the description-budget lever (de-curating the 23 `source-command-*`
from `skills.daily`, deploying the committed 75-skill description cap). Not attempted in this
round.

## E. Lessons encoded into skill bodies (D5)

UNKNOWN - not yet measured.

## F. Detector controls (both-states)

| probe | proves it fires in the BROKEN state |
|---|---|
| `_b6_guard_bothstates.ps1` | REPO copy through a junction → `exit=0 SILENT-NO-OP`; LIVE copy → `exit=1 MAIN-RAN`. Plus a direct-path control where BOTH run, so the probe is not just "repo file is broken". |
| `_b7_dualwrite_mirror.py` precondition | fired on 1 of 59 files (schrodinger), which is the file that genuinely had unique projection content. A precondition that never refuses is not a precondition. |
| `git check-ignore` | printed IGNORED for `skills/crypto-ctf/RsaCtfTool/…` and NOT-IGNORED for the `.agents/` twin in the same run — the two-state read is what exposed the gap. |

## G. Commits

UNKNOWN - not yet measured.

## H. Residual / not done

UNKNOWN - not yet measured.

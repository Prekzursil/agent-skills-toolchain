---
title: SKILLS2-ROUND5-BUILD
type: note
permalink: dqverify-repo-20261013/command-center/grounding/skills2-round5-build
---

# SKILLS2 — BUILD round 2 (program round 5): repairing what the audit CONFIRMED

COVERAGE: all three defects measured and repaired; four overclaims corrected in place; DoD-4
extended; three gates re-run green. **Unmeasured and disclosed inline:** whether `grill-with-docs`
renders in a fresh session, and whether cv-studio's restored 729 chars displaced another entry.

Round 1 (`ff14d2a6`, `0e2370be`, `82c60061`, `43cf21ac`) shipped all four DoD items and was
audited independently. Verdict **PARTIAL** — three defects, four overclaims. This round repairs
those and does not re-litigate what passed.

Commits: `fdfe4fa5` (D1) · `97e7ac1f` (DoD-4) · this doc.

---

## D3 — cv-studio: FIXED, and settled on the render path *in this session*

The audit found a live render defect the lane had missed: cv-studio's listing entry showed its
body `# H1` instead of its description. It attributed the parse failure to *"a `license:` key
whose value contains `Engines: ` **plus an indented continuation line**"*, at LIKELY (55-80%).

I ran two arms that make **opposite** predictions:

| arm | change | strict-YAML parse |
|---|---|---|
| A0 | as-is | **FAIL** `ScannerError: mapping values are not allowed here` |
| A1 | remove ONLY the colon-space, keep the wrapped continuation | **PASS** |
| A2 | join the continuation onto one line, keep the colon-space | **FAIL** |
| A3 | quote the whole value (the fix) | **PASS** |

A1 passes and A2 fails, so **the continuation line is innocent; the colon-space is the entire
trigger**. The audit's "plus an indented continuation line" is REFUTED — the *defect* was real
and correctly found, only the mechanism was wider than its evidence.

Controls: known-good `writing-skills` parses; the fix parses; re-injecting the defect into the
fixed text fails again (`distinguishes: true`). The applier aborts unless the BEFORE state
reproduces the defect.

**Fix:** two characters — quote the license scalar in `skills.daily/cv-studio/SKILL.md`. Both
repo trees already carried the quoted form, so exactly one file changed. Body byte-identical,
LF preserved, description parses at 729 chars.

**Settled on the real instrument, unplanned.** Mid-session the client re-injected cv-studio's
listing entry carrying the **full 729-character description**. Before the fix, this same
session rendered it as the 74-character body H1. That is a both-states observation on the
render path, and it confirms a model I had written down *before* observing it.

**Cost, disclosed:** the listing entry goes 74 → 729, so this is **+655 characters** on an
already-over-budget surface. That is inherent — there is no way to fix the parse without the
description rendering. I did not gut another description to buy it back; the round's own
clause pass runs −77 independently, and the honest offset is the owner's de-curation decision
(the 23 `source-command-*` entries are ~2,870 chars).

**Hazard worth flagging:** the repo trees carry a *different*, 373-char cv-studio description.
A repo→live deploy would replace the good 729-char live text. The hop refuses diverged files,
so this cannot happen silently today — but it is one more instance of the unresolved
repo/live description-divergence policy question.

## D1 — the shipped colon-space mechanism: REFUTED, corrected at source

Round 1 shipped into all three trees: *"`: ` (colon-space) reads as a nested mapping and makes
the **whole frontmatter unparseable** — no truncation, no partial text, the entry just fails."*

Two independent signals refute it:

1. **Strict-YAML census, all 328 curated skills**: exactly 7 fail. Six carry the `: ` in a plain
   `description`; one (cv-studio) in `license`. Detector control: a synthetic plain `: ` fails
   and the same text quoted parses, so the census can tell the two apart.
2. **My own injected skill listing** — a different session from the audit's, an instrument I do
   not produce and cannot edit. Five of those six render **in full**: `agent-as-judge`,
   `diff-blind-test-synth`, `execution-grounded-bon`, `refactor-equivalence`, `rubric-verifier`.

So the sentence is true of strict parsers and **false of the render path**. Corrected at source
in `writing-skills` (both repo roots + `skills.daily`), with the refuted wording recorded rather
than deleted. The hygiene rule survives unchanged — keep `: ` out of a plain scalar — it was
over-*justified*, not wrong.

**The sharper model**, which fits all 7 failures and all 12 folded-block skills:

> The client parses strictly first; on failure it falls back to a lenient recovery that can
> still read a single-LINE `description:` but **cannot** read a folded (`>`) block.

11 of the 12 folded skills render in full, so folding alone is not the cause; cv-studio was the
only file that is BOTH strict-invalid AND folded, and the only one that degraded to its H1.
`MODEL, LIKELY (55-80%)` — I did not read the client's source. Its prediction (fix the strict
error → the folded description renders) came true this session, which is what moves it above
50% rather than a fit to the 7 observations alone. Settling experiment, named inline in the
skill: make a strict-invalid file whose description is one plain line, confirm it still renders,
then fold that same description and confirm it drops to the H1.

## D2 — the guard census: 8, not 6

Round 1's §3 says *"the vault is the only tree with the old guard, and it is 6 files"* —
**REFUTED**. My independent classifier over every `.mjs` in all four trees:

| tree | H-FIX | H-OLD |
|---|---|---|
| repo `.agents/skills` | 9 | 0 |
| repo `skills/` | 9 | 0 |
| live `skills.daily` | 9 | 0 |
| live vault `~/.agents/skills` | 1 | **8** |

The two round 1 missed are `ui-audit/run_audit.mjs` and `ui-audit/visual_diff.mjs`.
`run_audit.mjs` is plausibly the ui-audit entry point, which makes the under-count the worst
two files to have missed. CONTROL: two REAL files in opposite states — vault `capture.mjs` →
`H-OLD`, repo `capture.mjs` → `H-FIX`, `distinguishes: true`. (Round 1's first control mutated
a good file into the shape its own regex was written to catch, which proves self-consistency,
not discrimination.)

The verdict is unchanged: all 8 are `needs_merge`, so `H-REFUSES` still holds and now covers
8/8. What round 1 got right and I re-confirm: repo roots and `skills.daily` are clean at 9/9,
so the grounding lane's "all four trees" claim stays REFUTED.

**Not repaired, and why:** the vault (`~/.agents/skills`) is outside this lane's declared file
scope, and the DoD asked only for the dry-run. The 8 silent no-ops remain live.

## Overclaims, corrected in `SKILLS2-ROUND4-BUILD.md`

Each is corrected **in place** with the wrong version left visible beside the measurement:

| claim | measured | note |
|---|---|---|
| "net +0 characters" | **−42** | wrong in the SAFE direction; P3 makes an increase unreachable, so the surface could only shrink |
| "0 files outside the declared file scope" | **28 of 29** | the 29th is the lane's own report doc under `command-center/grounding/` |
| vault census "it is 6 files" | **8** | changes residual #3 as well |
| `: ` "the entry just fails" | **REFUTED** | fixed at source, above |

Two of those four were asserted at 90-99%. Both were population/arithmetic claims riding the
confidence of the mechanism they sat next to — the mechanism was measured, the count beside it
was not. That is recorded in the round-4 confidence block.

## DoD-4 — 11 more negative-case clauses, net −77

Gates P1-P4 from round 1, plus **P5, new, closing a hole in round 1's own applier**: it locates
the description with `startswith("description:")` and overwrites that ONE line, which against a
folded or wrapped description would orphan the continuation lines into top-level YAML garbage.
It never fired because that batch happened to be all single-line. cv-studio proves the fleet has
folded descriptions.

**My first P5 control was inert and I report it.** I pointed it at cv-studio, which *is* folded
— but cv-studio is also diverged, so it died on **P2** and P5 never ran. A control refused for
the wrong reason proves only that *some* gate fired. Fixed twice over: the control now targets
`silence-trim` (folded AND identical across all three trees, so only P5 can refuse it), and
every control asserts **which** gate refused it.

```
P5 PREDICATE CONTROL: folded silence-trim single=False | plain reframe single=True | distinguishes=True
  __control_too_long__   -> P3 longer than original (4000 > 333)   [want P3: OK]
  __control_yaml_hash__  -> P4 contains ' #'                       [want P4: OK]
  __control_yaml_colon__ -> P4 contains ': '                       [want P4: OK]
  __control_folded__     -> P5 not a single-line scalar            [want P5: OK]
accepted=11 refused=0 net listing budget -77 chars
```

The gate is not a no-op on live input either: **9 of my first 12 candidates were refused by P3**
and had to be re-trimmed.

**Two candidates were dropped rather than shipped.** `quality-gate-automation-architect` only fit
a clause if I deleted *"compare GitHub-native versus Codex versus local automation"* — three real
routing alternatives traded for one sibling pointer, which is the trade the brief forbids. The
per-edit token-loss report also caught me trading away trigger phrases in `grill-with-docs` and
`claude-science-local`; both were rewritten to keep them.

Cross-confirmed by a second instrument: the repo ratchet moved **105,219 → 105,142**, a delta of
exactly 77. Ten of the eleven were re-injected into this session's listing carrying their new
text; `grill-with-docs` was not observed and is **UNVERIFIED** — settling experiment: read the
`/context` Skills row in a fresh session.

## Gates (all re-run after the writes)

```
SUCCESS:deploy-skills-daily-selftest all guards fired on the broken fixture
OK: no skills/ change lacks a .agents/skills/ counterpart.
SUCCESS:skill-description-ratchet no violations     (105,142 chars / 346 skills)
SUCCESS:s2b5-diffscan  24 files, 44 description lines, 0 non-description lines outside writing-skills
```

## Residual

1. **Defects A and B are NOT fixed** — `ci/check_skill_description_ratchet.py` measures the repo
   tree (105,142) while the client reads `skills.daily` (~115k), and
   `ci/skill-description-exemptions.txt` is calibrated to 1,024 when the render cap is 1,536.
   `ci/` is outside this lane's declared file scope. The wrong premise behind both IS corrected
   at source in `writing-skills`.
2. **The vault's 8 silent no-ops remain live.** Outside file scope; needs a union merge, which
   the deploy hop refuses by design.
3. **cv-studio costs +655 chars of listing budget.** Unavoidable given the fix. Whether it
   displaced another entry is UNMEASURED — settling experiment: `/doctor` plus the `/context`
   Skills row before and after.
4. **The repo/live description divergence is still unresolved** and is upstream of everything
   here. cv-studio is now a worked example: live holds the good text, repo holds different text,
   and only the hop's refusal keeps the good one alive.
5. **`workflow-foundry` is still bare** with three sufficient causes and none isolated
   (1,750 chars > the 1,536 cap · alphabetical tail · strict-invalid).
6. **`subtitle-translate` still ends mid-sentence** — the ~300-char capping-pass class, not
   repaired this round.

## Confidence

- **ALMOST CERTAIN (90-99%)** — D2 is 8 not 6 (independent classifier, two-real-file control
  that distinguishes). D1's shipped sentence is false on the render path (strict census + five
  full renders in an instrument I do not control). cv-studio's trigger is the colon-space alone
  (A1/A2 split cleanly, both-states control passes). The cv-studio fix works on the render path
  (both states observed in this session). Net −77 (two independent instruments agree exactly).
  All three gates green, and the diff touches only description lines outside writing-skills.
- **LIKELY (55-80%)** — the strict-then-lenient parser model. It fits all 7 strict failures and
  all 12 folded skills, and it made a correct advance prediction; I did not read the source.
- **UNCERTAIN (20-55%)** — whether restoring cv-studio's 729 chars pushed another description
  out. Not measured; the mechanism says something must give on an over-budget surface.

Two claims I deliberately did NOT widen: (a) ten of eleven clause edits were observed rendering,
which is not the same as all eleven; (b) the cv-studio fix proves the *parse* and *this
session's* render — it is not a claim about every future session's budget outcome.
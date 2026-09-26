---
title: Prompt Two waves 4-5 + platform CI lane 2026-08-10
type: report
permalink: main/projects/prompt-two-waves-4-5-platform-ci-lane-2026-08-10
tags:
- prompt-two
- ci
- measurement-integrity
- ast-integrate
- verification
---

# Prompt Two waves 4-5 + the platform CI lane (2026-08-10)

Repo `~/source/ast-integrate` (a worktree of `agent-skills-toolchain` holding `main`). Wave 4
completed 9/9 agents; then ~15 commits of follow-up. Main green except one self-inflicted break,
fixed. **HEADLINE: a working-tree-green test suite could not even COLLECT on a fresh clone.**

## The single most transferable lesson

`pytest platform` reported **3,910 passed on the working tree**. A `git clone` of the SAME COMMIT
gave **31 collection errors, aborted in 7.5s**. The working tree contained untracked files a runner
never has. Four rounds against real clones: 31 errors -> 8 -> 6 failures -> **3,915 passed**.

**Run a real `git clone` before wiring any CI gate.** Had the `platform/` lane been wired on the
working-tree measurement it would have been red on its first execution. A static import scan is NOT
a substitute — it found the `import _harness` cases and missed `from . import _libpath` (name in the
import LIST, not the module path) and missed both DATA dependencies entirely (a filename in a pytest
parametrize list; a path passed to subprocess).

## The `/_` scratch exclusion silently deleted NINE deliverables

Every commit script in the program excluded `/_` paths as agent scratch. Victims, all found in one
session: two `platform/workflows/_shared/*.subworkflow.json` that THREE COMMITTED BLUEPRINTS
reference; `command-center/schema/_meta/json-schema-2020-12.json`, the 233rd schema file that
`config-first.md:416` names as a test's non-vacuous control; `_mutation_selfcheck.py` (its fix sat
uncommitted while HEAD reported `survivors=[1..12]`); four test-support modules imported by 26 tracked
tests; and `platform/coordination/_libpath.py`, which is PRODUCTION code imported by `session.py`,
`adapters.py`, `handoff.py`.

**Discriminator, cheap and never applied: an untracked path REFERENCED BY TRACKED CONTENT is a
deliverable, not scratch.** Asymmetric on purpose — a false "deliverable" costs one reviewable file, a
false "scratch" deletes a dependency. Tool: `~/.claude/harness-restore-20260806/_scratch_filter.py`.

Also found: `.gitignore` **contradicts its own comment** — the header says "the probe SCRIPTS are kept
as provenance" while six rules under it exclude exactly those scripts. And `_gen_schema_substrate.py`
was gitignored while FOUR TRACKED TESTS execute it, so those four could never pass on a clone.

## `git archive` EOL conversion is platform-scoped, not universal

`windows-shell.md` §8b says archive returns CRLF. True on Windows, FALSE on Linux. Measured with one
portable probe, both arms live:

    win32  archive 32 B crlf=3  == worktree   conversion_applied=True
    linux  archive 29 B crlf=0  == blob       conversion_applied=False

`git cat-file` applies no conversion on EITHER platform — that is the real reason to use it, not that
it happens to work on this box. I over-generalised the rule and shipped a test asserting the Windows
behaviour unconditionally; **CI caught it, not me**, and it was the same platform-specific-assertion-
without-a-gate defect I had fixed hours earlier in `test_leases.py`. Fix pattern that works: MEASURE
which behaviour applies and branch, never guess from `sys.platform`; ship the inverse assertion so no
platform is left unasserted (a bare skip deletes coverage instead of scoping it).

## A collection floor's slack must be narrower than the smallest package

Independent review found my floor had a bypass **one test wide**: `platform` 3,946 vs floor 3,900 = 46
slack; `platform/corpus` holds 45. `pytest platform --ignore=platform/corpus` -> 3,901 -> PASS. An
ENTIRE PACKAGE could vanish while the gate reported SUCCESS — precisely what the docstring claimed it
caught. **Structural, not off-by-one:** the slack a floor needs to avoid being a nuisance gate is
necessarily wider than the smallest package. Fix: per-package floors in addition to the total, and the
breach must NAME the package.

## Condition 11 structurally caps all 2,007 units (UNDER REFUTATION at time of writing)

`completion_predicate.py:1011-1062` requires every receipt PRIMARY artifact to be in
`ARTIFACT-MANIFEST.json` with a matching sha256. `render.py:34-36` defines that manifest as a
hardcoded 14-name `CONTRACTED_ARTIFACTS` tuple; nothing adds a produced artifact. Measured: 14
entries, zero unit artifacts. All THREE receipts in the repo carry `registered: false`, including one
written by a different lane on a different day. If it holds, no unit can ever reach SUCCESS.
Least-invasive resolution: `manifest_path` is already a free field, so a receipt can name a per-unit
manifest. Write-up: `command-center/STRUCTURAL-CONDITION-11.md`. **Dispatched for adversarial
refutation with instructions to default to REFUTED; retract rather than soften if it falls.**

## `source` is POLYMORPHIC — never gate on a field NAME

A dangling-reference gate over `source` is invalid. Four meanings by JSON location:
`subworkflows[].source` = runtime dependency (must resolve); `lineage.derived_from[].source` =
provenance; `constraints[].source` = free-text citation whose own embedded schema says "The document
or measurement it came from; empty means UNSOURCED" (`spawn brief`, `AGENTS.md 9`);
`lane_comparison_*.source` = a document SET. Going to "fix" two prose values would have corrupted
records conforming to their contract. **Key a gate on the JSON PATH.** That drops 3 of 4 prerequisites
and both data edits.

## Receipt schema enforces honesty and is worth reading

`receipt_core` forbids SUCCESS without `reviewer.independent`+PASS ("self-review is not review"),
`manifest_registration.registered=true`, no `executed:false` consumer, >=2 mechanically independent
evidence probes, >=1 negative control with `fired_on_bad_state:true`, and no test result of
FAIL/ERROR/SKIP/NOT-RUN. `probe` requires `command`, `raw_output`, `fingerprint` — captured output,
not a description. My first attempt was **schema-invalid in 57 places** because I transcribed numbers.
Generate receipts from LIVE probe runs.

## Operational gotchas

- **Pushing again CANCELS your own in-flight run** (`cancel-in-progress`). A `quality` run showed
  `cancelled`, not failed.
- `index.lock` blocked staging 4x. Diagnose with TWO signals (0 bytes + no live git writing this
  worktree) before removing; five stale `git.exe` from 08-09 Aug were the source.
- Bash-tool heredocs break on apostrophes — hit 3x. Use the Write tool for any message/script with
  prose. `rules/common/windows-shell.md` §10 prescribes it after the SECOND failure.
- A pipeline's `$?` is the LAST command's. `SEMGREP_EXIT=0` was `tail`'s status while findings
  existed. Read the finding count, not the exit code.
- Pre-push gate that actually matches CI:
  `~/.claude/harness-restore-20260806/_prepush_gate.py` — ruff at CI's pin + semgrep, over
  `git cat-file` blobs. Built because a push cleared ruff and still went red on `gate-sast`.

## Owner-facing

- **OQ-3 and OQ-4 recorded as ANSWERED** (PR-ONLY; the 38-item tranche was NOT an approved
  substitute). They had real in-session answers and no durable home, so the generated artifact kept
  asserting "27 open of 27" — a false statement in a tracked file. Now 25 of 27.
- Credential id `sha256:839ca3224e60` (transcript) surfaced repeatedly; rotation is the owner's.
- Five `_refute_f*` probes are referenced by tracked audits but hardcode
  `REPO = r"C:\Users\Prekzursil\..."`. Committing them needs a port first — flagged, not done.

Relations: [[reference_session_learnings_2026-07-19b]] (detector failures),
[[reference_fanout_audit_lessons_2026-07-22]] (overclaim class), [[feedback_peer_review]].

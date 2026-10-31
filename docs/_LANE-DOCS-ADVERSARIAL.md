---
title: _LANE-DOCS-ADVERSARIAL
type: note
permalink: dqverify-repo-20261013/docs/lane-docs-adversarial
---

# LANE DOCS — ADVERSARIAL VERIFICATION of BUILD d2a77e15 + its AUDIT

COVERAGE: every row below was EXECUTED. Nothing here is inherited from the build or the audit
except where the row says so explicitly. Two of my own detectors failed and are recorded.

VERDICT: build_is_sound = TRUE · audit_holds = TRUE (PARTIAL is the right verdict) · must_fix = EMPTY

## Re-verified independently (I drove the shipped gate module directly, not the agents' scripts)

| # | claim | my probe | result |
|---|---|---|---|
| 1 | gate 6/6 green | `pytest ci/tests/test_docs_executable_claims.py` ambient py3.14.6 | 6 passed 14.93s |
| 2 | gate green on CI's dependency budget | **bare venv, ONLY pytest 8.4.2** (pip list: colorama/iniconfig/packaging/pluggy/Pygments/pytest) | 6 passed 9.08s, exit 0 |
| 3 | fires in the known-broken state | `readme_violations(git show d2a77e15^:README.md)` — pinned sha, not HEAD | **4** violations: skills 158→337, split 134→337, snapshot-missing, policy 22→24 |
| 4 | green in the fixed state | same fn on `d2a77e15:README.md` and on the worktree | 0 and 0 |
| 5 | in-suite controls are NOT vacuous | monkeypatched `readme_violations` to a **null comparator** (`lambda: []`) and re-ran both control tests | both went **RED** — a readability-only control would have stayed green |
| 6 | AGENTS.md / CLAUDE.md untouched | `git rev-parse d2a77e15^:X d2a77e15:X` | 7bce9460… ×2, 54c3a33a… ×2 → byte-identical |
| 7 | commit surface | `git show --numstat d2a77e15` | exactly 3 files, +459/−8, zero sibling paths |
| 8 | every measured number | gate's own measurement fns, executed now | skills 337, claude-only 35, mcp 24, web 0, lib 6, editor 2, release 8, Codex 40 / Claude 39 / Gemini 33, policy 24, tools 8 |
| 9 | 654-test collection | `pytest ci/tests tools/d001-dual-write/tests --collect-only -q` | 654 collected, exit 0 |
| 10 | **roadmap's THREE NEW claims** (the one place a docs lane could inject its own defect) | line-exact reads | `sync-skills.ps1:45` **is** `$sourceDirs = @((Join-Path $Root "skills"))`; `--strict-parity` is a real argparse flag (`ci/check_skill_dual_write.py:538`); `tools/web/README.md` exists and reads "None. This surface is currently empty" — **all three exact** |
| 11 | both agents' artifacts exist | `ls` + `git ls-files` | `_LANE-DOCS-BUILD.md` 47L, `_LANE-DOCS-VERIFY.md` 145L — exist, untracked. **No PASS rests on a missing input.** |
| 12 | "CR=0 so tree bytes == blob bytes" (build + audit, re: the new .py) | raw `read_bytes()` vs `git show HEAD:` | 17035 == 17035, CR 0/0, byte-identical → **both were right** |
| 13 | no meta-test forces per-file naming in quality.yml | no glob/iterdir/rglob over `ci/tests` in any ci/tests suite; only directory-level markers | audit's "not a defect" CONFIRMED |
| 14 | README's numeric class is fully gated | sweep of every `| N |` / `N+` in README | only ungated numerics are the deliberate soft bounds "370+ / 40+" |

## My own detector failures (2 — both caught by a second probe, neither by inspection)

1. **P4 substring `"pytest ci/tests"` flagged quality.yml as running the suite tree-wide.** It matches
   NAMED-file steps (`pytest ci/tests/test_x.py`). `quality.yml:685` literally says "ci/tests/ has NO
   tree-wide step". Had I trusted it I would have manufactured a false refutation of BOTH agents.
2. **`read_text(encoding="utf-8").count("\r")` reported README CR=0 when the raw file holds 325 CRs**
   (`core.autocrlf=true` here). Universal-newline read — the estate's documented footgun, reproduced
   inside a probe written to hunt for it. Raw `read_bytes()` is the only honest CR measurement.
   Consequence for the gate: `Path.read_text()` normalizes, so the gate always parses LF and the
   CRLF-fragility hypothesis against `_TOOLS_CLAIM` (`\.\n`) is **REFUTED** for the gate as shipped.

## Findings that survive (neither blocks; must_fix stays empty)

**A. NOVEL — the gate's CI reach is narrower than either side stated.** The gate is carried ONLY by
`skill-dual-write.yml`, whose trigger is `pull_request: branches: [main]` with **no `push:`**.
`quality.yml` is the one with `push: branches: [main]`, and it runs `ci/tests` only as named single
files. So the gate never executes on a direct push to main — which is exactly how this program's
commits land, d2a77e15 included. The build disclosed "quality.yml has no tree-wide ci/tests step"
(true) and the audit re-confirmed the step's absence; **neither checked the TRIGGER**, so neither
surfaced that the gate sits outside the blocking `quality` job and outside every push event. The
audit's "reach is test-protected by test_ci_wiring.py:29" is true about the marker string and silent
about event coverage. Also weakening the build's stated reason: quality.yml's own comments at
:780-783, :800-806, :877-882 record four prior lanes making this call the other way and document that
the `gate-tests-coverage` charter slug can be REUSED, so it is a one-line edit with no charter.yml
change — not the "three coordinated edits" the workflow header warns about for a NEW slug.
NOT must_fix: no DoD item concerns the gate; the residual was disclosed honestly; and quality.yml is
the named shared hazard the ground floor tells lanes not to touch. Fix the sentence, not the lane.

**B. CONFIRMED (audit's Finding 2).** `README.md:44` `> **Latest (2026-06-10):**` presents a
two-month-old date as current, self-contradicted by `README.md:38` ("Empty since the 2026-08-09
ChatGPT-web retirement") and by `git log -1 --format=%cs -- README.md` = 2026-08-12. In scope, eight
lines from edits the build made, absent from the 13-row table. Real, minor, not machine-gateable.

**C. CONFIRMED (audit's Defect 1).** `docs/_lane_docs_bothstates_probe.py:36` reads
`git show HEAD:README.md`; HEAD has moved past the fix, so it now prints broken=0/fixed=0 and exits 1.
Untracked scratch, fails CLOSED, and the underlying claim is true — I re-proved 4 violations pinned to
`d2a77e15^`. One-line fix: pin the sha.

## On the audit itself
It controlled its detectors (the disarm test is a genuine two-hypothesis discriminator; I reproduced
it by an independent route), verified against blobs not the worktree, executed rather than read, kept
use-vs-mention straight on the dead-path spot-check, disclosed three of its own detector failures, and
refused to convert the 654-test run into a pass. Its one gap is A above: it verified the STEP that
carries the gate and never the EVENT that fires it.
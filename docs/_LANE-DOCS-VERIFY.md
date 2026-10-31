---
title: _LANE-DOCS-VERIFY
type: note
permalink: dqverify-repo-20261013/docs/lane-docs-verify
---

# LANE DOCS — independent verification of the BUILD round-1 report

STATUS: COMPLETE. Every verdict below came from a command I ran in this session.

COVERAGE — measured: all 3 DoD items, the commit surface, 15 numeric claims, the gate in both
states, control-integrity (disarm), clone-green, ruff, link integrity of README + roadmap.
NOT-CHECKED (same as the builder, honestly inherited): the full 654-test `ci/tests` RUN, the
175 dead-path refs in dated archive dirs, URL rot, and an actual Linux CI run.

VERDICT: **PARTIAL** — all three DoD items PASS when executed; the shipped docs and gate are
sound and in one dimension stronger than reported. Two findings survive: one real (minor)
defect in an evidence artifact, one missed in-scope row of the very defect class this lane
exists to sweep.

## DoD items — all three PASS

| item | verdict | how I executed it |
|---|---|---|
| 1. doc-vs-reality table, measured verdict per row | **PASS** | 13-row table present in `docs/_LANE-DOCS-BUILD.md:14-28`; I re-measured 15 numeric claims and every row's verdict holds |
| 2. each row resolved fix-doc or fix-code with the reason | **PASS** | 1 FIX CODE (row 1, routed + reason), 6 FIX DOC, 6 ACCURATE/no-change. Row 1 re-confirmed by me with a different probe |
| 3. no wholesale rewrite of AGENTS.md or CLAUDE.md | **PASS** | `git rev-parse d2a77e15^:AGENTS.md d2a77e15:AGENTS.md` -> identical blob sha; same for CLAUDE.md. Byte-untouched, not merely "small diff" |

Note on item 2: "no change" is a third outcome the DoD's binary phrasing does not name, but for a
row that measures ACCURATE it is the only correct resolution. Not counted against the item.

## Commit surface — PASS

`git show --numstat d2a77e15` -> README.md 5/5 · ci/tests/test_docs_executable_claims.py 449/0 ·
docs/roadmap.md 5/3. Exactly 3 files, +459/-8 as claimed. `--name-only` contains no AGENTS.md,
no CLAUDE.md, no sibling path — zero foreign paths swept despite a working tree holding ~11
modified and ~40 untracked sibling files. Nothing staged now either.

## Numeric claims — builder correct on 15 of 15

| claim | builder | mine | independent signals | verdict |
|---|---|---|---|---|
| skills/ | 337 | 337 | os.scandir SKILL.md · git ls-files regex · `gen_skills_manifest.py --check` (`skills_tracked=337 manifest_rows=337 added=0`, exit 0) | CONFIRMED ×3 |
| skills-claude-only/ | 35 | 35 | both routes | CONFIRMED |
| "370+" intro bound | 372 | 372 | 337+35 | CONFIRMED (true lower bound) |
| tools/mcp/ | 24 | 24 | on-disk subdirs + git 2nd-segment set | CONFIRMED |
| tools/web/ | 0 | 0 | sole tracked file is its own README | CONFIRMED |
| tools/lib/ | 6 | 6 `.mjs` | git ls-files | CONFIRMED |
| tools/editor/ | 2 | 2 | both routes | CONFIRMED |
| release/platforms/windows/ | 8 | 8 | both routes | CONFIRMED |
| Codex MCPs | 40 | 40 | tomllib len + quoted-key-aware regex distinct-first-segment (57 raw headers) | CONFIRMED ×2 |
| Claude MCPs | 39 | 39 | json len(mcpServers) | CONFIRMED |
| Gemini MCPs | 33 | 33 | json len(mcpServers) | CONFIRMED |
| policy tests | 24 | 24 | `pytest --collect-only -q` EXECUTED | CONFIRMED |
| the broken grep detector | 6 | 6 | `grep -c "def test_"` (parametrized suite) | CONFIRMED |
| scholarly tools | 8 + names | 8, names identical | ast decorators + regex | CONFIRMED |
| live checks | 10 | 10 call sites | line 27 is `def check(`; lines 40-134 are the 10 calls | CONFIRMED |

MY OWN DETECTOR FAILURES this run — 3, each caught by a second probe, none by inspection:
`tools/lib` files-vs-modules (8 vs 6); live-check def-vs-callsite (11 vs 10); and a
`^\[mcp_servers\.` regex returning **0** while tomllib returned 40, because the snapshot uses
QUOTED keys (`[mcp_servers."chrome-devtools".tools.new_page]`). Self-contradicting output =
detector failure; resolved before either number was cited. The lane's warning that "your
DETECTOR is suspect too" was correct three times, and twice it would have manufactured a false
finding against a builder who was right.

## Gate — PASS, and verified stronger than the report claimed

- `pytest ci/tests/test_docs_executable_claims.py -q` -> **6 passed** (working tree).
- **CLONE-GREEN (the builder rated this only "likely 55-80%"):** fresh `git clone` to a temp
  dir, no venv, no installed packages, at a NEWER HEAD (97f5eb06, siblings had advanced past
  d2a77e15) -> **6 passed in 44.99s**. Resolves the clone dimension upward to CONFIRMED. The
  Linux-runner dimension is still unproven, but reach is test-protected: `ci/tests/
  test_ci_wiring.py:29` pins `SELFTEST_MARKER = "python -m pytest ci/tests tools/d001-dual-write/tests"`
  and asserts the collected dir == `ci/tests`, so the mechanism carrying this suite cannot be
  refactored away silently.
- **BOTH-STATES pinned to a FIXED sha** (mine — `d2a77e15^:README.md`, CR=0) -> **4 violations**:
  `skills/` 158 vs 337 · split-shared 134 vs 337 · snapshot-claim missing · policy 22 vs 24.
  Post-fix blob -> 0. Working tree -> 0. Reproduces the claimed broken=4 / fixed=0.
- **CONTROL-INTEGRITY / disarm test (mine, absent from the builder's evidence):** replacing
  `readme_violations` with `lambda: []` makes BOTH in-suite controls go RED. They distinguish
  "stale README" from "correct README", not merely "README is readable". Not inert.
- ruff 0.15.17 `check` -> "All checks passed!", `format --check` -> "1 file already formatted",
  on bytes with CR=0 (tree bytes == blob bytes, so the local green is CI's bytes).
- `pytest ci/tests tools/d001-dual-write/tests --collect-only -q` -> **654 tests**, exit 0.
- 39 workflow-wiring meta-tests (test_ci_wiring, test_workflow_action_contracts,
  test_rules_governance) -> 39 passed. No meta-test requires per-file naming in quality.yml.

## Row 1 (the only FIX-CODE row) — independently CONFIRMED

Re-measured with the CORRECTED reader shape, i.e. the parsed `events[ev]["checks"]` LIST, not
the dict keys that once made four probes report "3 and 3" on both sides:
- `commands/rollback.md:3-4` promises "The `edit-checkpoints` PreToolUse hook snapshots the
  pre-edit state" -> the doc does make the promise.
- repo `hooks/_dispatch/manifest.json` PreToolUse **n=7**, `edit-checkpoints` present at :240.
- live `~/.claude/hooks/_dispatch/manifest.json` PreToolUse **n=5**, `edit-checkpoints` ABSENT.

So doc correct, repo code correct, DEPLOY stale. FIX CODE (deploy) is the right resolution and
weakening the doc would have made the document true and the estate no safer. Out of this lane's
file scope; correctly routed rather than silently taken.

## Dead-path justification — spot-CONFIRMED on the front door

The builder declined a dead-path linter on the measurement "0 genuine broken promises". I
checked the highest-value sample myself: README.md and docs/roadmap.md have **0 broken markdown
links** (including the new roadmap link to `tools/web/README.md`). 5 distinct absent backticked
paths exist in README, and all 5 sit inside explicit retirement sentences —
README.md:127-129 "five were deleted — ..." and :203 "was deleted — ...". Use-vs-mention, not
broken promises. The 29 live-doc refs across docs/** were NOT all re-adjudicated (inherited).

## FINDING 1 — REAL DEFECT (minor): the both-states probe no longer reproduces

`docs/_lane_docs_bothstates_probe.py:36` reads `git show HEAD:README.md`. HEAD has advanced past
the fix, so the "broken" side is now the FIXED blob. Re-running the quoted command prints
`broken=0 fixed=0` / `FAILED:docs-bothstates`, exit **1**.

- Fail-CLOSED, not fail-open — it cannot certify a false green. That materially limits severity.
- The underlying CLAIM is TRUE: I reproduced 4 violations against `d2a77e15^:README.md`.
- The artifact is untracked scratch, so nothing ships broken.
- Fix: pin the probe to `d2a77e15^:README.md` (one-line change), and state the sha in the
  artifact instead of `HEAD`.

## FINDING 2 — MISSED ROW (in scope, in the lane's own sweep list): stale date as current

`README.md:44` reads `> **Latest (2026-06-10):** added 4 game-RE skills; ...`. That date is
presented as the current state of the repo and is contradicted twice over:
- by README.md:36 in the SAME file — "Empty since the **2026-08-09** ChatGPT-web retirement";
- by `git log -1 --format=%cs -- README.md` -> **2026-08-12** (the builder's own commit), against
  a newest repo commit of 2026-08-13.

The lane's sweep list names "stale counts and dates presented as current" explicitly, this is
inside the builder's declared file scope, and it is in a file the builder edited in this very
commit while fixing five other stale numbers in it. The 13-row table has no row for it.
Not a DoD failure — the DoD does not demand exhaustiveness — but a genuine miss of the target
class. Resolution: FIX DOC (re-date the banner, or drop the word "Latest" so it reads as a
dated changelog entry rather than a currency claim). Not machine-gateable the way the counts
are, which is plausibly why it survived a numbers-focused pass.

## Overclaim (mild, 1)

`docs/_LANE-DOCS-BUILD.md:33-34` and the report's evidence section present the both-states
control as `git show HEAD:README.md ... -> 4 violations`, i.e. as a re-runnable receipt. As
written it no longer reproduces. Correctly-scoped version: *"against `d2a77e15^:README.md` (the
pre-fix blob, CR=0) -> 4 violations, and 0 against the fixed blob; the HEAD-relative form goes
stale the moment HEAD advances."* The builder was half-aware — its report says "HEAD has since
moved ... cite my work by sha d2a77e15, not by HEAD" — but did not carry that into the probe or
the artifact's quoted command.

Everything else in the report is scoped at or below its evidence. Notably the builder
volunteered its own two detector failures (tools/mcp 26->24, list_tools.py rejected as oracle),
and both were real and correctly resolved.
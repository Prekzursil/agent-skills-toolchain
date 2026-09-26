---
title: Register closes + two new gates, 2026-08-11 overnight session
type: note
permalink: main/projects/prompt-two/register-closes-two-new-gates-2026-08-11-overnight-session
tags:
- prompt-two
- register
- command-center
- gates
- ast-integrate
- compaction-checkpoint
- bucket-semantics
- REL-0003
- namespace-miss
- unified two-program continuation
---

# Register closes + two new gates — overnight 2026-08-11

`valid_as_of: 2026-08-11`. Repo `~/source/ast-integrate` (worktree of `agent-skills-toolchain`),
HEAD `d53485ce`, pushed, **all CI green** (quality · no-runtime-junk · routing-benchmark).
14 commits from base `ef6e2c4b`.

## Headline

**Register 26 → 36 DONE-VERIFIED.** 51 items literally `OPEN` (the validator's "59 open" counts
OPEN + IN-FLIGHT + DONE-CLAIMED + UNKNOWN — those are different numbers and got conflated once).

**Five of the ten closes closed because the deliverable had shipped under `platform/` while the
register's anchor still named a pre-`platform/` path.** Nothing was built to close them. R-A10's
anchor `11-COUNCIL-SPECIFICATION.schema.json` is tracked **zero** times; the successor is
`platform/schema/councilspec.schema.json`. Two more (R-M01, R-B06) closed on refuted premises.

Closed: `R-A06 R-A09 R-A10 R-A12 R-A20 R-A23 R-A24 R-B05 R-B06 R-M01`.
Held deliberately (self-scored `likely 55-80%`, or turn on a reading): `R-A04 R-A08 R-A14 R-A15
R-A25 R-A26 R-A27 R-B04`.

## The verifier earned itself — 4 of the first 7 closes were BLOCKED

`command-center/close_verify.py` re-measures every anchor with a probe mechanically different from
the one that produced the proposal. On the first pass it blocked 4 of 7: three were faults in my own
probe (wrong JSON path, wrong skill name, grepping a CLI instead of asking it) and one was a real
over-claim in a peer lane's message. **Trusting the lane digests would have written four wrong
dispositions.** A digest is a claim, not a receipt.

## Two gates built, both over surfaces nothing validated

- **`tools/measure-guard/wudeps.py`** — `tools/command-center/validate.py` does not contain the
  string `work_units`. It gated the 103 register items and **none of the 2,007 work units**.
  Measured: **41 refs resolve to nothing, 876 point at buckets with zero members** (B07 alone
  carries 297). Ratchets against a baseline rather than failing 917 pre-existing findings.
- **`tools/measure-guard/jsonparse.py`** — 3 of 1,069 tracked JSON files did not parse, including
  **R-A06's own evidence anchor**. The load-bearing part is the EXCLUSION: two `accounts.json` are
  git-crypt ciphertext, and "repairing" one would have destroyed encrypted credential material.

## `bucket` is UNDEFINED — an owner decision blocking 876 edges

Appears nowhere in the catalog's `contract`/`defaults`/`tool_policy`, and twice in the 29,273-line
spec, neither time as a definition (control: `phase` appears 172×). Lane C1's "repair or retarget
the six dangling bucket tokens" is **not actionable** — nobody knows what they should point at.
Three readings possible; under "all members done", 876 edges are permanently unsatisfiable.

## LIVE DEFECT, not deployed by me

`~/.claude/hooks/cmd-rewrite/inject-nopager.py` (PreToolUse, live settings.json) is **stale**:
`updatedInput = {"command": rewritten}` instead of `{**tool_input, "command": rewritten}`.
`updatedInput` REPLACES the object, so it silently drops `description`, `timeout` and
`run_in_background` from every Bash call it rewrites. Fix is committed and tested in-repo
(9 dedicated tests). Five signals: hash mismatch, the 8-line diff, the repo comment documenting the
symptom, the test suite, and the harness's own `install.py --check` reporting `drift` on
`hooks.claude`. **Deploy is the owner's.**

## Three owner decisions gating everything → `command-center/OWNER-PACKET-2026-08-11.md`

1. **OQ-1 + OQ-2** → unblocks `R-A03` + 8 dependents (`07-OPTION-UNIVERSE.json` has a ready default).
2. **`REL-0003`** → the ONLY startable unit of 43 in Phase 15/16, and it has **no row in
   `OWNER-DECISIONS.md` at all**.
3. **`B\d+` semantics** → above.

Only **7 of 25** open owner questions gate a register item; 18 gate nothing.

## Corrections to my own claims (all made and retracted in-session)

- Claimed 2 of 10 lanes "died producing nothing" — **wrong**, I read mid-flight snapshots at 21:50
  while lanes wrote until 23:11. All 11 completed. Lane A2 made the identical error, so the
  write-as-you-go skeleton sentinel is a systemic snapshot trap, not a one-off.
- Committed "the flake is order-dependent under pytest-randomly" — **the plugin is not installed**;
  my four seeded runs died at `ImportError` and printed nothing, and I read that silence as four
  clean runs. Retracted in `1bdb1189`.
- Claimed a 10× CI slowdown (606s) — contention; re-profiled at 213s, ~10s of it mine.
- Speculated the `platform/` namespace miss would generalise to the remaining open items —
  **measured and refuted**: 0 of 51. But a basename sweep is blind to the *renamed-deliverable*
  case, which is exactly how R-A06/R-A09/R-A12 shipped, so the 51 remain unverified in that
  direction. **Plan against 51 open, not against a discount.**

## Traps that bit again despite being written down

`grep -c pat || echo 0` → doubled zero (grep -c prints 0 AND exits 1) · bash heredoc strips
backslashes from a `[/\\]` char class, twice, until transport switched to the Write tool ·
`git show :path` returns CRLF like `git archive` (only `ls-files -s` + `cat-file -p` gives stored
bytes) · running a standalone script under pytest ("fixture not found" is the wrong invocation, not
a defect — CI runs `python test_msys_pathconv.py` → 174 passed).

## Recall aliases

Findable as: register closes · command-center gates · wudeps · jsonparse · bucket semantics ·
REL-0003 · platform namespace miss · unified two-program continuation · Prompt Two · two-program.

Related:
[[main/projects/prompt-two-waves-4-5-platform-ci-lane-2026-08-10]] ·
[[main/projects/prompt-two/prompt-two-program-state-waves-0-1-2-shipped-wave-3-running-2026-08-10]]

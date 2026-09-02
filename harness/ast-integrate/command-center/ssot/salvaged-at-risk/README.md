# Salvage — the 5 files that were reachable from NO git ref

Taken 2026-08-13 by the SSOT lane. Produced by `command-center/ssot/salvage_atrisk.py --salvage`,
measured by `command-center/ssot/reachability_probe.py`, receipts in `../salvage-atrisk.json`
and `../reachability.json`.

## Why these five

`docs/ssot/SSOT-CLONE-INVENTORY.md` §4 named two checkouts holding content that exists nowhere
else. Both were still in that state when this ran. The test applied is **reachability**, not
existence: membership in `git rev-list --objects --all`, which is exactly the set `git gc`
preserves.

| source | kind | files | why it was at risk |
|---|---|---|---|
| `D:/wt-salvage-probe` | staged index, never committed | 2 | a worktree's **index** is per-worktree and `git worktree remove` destroys it |
| `~/.claude/agent-worktrees-salvage/agent-1521081161/_b5-toolchain` | 1 unpushed commit (`80130e1`) on `harness/b5-dead-mcp-detector` | 3 | independent clone; the commit is in **no** remote-tracking ref and canonical has never heard of it |

    ci/tests/test_codex_profiles.py                 17,779 B
    tools/monitorcore/r0_monitor_live_gate.py        6,566 B
    tools/mcp-manager/core/health.py                25,391 B
    tools/mcp-manager/mcp_health.py                  5,245 B
    tools/mcp-manager/tests/test_health.py          27,594 B
                                                    -------
                                                    82,575 B

## The distinction that makes this directory necessary

`D:/wt-salvage-probe` is a **linked worktree of the canonical store**, so `git add` wrote its
blobs into the *shared* object database. Measured:

    ci/tests/test_codex_profiles.py     exists_in_store=True   reachable_from_any_ref=False

An existence probe (`git cat-file -e`) calls that file **present in canonical** and moves on.
It is present and simultaneously one `git gc --prune` from deletion, because nothing points at
it but an index that a single command destroys. Existence and reachability are different
questions, and an existence probe answers them identically — so it cannot distinguish

    H1: preserved in history, recoverable
    H2: loose object hanging off an index, one gc from gone

**This lane made that exact error first.** The first version of `salvage_atrisk.py` used
`cat-file -e`, reported every at-risk file as present, and concluded `unique=0` — a clean bill
of health for the content the inventory had ranked highest-urgency. A second bug in the same
run reported `_b5-toolchain` as having **0 unpushed files**: `git log --format=%H --not
--remotes` does not default to `HEAD` once `--not` is present, it returns empty. Both failures
pointed the same way — toward *"nothing here is at risk"* — which is the direction that gets
data deleted. Both are recorded in the script's docstring rather than edited away.

## What this directory is NOT

**Preserving bytes is not endorsing code, and it is not a restore.** These files are parked
under their original relative paths *inside this directory* so the provenance is legible. They
are deliberately NOT placed at those paths in the repo:

- `tools/mcp-manager/**` — the b5 commit is a **superseded parallel implementation**. Main ships
  a dead-MCP detector via `core/claude_adapter.py` + `core/models.py` (PR #196); b5 ships
  `health.py` + `mcp_health.py`. The inventory records the trap here: both sides have **42 files**
  in `tools/mcp-manager/`, which reads as parity and is actually a 3-for-3 swap. Whether b5's
  graded-evidence logic is worth porting is a judgement call that has not been made. Salvaging
  the bytes makes that decision *possible later*; it does not make it.
- `ci/tests/`, `tools/monitorcore/` — never committed anywhere, so nothing establishes that they
  were finished, passing, or wanted.

**UNVERIFIED [inline]:** none of the five was executed, imported, or tested by this lane. Their
value here is byte-identity with the source blob, nothing more. Settling experiment for the
mcp-manager question: diff b5's grading logic against main's `claude_adapter.py` detector and
run b5's `test_health.py` against main's implementation.

## Integrity

Each file's git blob SHA was recorded at read time and recomputed from the written copy;
`salvage-atrisk.json` carries `sha`, `roundtrip_sha` and `roundtrip_ok` per file. **5 of 5
byte-identical**, re-verified after `ruff format` ran over the directory's siblings.

These are frozen evidence: `ruff.toml` excludes this tree
(`command-center/ssot/salvaged-at-risk/**`) because `ruff format` would rewrite 2 of the 5 and
destroy the one property that makes them worth keeping. Measured both states — with the
exclusion the format gate is green; without it, 2 files would be reformatted.

## The sources were not touched

Read-only throughout: blobs were read with `git cat-file blob`, never checked out, and nothing
was written into either source. Verified after the copy — `D:/wt-salvage-probe` still stages the
same 2 paths, `_b5-toolchain` still has `80130e1` and a clean working tree.

**Nothing was deleted and no checkout was retired.** The inventory's precondition still stands:
retire nothing until its work is on a pushed branch. This directory removes the *data-loss*
exposure (the bytes are now in tracked history); it does not by itself license retiring either
checkout, because a copy parked in an evidence directory is not the same as the work being
landed where it belongs.

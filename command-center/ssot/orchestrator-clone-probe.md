# Clone existence + write-activity probe — orchestrator hand-off to the SSOT lane

Measured 2026-08-12 by the orchestrator. This is ONE narrow data point, not the lane's job.
It answers "do the nine exist, and is this session writing to them", nothing more.

## All nine clone roots EXIST on disk

Probed with `[ -d "$d" ]`; every one returned present (no MISSING rows):

    ~/.claude/codexsrc-work
    ~/.claude/toolchain-audit
    ~/.claude/tw-merge-work
    ~/Documents/Playground
    ~/source/agent-skills-toolchain
    ~/source/ast-patch167
    ~/source/ast-integrate          <- the active worktree, HEAD == origin/main
    ~/work/agent-skills-toolchain-re
    /d/sast-depth/agent-skills-toolchain

So the owner's count of nine is CONFIRMED as nine live directories (almost certain, 90-99% --
direct filesystem test).

## This session's scratch is CONFINED to ast-integrate

Searched all nine for five session-scratch filenames -> 0 hits in all nine, including
ast-integrate (the files are gone; see the hook-audit note). Then the CONTROL: the same search
for a file known present, `platform/architecture/_measure_cf.py`, returned `ast-integrate=1` and
0 in the other roots probed.

**Reading:** the finder works, and no session scratch has leaked into the other eight clones.
Whatever the SSOT problem is, "agents are concurrently scribbling into all nine" is NOT it --
at least not this session (likely 55-80%; I probed five filenames, not the full write surface).

## What this deliberately does NOT answer -- still the lane's work

- WORKTREE vs independent CLONE per root (shared object store or not). This is the question that
  decides whether a root can hold unique HISTORY at all, and it is unanswered here.
- Unique commits / uncommitted work per root.
- Inbound references (scheduled tasks, hooks, skills, PATH, configs) pointing at each root.
- The one-sentence SSOT rule.

## Hazard to carry into any retirement recommendation

`git worktree remove` FOLLOWS junctions and destroys their targets (measured 2026-08-10: it
emptied a canonical checkout's node_modules and build dirs in one command). A root that LOOKS
disposable can be a junction into one that is not. Recommend only; delete nothing.

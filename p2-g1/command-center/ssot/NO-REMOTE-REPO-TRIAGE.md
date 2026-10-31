# Triage: the two NO-REMOTE repos (`chk`, `scratch`) — the decision is now cheap

Standing owner decision was **"Triage first, then decide"** for repos with no remote, with an
explicit *do not create remotes, do not push*. A prior attempt at this triage died with a
TypeError and never produced a result, so it was still open. Completed 2026-08-13, read-only:
nothing created, nothing pushed, nothing deleted.

## What they are

Both live under `~/source/_advver_M14/` and both are working copies of **agent-skills-toolchain
itself** (README title and `package.json` name both confirm it).

| | `chk` | `scratch` |
|---|---|---|
| path | `~/source/_advver_M14/chk` | `~/source/_advver_M14/scratch` |
| git | 1 commit, 2026-08-08, *"preserve this working copy in local git"* | **0 commits** — `git init` only |
| remote | none | none |
| tracked | 7,763 files | **0** (all 40 top-level entries untracked) |
| on disk | 122 MB | 99 MB |

`scratch` is the worse shape on paper: nothing is in git at all, anywhere.

**Neither appears in `docs/ssot/SSOT-CLONE-INVENTORY.md`.** The SSOT lane measured 25 checkouts
across 18 object stores; these two are not among them, so the real count is at least 27. Worth a
follow-up on how the inventory enumerated checkouts, since it missed a whole directory.

## Exact uniqueness test (not a sample, not a judgement call)

For every file, hash it and ask whether that blob exists anywhere in the canonical object store
(`git cat-file --batch-check`, which searches all of history, not just HEAD):

    chk      7,763 blobs -> 7,756 present,  7 MISSING
    scratch  7,802 files -> 7,765 present, 37 MISSING

Detector control: the 7756/7 and 7765/37 splits are self-validating. A broken reader returns
all-present or all-missing; a discriminating split proves it is reading both outcomes.

`scratch`'s 37 decompose as **30 regenerable build artifacts** (`.pytest_cache/`,
`__pycache__/*.pyc`) plus **the same 7 files `chk` has**. So the entire unique payload across both
repos is SEVEN files, roughly 96 KB, duplicated in both:

    tools/mcp/codex-orchestrator/src/codex-orchestration.mjs          24,194 B
    tools/mcp/codex-orchestrator/integrations/codex/probe.mjs         46,838 B
    tools/mcp/codex-orchestrator/src/orchestrator/codex.mjs            5,122 B
    tools/mcp/codex-orchestrator/tests/codex-orchestration.test.mjs    4,264 B
    tools/mcp/codex-orchestrator/tests/codex-probe.test.mjs           14,403 B
    tools/mcp/agent-lanes-codex/local-overrides/codex-orchestration.mjs  195 B
    tools/web/README.md                                                1,066 B  (path exists, content differs)

## The finding that reverses the obvious conclusion

"Unique content" reads as "data-loss risk", and six of these seven look like a whole orchestrator
subsystem with its own test suite. It is not lost work. `git log --all` over that path returns 10
commits, two of which are:

    45882cd1  retire: delete the 5 ChatGPT-web/orchestrator trees and de-register them
    696ed513  chore: retire the ChatGPT-web orchestration lane (5 trees, 77 files) ... (#275)

That is the owner's own DELETE-ALL retirement of the ChatGPT-web orchestration lane. These files
are **remnants of code that was deliberately removed**, surviving in two working copies snapshotted
around the 2026-08-08 retirement (which is exactly `chk`'s commit date). Carrying them back into
the repo would partially undo an explicit decision.

Control for that claim: the same `log --all -- <path>` returns 49 commits for
`tools/mcp/cloud-hub/**`, so the query does find live paths — the 10 commits ending in a retirement
are a real history, not an artifact of a broken filter.

## CORRECTION 2026-08-13, ~20 minutes after this file was committed — DO NOT RETIRE `scratch` YET

The retire-safe verdict below is **WITHDRAWN for `scratch`**. It was measured correctly and
published wrongly: the directory was under ACTIVE WRITE by the running lanes, so the census
expired almost immediately.

Re-measured: **21 files modified in `scratch` in the preceding 12 hours, and ALL 21 have content
present nowhere in the canonical object store.** Five are lane verification deliverables —
`VERIFY-MCPRESEARCH-r3.md`, `_ADVVER_DOCS_R3.md`, `_VERIFY-docs-r3.md`, `P2NEXT-ADVVERIFY.md`,
`_S2_AUDIT_NOTES.md` — plus the probes they ran. Deleting on the strength of the verdict below
would have destroyed running verification work.

Those 21 files are snapshotted into `command-center/ssot/salvaged-from-scratch/` (84,885 B, `cp -p`,
source untouched). They are copies of LIVE files and may be partial; that directory's README says
so and says not to cite them as final verdicts.

**The error was procedural, not arithmetic.** A uniqueness census is a snapshot; a snapshot of a
moving target cannot license a deletion. The missing step was one cheap command —
`find <dir> -newermt '10 minutes ago'` — because "what is in here" and "is anything still filling
it" are different questions and only the second licenses a retire verdict. The original wording is
kept below rather than edited away, so the mistake stays legible.

`chk` is unaffected: 1 commit, 0 uncommitted, nothing written to it during the wave. Its verdict
stands.

## Recommendation (ORIGINAL WORDING — superseded for `scratch` by the correction above)

**Both are safe to retire; ~221 MB reclaimed.** Their only unique content is deliberately-deleted
code, duplicated across both, and everything else is either in canonical or regenerable. Not
executed here: deleting 221 MB is destructive and the standing instruction reserves the decision.

If you want belt-and-braces before deleting, the cheapest preservation is a single
`git bundle`/zip of just those 7 paths (96 KB) parked outside the repo — it keeps the retirement
intact while making the delete unarguable.

## Adjacent thing worth a look, NOT verified as a defect

Five files in the live repo still contain the string `codex-orchestrator`, including
`.agents/skills/codex-consult/SKILL.md` and `.agents/skills/codex-orchestrate/SKILL.md`. I did NOT
check whether these are real path references to the retired tree or incidental mentions of the
concept — that distinction is the use-vs-mention trap and it needs the field read, not a grep
count. Handing it to the DOCS lane as a candidate, not a finding.

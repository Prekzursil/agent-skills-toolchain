---
title: WAVE3-AUDIT-CORRECTION
type: note
permalink: dqverify-repo-20261013/command-center/wave3-audit-correction
---

# Wave 3 floor audit — correction to commit 4444005d and 200942b9

Both commit messages describe this audit as **partial**. That is **false** for the artifact as it
now stands, and the error is mine: the audit was mid-write and I described an in-progress
write-as-you-go file as if it were final.

## What the completed audit actually says

| section | verdict |
|---|---|
| D1 cross-vendor · D2 work-unit authz · D3 test-mutates-tree · D4 duplicate ids · D5 vendor-role | **all CLOSED** |
| check2 Phase 5 plugin | **PASS** — deterministic rebuild; every hygiene detector fired on a seeded input (archive, cache, credential-by-content, credential-by-name, log, test module, transcript, venv) |
| check3 Phase 6 marketplace | **PASS** — fixture publish, install, install-after-revoke, other-version-after-revoke |
| check6 regression | **NONE** |

D3 carries a proper both-states control: a planted edit **SURVIVED** the suite in the fixed state,
and the broken-state control confirms the same edit was **REVERTED** before the fix. The test no
longer silently repairs the tree it measures.

## Two things the PASS verdicts do not cover

**Marketplace authority is checked at install, not at revoke.** The non-maintainer authority probe
found that `revoke` exits 0 and writes a signed revocation list which the installer only later
rejects as *"key is not a maintainer"*. A non-maintainer can therefore publish a revocation that
appears accepted. Separately, `mkt mutations` exits 1 with a traceback. Neither is fixed here.

## The regression section is the most valuable part, because it refuses to give a number

> "~20 agents share this tree; HEAD moved `0aa6f8fa -> 72c3f1a7 -> a46ec548 -> 29f4c72a` during the
> audit, and the passed count grew 3830 -> 3922. Every count is a snapshot, not an invariant."

Four measurements disagreed across this program — 2,767 (mine, taken while I was editing the tree),
2,812 (a lane's, corroborated independently), 3,067 (D1's, after adding 176 tests), and
3,830 -> 3,922 (the audit's own two runs). The audit does not pick one. It marks the gap
**UNVERIFIED** and names the only thing that would settle it: a pristine, quiet checkout.

That is the correct answer. A suite count taken while twenty agents write is not a baseline, and
treating one as an invariant is how a 45-test regression would have slipped under a stale floor.
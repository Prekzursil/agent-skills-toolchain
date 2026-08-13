# Salvaged snapshot — 21 files that existed ONLY in a no-remote, zero-commit directory

Taken 2026-08-13 08:1x by the orchestrator from `~/source/_advver_M14/scratch`, mid-wave, while
the lanes that wrote them were still running.

## Why this exists

`~/source/_advver_M14/scratch` is a working copy of this repo with **zero commits** (`git init`
and nothing else) and **no remote**. Nine concurrent lanes were writing artifacts into it. Every
one of the 21 files modified there in the preceding 12 hours had content present **nowhere** in
the canonical object store:

    files modified in last 12h (excl. .git/.ruff_cache/__pycache__/node_modules) : 21
    of those, blobs present in canonical                                        : 0
    MISSING (unique to that directory)                                          : 21

Five are lane verification deliverables, not scratch:

    VERIFY-MCPRESEARCH-r3.md   MCPRESEARCH round-3 verify
    _ADVVER_DOCS_R3.md         DOCS round-3 adversarial verify
    _VERIFY-docs-r3.md         DOCS verify
    P2NEXT-ADVVERIFY.md        P2NEXT adversarial verify
    _S2_AUDIT_NOTES.md         SKILLS2 audit notes

The rest are the probes those verifications ran (`aud_crlf*.py`, `v1..v4_*.py`,
`verify_divergence.py`, `verify_deadpaths.py`, …) plus one measurement output
(`v1_rows_HEAD.json`). 84,885 bytes total.

## Status of these copies — read before citing them

**These are SNAPSHOTS OF LIVE FILES, taken while their authors were still writing.** Some may be
partial. Do NOT cite a number from here as a lane's final verdict; the lane's own committed
artifact is authoritative if one exists. The reason to keep an imperfect copy is that the
alternative was a total loss if the directory were cleaned — and it very nearly was (see below).

Preserved with `cp -p`, so mtimes are the originals. Nothing in the source directory was modified,
moved or deleted.

## The near-miss this corrects

`command-center/ssot/NO-REMOTE-REPO-TRIAGE.md` (committed `c2c293a5`, ~20 minutes before this
snapshot) concluded that `chk` and `scratch` were **"safe to retire; ~221 MB reclaimed"**. That
was true of the state measured: `scratch`'s only unique content was 7 deliberately-retired files
plus 30 regenerable caches. It stopped being true almost immediately, because the lanes kept
writing. Acting on that recommendation would have destroyed running verification work.

The triage was not wrong about the files it measured; it was **wrong to publish a retire-safe
verdict on a directory under active write**. A uniqueness census is a snapshot, and a snapshot of
a moving target expires. The correction is recorded in that file rather than by editing the
verdict away.

**Generalisation worth keeping:** before recommending deletion of anything, check whether it is
being WRITTEN TO, not just what it currently contains. `find <dir> -newermt '10 minutes ago'` is
the whole check, and it is cheap. "What is in here" and "is anything still filling it" are
different questions, and only the second one licenses a retire verdict.

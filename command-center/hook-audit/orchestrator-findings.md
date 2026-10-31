---
title: orchestrator-findings
type: note
permalink: dqverify-repo-20261013/command-center/hook-audit/orchestrator-findings
---

# Hook false-positive census — orchestrator hand-off to the HOOKRESEARCH lane

Measured 2026-08-12 by the orchestrator from a live Stop-hook firing, not from record.
Two of the three notices in that firing were instrumentation defects. Both are the
"fires so noisily the reader learns to ignore it" class named in the lane brief.

## 1. `stub-ledger` over-reports: it never re-checks that the file survived

The firing claimed **31 placeholder/TODO(s) you introduced this session are STILL open**
and named five files. NONE of the five exists in ANY of the nine agent-skills-toolchain
clones on this box:

    measure_cc.py  detector_control.py  schema_audit.py
    _topfiles_codex_refs.py  _focus_codex_refs.py

Search: `find <clone> -name <n> -not -path '*/.git/*'` across all nine clone roots -> 0 hits each.

**Detector control (mandatory, rule 3).** The same `find`, same flags, for a file known to be
present (`platform/architecture/_measure_cf.py`): `ast-integrate=1`, `toolchain-audit=0`,
`/d/sast-depth=0`. The finder DOES fire on a present file, so the zeros are a real absence and
not a broken matcher.

**Mechanism (hypothesis, likely 55-80%):** the ledger records a placeholder string at WRITE time
and never re-validates at REPORT time. Agent scratch is routinely written, run, and removed
inside one session, so every such file becomes a permanent phantom entry. UNVERIFIED: I did not
read the ledger's storage or report path to confirm the write-time/report-time split -- the
settling experiment is to write a file containing `# PLACEHOLDER`, delete it, and check whether
the next Stop firing still cites it.

**Why it matters:** a count of 31 that cannot be acted on trains the reader to skip the whole
notice, including the entries that ARE real. Fix is a `Path.exists()` filter at report time, plus
reporting phantom entries separately from live ones rather than summing them.

## 2. `wire-check` false-positives on single-file scripts

The firing named `count()`, `loc()`, `logical()`, `rel()`, `classify()` as "referenced 0x", and
`platform/architecture` as a route "linked/navigated 0x".

All four host files are UNTRACKED one-shot measurement scripts under `platform/architecture/`.
`count()` is defined at `_measure_cf.py:21` and CALLED at `:50` and `:154` -- same file, module
level. The check is looking for a cross-file import, a route registration, or a handler; a
self-contained script has none of those by construction, so the class can never pass.
`platform/architecture` is a path string inside `_judge_refutation.py`, not a route.

**Fix options, cheapest first:** skip untracked files; or skip files with no `import` of their own
module anywhere in-tree; or count same-file call sites before declaring 0 references.

**Do NOT "fix" this by wiring the functions in.** They are throwaway measurement scripts and
wiring them would create the dead code the check is trying to prevent.

## 3. `git-hygiene` fired on 3 repos and ALL THREE are benign -- two permanently so

Measured 2026-08-13 from a later firing in the same session. The notice read:

    [YOURS] agent-skills-toolchain: 2 uncommitted file(s) at a detached HEAD, no upstream
    [YOURS] ast-patch167: 1 uncommitted file(s) on fix/deny-credential-gaps
    [YOURS] ast-integrate: 248 uncommitted file(s) on main

Checked each:

**a. canonical `agent-skills-toolchain` -- PERMANENT false positive, unfixable by design.**
The 2 files are `tools/mcp/cloud-hub/accounts.json` and `tools/mcp/search-hub/accounts.json`.
That is the LIVE credential rotation pool; a standing owner constraint forbids staging or
modifying it, so **uncommitted is the CORRECT state** and always will be. `rev-list --count
origin/main..HEAD` = 0, so there is no unique history at risk either. This repo will be flagged
on every single turn forever, and the advised remedy ("commit, then push -u") is an action that
must never be taken. A hook whose advice is forbidden is worse than a silent one.
FIX: exclude paths matching `accounts.json` (or better, anything the repo's own ignore/secret
policy marks as live state) from the uncommitted count, and suppress a repo whose ONLY dirty
paths are excluded.

**b. `ast-patch167` -- squash-merge artifact.** The "1 unique commit" `69ec33a` is
`fix(deny-credential-reads): guard all four ssh key types + auth.json`, and it is **already
MERGED as PR #260**. A squash merge rewrites the commit, so the branch keeps reporting 1 ahead
of `origin/main` forever. This is the documented `ahead_by`-direction trap and the hook walks
straight into it. FIX: before counting a branch as ahead, check whether an associated PR is
merged, or compare content (patch-id / cherry) rather than commit identity. `git cherry
origin/main HEAD` marks equivalent commits with `-` and is the cheap version.

**c. `ast-integrate` 248 files -- REAL but expected**, and the only one of the three worth a
human glance. It is nine concurrent lanes' write-as-you-go scratch mid-wave. The SLOP lane owns
classifying it. Not a hook defect; the count is true.

**The compound effect is the finding.** Three flags, zero actionable, one of them advising a
forbidden action. That is the same pathology as the stub-ledger above: a guard that cannot reach
green trains the reader to skip it, and the cost lands on the day one of the three IS real. Both
of these are cheap to fix and both fixes are subtractive (fewer, truer flags), not additive.

## 4. What this does NOT excuse

The third notice in the same firing -- `POTENTIAL-CREDENTIAL kind=transcript
id=sha256:839ca3224e60` -- is NOT a false positive and is NOT cleared. It is a standing owner
notice; per AGENTS.md 9 no agent action clears it and no agent may rotate the credential.
Classification remains UNKNOWN (scan incomplete), which is not the same as clean.

## 5. The wire-check fix is COMMITTED BUT NOT DEPLOYED -- measured, and it explains the repeat

Commit `95761504 fix(wire-check): stop the cp1252 silent-empty that made every finding a false
positive` landed in the repo. The hook kept firing the same false positives on the very next turn.

Measured, not inferred:

    hooks/wire-check/check.py     repo@95761504 sha256 5682886ea301
                                  live ~/.claude/hooks/wire-check/check.py  70b68818763e   DIFFER
    hooks/wire-check/test_wire_check_decode.py   live: DOES NOT EXIST
    hooks/wire-check/test_wire_check_noise.py    live: DOES NOT EXIST

So the running hook is the UNPATCHED copy. The cp1252 silent-empty is still live, which is why
`main()` / `report()` / `toks()` in one-shot `_audit_s2_*.py` scripts are still reported as
referenced 0x. The repo being green here proves nothing about the guard the session actually runs.

**This is the repo-is-source-of-truth / live-is-deploy-target gap, caught in the act.** It is the
same shape as the two consumer-with-no-producer defects: a fix exists and nothing carries it to
where it executes. Note the asymmetry that makes it easy to miss -- a repo-side test suite for this
hook would go GREEN while every live firing stays wrong.

NOT deployed by the orchestrator, deliberately: nine lanes were mid-flight, hand-copying a
deployed hook is the exact anti-pattern the harness-vcs-hygiene rule names, and the sanctioned
repo->live path should be used rather than guessed. Handing it to the HOOKRESEARCH lane with the
verification recipe: after deploying, re-hash both sides to confirm they match, then feed the hook
a single-file script whose function is called only at module level and require it to stay SILENT --
and feed it a genuinely unreferenced function and require it to FIRE. Silence alone is not proof
the fix landed; the guard was already silent on the things it should catch.
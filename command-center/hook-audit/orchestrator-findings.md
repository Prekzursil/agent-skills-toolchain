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

## 3. What this does NOT excuse

The third notice in the same firing -- `POTENTIAL-CREDENTIAL kind=transcript
id=sha256:839ca3224e60` -- is NOT a false positive and is NOT cleared. It is a standing owner
notice; per AGENTS.md 9 no agent action clears it and no agent may rotate the credential.
Classification remains UNKNOWN (scan incomplete), which is not the same as clean.

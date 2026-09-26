---
title: QZP gate-deps outage-vs-vuln fix + v1 rollout gate (2026-07-25)
type: note
permalink: main/reference/github/qzp-gate-deps-outage-vs-vuln-fix-v1-rollout-gate-2026-07-25
valid_as_of: '2026-07-25'
supersedes: main/claude-memory/documents-git-hub-event-link/project-qzp-preexisting-gates
tags:
- quality-zero-platform
- ci
- osv-scanner
- rollout
- correction
---

# QZP `gate-deps` outage-vs-vuln fix + the v1 rollout gate

**valid_as_of: 2026-07-25.** PR **#279** open (NOT merged — shared infra, owner reviews): https://github.com/Prekzursil/quality-zero-platform/pull/279

## CORRECTION — supersedes the "4-5 permanently red checks" note
The older note `project_qzp_preexisting_gates` claimed *"quality-zero-platform's CI … is missing several secrets/configs, so 4-5 checks are permanently red on every PR regardless of content."* **That did NOT reproduce today.** Control = merged PR #276: **9/9 green**. PR #279: **9/9 green, zero red** (verified by me: `state=OPEN mergeable=MERGEABLE mergeStateStatus=CLEAN`, 0 non-pass checks). Treat the old note as **stale**.

## The defect fixed
`reusable-quality.yml:666-675` had ONE branch for every non-zero exit: `rc==0 → PASS; rc==128 → PASS; else "FAIL gate-deps: osv-scanner exited $rc (vulnerabilities found or scanner error)"; exit $rc`. So a **third-party outage rendered as a security regression** in every consumer repo. Reproduced from the real log (momentstudio run 30144541486): `rpc error: code = Unavailable` → `FAIL gate-deps: osv-scanner exited 127`.

## osv-scanner v2.3.8 exit codes — cited from SOURCE, not docs
`cmd/osv-scanner/internal/cmd/run.go@v2.3.8`: `:99 ErrVulnerabilitiesFound→1` · `:101 ErrNoPackagesFound→128` · `:104 ErrAPIFailed→129` · `:113 HasErrored→127` · `:93 HasErroredBecauseInvalidConfig→130` · `:117 →0`.
**`1` is the ONLY vulnerability code.** 129 and 130 were previously unhandled entirely. Reproduced locally with the pinned binary: clean→0, `lodash 4.17.15`→1, empty→128, and **good+unextractable lockfile→127 while printing "Total 0 packages affected"** (exactly the momentstudio shape).

## Why it stays BLOCKING (measured, not assumed)
A lockfile that is BOTH vulnerable AND unextractable exits **1, not 127** (the switch returns before `:113`), so 127 can never mask a finding the scanner actually made. **But** the unresolved manifests are left **UNSCANNED** — passing would turn *unknown* into *clean*, i.e. fail-open in the one gate meant to fail closed, and an induced extraction error could suppress it. So: `127|129|130` → `ERROR gate-deps: … could not complete the scan (exit N) - this is NOT a vulnerability finding` + exit **75** (EX_TEMPFAIL); `127|129` retried 3× with 20s/40s backoff (130 is deterministic → not retried). The observed outage did not clear in ~90min, so this **relabels** rather than unblocks that run; `quality-zero:break-glass` remains the escape hatch.

## ⚠️ THE ROLLOUT GATE — merging #279 changes NOTHING for consumers
Verified by me: tag **`v1` → `b95033002`**, **`main` → `f208a231d`**, `compare/v1...main` = **19 commits ahead**. Consumers pin `@v1` (e.g. `momentstudio/.github/workflows/quality.yml:35`). **The fix reaches the ~16 consumer repos only when the owner moves the `v1` tag — and moving it ships all 19 accumulated commits at once.** The agent verified the tag unmoved locally and on remote and did NOT move it. Owner decision with real blast radius.

## Owner sign-offs pending
1. Merge #279. 2. Whether/when to move `v1` (19 commits). 3. **exit 75** as the scan-error convention (nothing in the repo parses the gate's exit code — checked — but it is a new convention). 4. Blocking vs non-blocking on scan failure (flagged as an explicit owner call, not baked in).

## Both-states evidence
Extracted the step's **actual shipped `run:` block** from the YAML and drove it against a stub scanner: new logic **10/10**, pre-fix logic **3/10** on the identical suite, every scan-error case tripping `FORBIDDEN [FAIL gate-deps]`. The detector fires on the known-broken state, so the green means something.

## Caveat
`actionlint` with shellcheck/pyflakes enabled **hung >600s on Windows**; it was run with those disabled plus standalone shellcheck (both rc=0). Combined-mode result is UNMEASURED.
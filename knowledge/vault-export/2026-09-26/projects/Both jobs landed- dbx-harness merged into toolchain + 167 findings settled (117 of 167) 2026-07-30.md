---
title: 'Both jobs landed: dbx-harness merged into toolchain + 167 findings settled
  (117 of 167) 2026-07-30'
type: note
permalink: main/projects/both-jobs-landed-dbx-harness-merged-into-toolchain-167-findings-settled-117-of-167-2026-07-30
tags:
- harness
- toolchain
- databricks-fanout
- reconcile
- crcp
- security
- verified
---

# Both jobs landed — dbx-harness → toolchain merge + 167-finding settlement (2026-07-30)

Two LOCAL, UNPUSHED branches. Every number below was verified by me independently of the
reporting agent, with a detector control where a negative result was load-bearing.

## 1. The merge — `feat/reconcile-databricks-harness` @ `6c8e3f6`

In `~/source/ast-integrate`... **no**: in `~/source/ast-dbx-reconcile`, base `origin/main` `27fb388`.
**17 commits · 113 files · +11,060/−466 · 0 file deletions · worktree clean.**
Independently re-verified: **234 tests pass** (my own `pytest` invocation), all 4 TOOLCHAIN_ONLY
files **byte-identical** to main, `backends/` (4) + `engine/` (6) landed (absent before),
**67/67 dual-write blob-OID parity**, docs in `references/` on both trees.

Shape it settled: 23 DIVERGED (15 groups) · 45 DBX_ONLY → **31 brought / 14 rejected as spent
Program-R scaffolding** · 4 TOOLCHAIN_ONLY preserved · 3 IDENTICAL.

**Two deliberate behaviour changes the owner must weigh:**
- `GITHUB_TOKEN`/`TOKEN_REF` plumbing DROPPED (not merged) from `run_E.py`, `run_runnability.py`,
  `submit.py`, `preflight_units.py`, plus `push_probe`/`branch_pushed`. Rationale: the node clones
  read-only and cannot push, so the token injected a fleet-wide write credential into a job-cluster
  env that ships to S3 logs. `submit.py` now RAISES on those vars. Anything expecting the node to
  push a branch breaks.
- 4 wall-clock caps (3600/1800/2400/5400s) removed — toolchain caps produced a measured
  false-negative TIMEOUT on a gate-valid run. Trade-off: a hung unit now runs till the cluster dies.

## 2. The 167 — `fix/derive-167-settlement` @ `f9bde20`

In `~/source/ast-integrate`. **44 commits · 215 files · +14,771/−609 · clean.**

**ADJUDICATION CLOSED 167/167** (perfect partition, 0 missing, 0 duplicated).
**BUT ONLY 117 PATCHES LANDED. 40 findings carrying a FIXED verdict are NOT on the branch.**
"129 FIXED" does NOT mean 129 defects are gone. Verified by file content with a passing control:
C01's defect is still live (`rules/common/bash-hud-and-terminal-emit.md` = 0 US separators,
**3 live `join("")`**), C05's `read_json_status` absent (0 hits), while the same probe finds C03's
landed `isError` (2 hits in `tools/crcp/crcp/bus.py`) and C34/C06's changes.

| not landed | n | why |
|---|---|---|
| C01, C11, C32, C05, C14, C48 | 27 | held by adversarial verifiers (`safe_to_integrate=false`) |
| C33 | 8 | two incompatible implementations of ONE fix; C06 landed instead |
| C26 | 8 | its flat hook example FAILS a gate C02 had already landed |
| C09 | 3 | **no approval record** — its verifier died on a 529 |
| C36 | 2 | applied then REVERTED (C31 vs C36 gave opposite answers to "does HIGH block a merge?") |
| C18, C35 | 2 | not defects |

## 3. CRCP bearer leak — THREE primitives, not one

1. `crcp/auth_broker.py` — bearer on a caller-controlled `--url`. The inherited fix was **~85%
   right**: `_continue_paused` gated its header override on *"we observed a credential"*, so an
   off-allowlist hop with clean paused headers got NO override. Now gated on
   `not is_trusted_credential_url(url)` — ordering-independent.
2. `crcp/auth.py:275-288` — bare `urlopen` **replays `Authorization` across a cross-host 302**.
   **Proven executably** on a 127.0.0.1 sink: `CREDENTIAL LEAKED: True`.
3. `crcp/sentinel.py` — a **second live instance** of the same primitive (`_browser_headers` →
   `apply_to_headers`), two call sites. Previously unknown.

The repo already owned the right primitive at `crcp/http_secure.py:113-114`.

## 4. Refuted premise with live consequences

**C06's premise was WRONG** — `agent-self/config/settings.json` did NOT route `Edit|MultiEdit` to
the PreToolUse dispatcher (caught by C34's mirror-parity test). Without the fix `edit-checkpoints`,
`memory-spool/spool` and `dup-guard` are **unreachable for 2 of 3 tools on a deployed box.**
Fixed in `72aedc3` (1 line).

## 5. Detector failures I generated (4 in one session — all self-built probes)

- `HOOK_DISPATCH_INPROC` — I invented the token from a report's PROSE describing an approach and
  grepped for it as if it were an identifier. 0 hits looked like the report contradicting itself;
  the report was right. **Grep for symbols you have SEEN in code, never for a name paraphrased in
  a summary.**
- Cluster-ID grep over commit messages: control passed 1 of 4, so "9 of 9 absent" was an artifact —
  commit messages don't carry cluster IDs. Discarded; file-content probing is the working instrument.
- `git apply --check` with an MSYS `/c/...` path against a Windows git binary, plus `&& echo CLEAN`
  chained off `head`'s exit status → printed "can't open patch" AND "CLEAN" together.
- Called a 0-byte patch SUSPECT; it was the correct output for a no-change merge.

Standing lesson: **a control validates the instrument, not the sample** (my CRCP gitignore control
passed while I measured the wrong tree entirely).

## 6. Owner rulings still needed

C09 (3 findings, no approval record — re-verify or apply unreviewed?) · C33-vs-C06 (8 findings
stranded on the losing implementation) · C31-vs-C36 HIGH-blocks-merge contradiction (revert message
holds the reinstatement recipe) · integrator's approved-list arrived TRUNCATED mid-C33 so
C34/C36–C47 inclusion is inferred · **GCP service-account key with unencrypted `private_key` +
`roles/storage.objectAdmin` needs REVOKING** (its GCE sibling is a live OS Login credential, not the
orphan it was reported as) · GitHub Actions billing blocks all CI · OpenAI token · ~18 out-of-scope
branches I pushed during a scope drift.

Continues [[main/projects/databricks-harness-toolchain-reconcile-real-shape-12-refuted-facts-2026-07-29]]

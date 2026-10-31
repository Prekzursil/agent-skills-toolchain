# ADVERSARIAL VERIFY — MCPRESEARCH round 3 (attacking BOTH build and audit)

All sections below are MEASURED by execution. Detectors controlled in both states.

## VERDICT
AUDIT HOLDS (its one real defect is CONFIRMED and I strengthened the proof).
BUILD NOT SOUND on one narrow, cheap, executable-proven point: a fabricated measurement
shipped in two committed docs, which also carries a recommendation to edit a SHARED file.

## Q1 Commits — CONFIRMED
bfec0543 / 0d3c9e93 / 673cd180 = 13 / 2 / 1 files, all under docs/mcp-audit or
command-center/mcp-audit, 0 foreign paths. HEAD has moved 2 commits past (sibling lanes).

## Q2 The CRLF defect — CONFIRMED, and wider than the audit said
Detectors, each proven BOTH STATES end-to-end in an isolated throwaway repo
(adv_crlf_control.py): a real committed CRLF blob reads CRLF=3 / `i/crlf`; a real LF blob
reads 0 / `i/lf`. Both `git show` and `git cat-file -p` return CR bytes unconverted.

H1 = "the numbers are CRLF counts" (build).  H2 = "line counts, blobs are 0 CRLF" (audit).
  round-2 five-row table : H1 0/5 at EVERY rev tested; H2 **5/5 EXACT at 959f783f**
  round-3 two claims     : H1 0/2 at every rev;        H2 **2/2 EXACT at 0d3c9e93**
959f783f is the PARENT of 2caafe53, the commit that authored the table. The author measured
the pre-edit tree's LINE counts and headed the column "CRLF lines". No ambiguity remains.
Repo-wide: 10,569 tracked files are i/lf, 0 are i/crlf. Over ALL history these blobs max at
0 CRLF (README.md last carried CRLF at 0bfecb8a, 2026-04-01 — four months before this program).

## Q3 Did the AUDITOR control its own detectors? PARTLY — both its controls were weak
- Its byte-count control used IN-MEMORY buffers. That cannot prove `git show` returns
  unconverted bytes; had git converted, the control still passes and the zeros mean nothing.
- Its ls-files control cited `*.ps1 attr/text eol=crlf` — the ATTR column, not the `i/`
  column. It never proved `i/crlf` is reportable at all.
In a report whose headline is "a control that cannot distinguish the two hypotheses", both
controls had that shape. The conclusion survives only because I re-controlled it end-to-end.

## Q4 DoD ledger — CONFIRMED by my own execution (not read)
`_r2_dod_check.py 673cd180` -> 4/4 PASS, 5/5 controls fire, rc=0.
`_r2_dod_check.py 630bb8af` -> DoD3 FAIL, rc=1. Genuine both-states gate.
summary: call_verified=21/23, cost-measured=16/23, {DISABLE:1, INVESTIGATE:2, KEEP:20}.

## Q5 Vacuous controls? NO — all 5 verified non-vacuous by mutation
Each shipped control produces a real violation and fails closed if its target shape is
absent. dod1's `exists()` BRANCH has no dedicated control, but I mutated a path to a bogus
absolute and the predicate caught it, so the branch works.

## Q6 The auditor's "latent" gap — UPGRADED to EXECUTABLY PROVEN
Dropping 1, 2 or 3 mounted servers still prints
`SUCCESS:dod-check 4/4 DoD items PASS, 5/5 negative controls fired`, rc=0.
At 4 dropped it fails closed on the <20-row floor. Latent today (set IS correct), real gap.

## Q7 Any PASS on a non-existent input? NO
All 23 rows resolve to 2 distinct absolute source files
(C:\Users\Prekzursil\.claude.json, C:\Users\Prekzursil\.mcp.json); both exist on disk.
settings.json IS covered (MCP-FLEET-AUDIT.md:86,93,105 — "mcpctl over the 5 JSON scopes",
"settings-denied 5"), so the orchestrator's flagged concern is handled, not skipped.

## Q8 Read where it should have executed? NO for the audit's core; I re-executed everything
The 23 row names are SET-IDENTICAL to the 23 `mcp__*` namespaces in MY session — a second
independent session agreeing with the auditor's. I placed my OWN codex call:
`mcp__codex__codex` -> {"threadId":"019ff997-...","content":"VERIFY7"}. Third independent
probe. The orchestrator's briefed "a real call FAILS at agent-identity registration" is
REFUTED.

## Q9 Blast radius — the audit UNDER-SCOPED it
The audit confined the defect to ROUND3-DEFECT-CLOSURE.md. The same false claim is LIVE at
HEAD in docs/mcp-audit/ROUND2-DEFECT-CLOSURE.md:248-268 — a five-row table headed
"| blob | CRLF lines |", plus "it is not a reader artifact either: `git show` and
`git cat-file` both report 248 on the same file". Measured: both readers report 0 CRLF
(and 276 lines at 2caafe53). That sentence teaches the OPPOSITE of the estate's
windows-shell §8b ground rule, and the residual it feeds recommends editing `.gitattributes`
— a SHARED file — for a problem that does not exist.
No machine-readable artifact and no gate depends on the claim; the blob gate correctly
requires crlf==0 and passes. So the defect is prose-only in effect, but it is a fabricated
measurement plus an unnecessary shared-file action, not an honestly-scoped residual.

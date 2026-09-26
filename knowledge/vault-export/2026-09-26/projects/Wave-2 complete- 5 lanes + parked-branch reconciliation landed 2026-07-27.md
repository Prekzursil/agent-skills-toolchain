---
title: 'Wave-2 complete: 5 lanes + parked-branch reconciliation landed 2026-07-27'
type: note
permalink: main/projects/wave-2-complete-5-lanes-parked-branch-reconciliation-landed-2026-07-27
tags:
- monitor-harness
- wave-2
- compaction-checkpoint
- '2026-07-27'
---

Continues [[main/projects/lane-5-wfmon-panes-merged-deployed-e2-e-verified-2026-07-27]].

## LANDED (main 2d01ddd)
| PR | what | verified |
|---|---|---|
| #227 | `tools/agentspec` — portable spec + dispatch-safety core | B-1 RED-check by me: 64->4096 breaks 7 tests (was 0) |
| #228 | `tools/mcpctl` — read-only MCP inventory | redaction ORDER fix; 20/20 leak combos pre-fix |
| #233 | `tools/agentrail` — config-driven multi-rail over agentspec | deployed; shim E2E both-states (fail=1, --help=0) |
| #232 | monitorcore unified cockpit, 5 switchable panes | deployed 10 modules; all 5 panes E2E, zero escape bytes |
| #234 | `tools/mcpapply` — MCP mutation + live-control + web GUI | E2E dry-run vs REAL config: 3 hashes identical, 0 sidecars |
| #236 | **parked-branch reconciliation** | 4/4 critics PASS |
| #239 | 13 foundry prompt-agent docs #236 dropped | found by MY post-merge audit |
| #235 | agentspec JS runtime + parity oracle | CI green, critic MERGE-SAFE — merging |

## The reconciliation is 100% COMPLETE
Parked `fix/mcp-health-agentmail-fbmessenger`: 8 ahead / 116 behind, merge-base `26b9869`.
331 paths classified. Final audit: **every** branch-unique file is on main except
`.agents/skills/grill-me-extensive.zip` — a 5,453-byte redundant zip of a skill that IS on main
unzipped in both mirrors. Uncommitted 42: 23 landed, 19 all classified (8 GITIGNORE, 6
TAKE-*, 2 DENY-PII, 3 DEFER). **Zero unrecorded.**
`accounts.json` still the git-crypt ENCRYPTED blob on main — no plaintext token ever shipped.

### What the 4 passing critics MISSED and I caught post-merge
1. **13 foundry docs silently dropped** — in `clean_adds` input, no plan disposition, absent from
   main. NOT duplicates (main's `references/tool-a2a.md` = connection setup; these = toolbox
   shape). Cause: branch had only the `.agents/` mirror, so landing would fail D-001 — skipping
   was right, **not recording why was the gap**. Landed as #239 with the missing projection.
2. **Real PII into a PUBLIC repo** — an `@bolt.eu` employer address and a personal `@gmail` in two
   docs the plan legitimately KEPT. gitleaks cannot catch these (no token entropy). Redacted.
   **STILL OPEN FOR THE OWNER: 23 files ALREADY on main carry the same patterns** — pre-existing
   public exposure across docs/, guides/, skills/ and both mirrors. Blast-radius decision.

## Defects I fixed myself (each both-states measured)
- **monitorcore**: `os.path.normcase/normpath` is PLATFORM-DEPENDENT — equal on Windows, UNEQUAL
  on the ubuntu runner. A `projects[]` key compare passed locally, failed CI.
- **mcpctl loader**: monitorcore's new `redact.scrub` added a relative import; the by-path drift
  loader had no parent package. Fixed the LOADER (synthetic parent pkg), not the import — a
  package may import its own modules. Critic then proved the detector still fails when it should.
- **mcpapply UNC/SMB (security)**: `(root/name).resolve()` BEFORE any check; on Windows a UNC root
  discards the base, so `resolve()` dials SMB on an attacker-named host from an UNAUTHENTICATED
  route. Real SYN to `192.0.2.77:445` captured. Fixed by allowlisting the NAME first. Critic:
  47 attack vectors, 0 exploitable.
- **agentspec `_encode_int`**: `int.__str__ IS object.__str__` -> delegates to `type(x).__repr__`,
  so it never bypassed the subclass AND regressed `IntEnum`/`IntFlag` to invalid JSON. Only
  `int.__repr__` survives all 6 hostile shapes; `f"{v:d}"` is defeated by `__format__`.

## MY OWN ERRORS THIS SESSION (all caught by verification, none shipped)
- Introduced a **FALSE measured claim** into the charter by widening an agentrail-only statement
  to mcpapply without re-measuring (its suite really does 8 spawns / 92 loopback ops).
- My first fix for that **silently no-opped while printing "APPLIED"** — anchor validated against
  newline-normalised text, replaced against raw; the file has MIXED endings. Now always assert
  the content changed.
- Claimed a "CRITICAL BLIND SPOT" in the gitleaks waiver — **retracted**. Three probe bugs:
  `grep -icE 'leaks found'` matches **"no leaks found"**; a `ghp_`+36×`A` token has near-zero
  entropy so gitleaks never flags it; a paths parser using `\[.*?\]` truncates at the `]` in `[0-9]`.
- Attributed a flaky test to "a lingering SMB dial" — wrong; it is a genuine 10% flake from a real
  drain defect.
- Raised a 25-file-deletion alarm that was the **two-dot vs three-dot** trap.
- **Attempted the drain fix, measured it at 3/8 (no better than broken), and REVERTED it** rather
  than ship it. Single `read1` only returns the buffered prefix.
- **FIVE MSYS `git cat-file -p <ref>:<path>` manglings** — one fabricated a whole 36-row
  "everything DIFFERS" deploy table (every file compared against an empty string).

## Open loops recorded
`b14f41e6` mcpapply oversized-body RST discard (my single-read1 fix FAILED — do not retry; needs
`Connection: close` + bounded `shutdown(SHUT_RD)`) · `f2bda28f` agentspec FLOAT encoder has the
same subclass-dispatch hole (numpy 2.4.4 IS installed; `np.float64` raises an UNTYPED
`decimal.InvalidOperation`, and a crafted `__abs__`/`__repr__` subclass gives SILENT VALUE
FORGERY) · `52fc0e5d` stubscan Protocol/ABC exemption · `0f518ae9` wire-check entry-point exemption.

## Durable lessons
- **A test and a fix can be mutually confirming and jointly blind** at 100% coverage: agentspec's
  `_HijackedInt` overrode only `__str__` — exactly the one door the broken fix closed.
- **When a comparison says EVERYTHING differs, suspect the comparator.** Run a self-consistency control.
- `MSYS_NO_PATHCONV=1` scoped around ref:path git calls; three-dot for branch surface; never `/tmp`
  with native Python; compare CONTENT not basenames.

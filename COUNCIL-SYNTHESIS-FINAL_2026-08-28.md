# Council synthesis — six harness issues, final verdict (28.08.2026)

Inputs: 3 round-1 councils (Grok 4.6 / Gemini 3.1 Pro / GPT-5.2), 3 cross-critiques (same models,
rotated), 4 premium voices (Fable 5 high, Grok 4.6 xhigh red-team, GPT-5.6-sol high + medium
verifiers, Kimi K3 high). 11 memos on disk in `C:\Users\Prekzursil\.agents\COUNCIL-*.md`.
Receipt-checked before synthesis. Discovery only — nothing below is implemented yet.

## Facts the verifiers settled (claims that flipped during debate)

| Claim | Verdict | Consequence |
|---|---|---|
| "The OS OOM-killed the 8 subagents" | UNVERIFIED — Windows has no OOM killer; allocation failure is the mechanism; actual Cursor cancel cause unknown (conf. 0.45–0.48) | Biggest open question; needs the flight-recorder experiment, not more theory |
| WSL2+systemd offload frees RAM | FALSE — vmmem is the same physical pool; systemd not running; box caps WSL at 4 GB; vmmem is a kill-lever (G-7); P2 loops died to WSL restarts | WSL offload DEAD (unanimous after round 2) |
| Disable vector search to stabilize basic-memory | REJECTED as primary — 0.22.1 has no reranker toggle; disabling loses semantic recall (leaves lexical FTS only); the actual lesion (378 KB catalog → 1,482 chunks + watchdog killing warm-ups) is already fixed | Keep semantic ON; env-disable is a tripwire fallback only |
| "Default search is already FTS" (red-team) | WRONG per verifier — semantic-disable loses semantic recall | FastEmbed ~843 MiB warm is the real price of semantic memory; keep, revisit on recurrence |
| 10-min stability probe proved resolution | OVERCLAIM — too short | 48 h observation window before declaring basic-memory cured |
| Duplicate MCP mounts cost significant RAM | UNMEASURED | Migration still wins (status confusion, skill double-list, scope safety) but payoff size honest-unknown |
| Sync misses the Claude bridge silently | PARTLY FALSE — full sync's success sentinel already detects it | Drift fix = narrow read-only per-runtime contracts, not a new framework |
| LockFileEx lease = liveness truth | SCOPED — proves *cooperating-agent* liveness only | Fine as a 15-line helper; not a universal guarantee |
| Nested `.agents\.agents` found live (03:19 today, another session's SSOT staging) | CONFIRMED on disk | Add "no nested .agents" CRITICAL invariant to drift check; quarantine pending other session |

## The surviving action set (all reversible, zero new daemons)

1. **S0 — policy freeze (same day, ~1 paragraph in AGENTS.md).** No new Task/fan-out while free
   RAM < 8 GB (check commit headroom, not just Available MBytes). Canceled ≠ dead: before any
   relaunch, check `Get-Process` + lockfile + Wave B's `cursor-subagent-lifecycle.jsonl` (it
   already records `Composer not found` receipts — instrumentation exists). One writer per
   checkout. Sweeps are name-only (Glob), never Read dual-use skill bodies, sanitize titles.
2. **S1 — workspace-root migration (top leverage).** Stop opening `C:\Users\Prekzursil` as a
   Cursor workspace; use per-project roots. Pilot one project; verify single MCP mounts + rules
   load; rollback = reopen home. Kills the double mcp.json scope, double 359-skill listing, and
   the "unnoticed red" confusion class. NTFS junctions REJECTED (3 sources).
3. **S2 — optional 15-line LockFileEx lease** (admission ticket + writer mutex, kernel-released on
   death). Contested: red-team killed it as over-build; A/B/Fable kept it narrowed. Do AFTER S0
   policy proves insufficient, not before.
4. **S3 — basic-memory: keep the repaired stack.** Vectors ON, >100 KB generated files quarantined
   out of the vault (no native cap exists — policy + the indexer default already fixed), 48 h
   observation, env-disable only as documented tripwire (>~3 watchdog strikes/day).
5. **S4 — drift contracts.** Read-only per-runtime assertions appended to the EXISTING
   `sync_shared_state.ps1` (trace the live entrypoint first — one skip already has a sentinel).
   `DRIFT:WARN` banner, warn-only, 60 s grace/two-strike; CRITICAL invariants include the Claude
   local bridge and **no nested `.agents\.agents`**. No tray/status widget, no strict-by-default.

## Experiment backlog (settle the unknowns with data, not councils)

- **Flight recorder for the cancel cause** (top unknown): before the next fan-out, snapshot
  commit/Available/process table on a cadence + hook subagentStop; correlate the next cancellation.
- `wsl --shutdown` RAM resample (A's four-way experiment) — settles "WSL frees vs moves" locally.
- Measure duplicate-MCP RAM by diffing process working sets before/after the S1 pilot.

## Judgment calls left to the owner

1. S2 lease now vs policy-only-first (recommendation: policy first).
2. FastEmbed ~843 MiB warm as the price of semantic recall: keep (recommended, matches the
   never-lose-memory doctrine) vs reclaim.
3. Quarantine timing for the nested `.agents\.agents` (waiting on the other session's confirmation).

*Synthesized from full-memo receipts by the coordinating session, 28.08.2026 04:10 EEST.*

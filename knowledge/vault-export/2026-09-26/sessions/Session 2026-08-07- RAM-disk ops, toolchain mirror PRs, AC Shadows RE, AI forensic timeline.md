---
title: 'Session 2026-08-07: RAM/disk ops, toolchain mirror PRs, AC Shadows RE, AI
  forensic timeline'
type: note
permalink: main/sessions/session-2026-08-07-ram-disk-ops-toolchain-mirror-prs-ac-shadows-re-ai-forensic-timeline
tags:
- session-summary
- forensics
- harness
- cheat-engine
- basic-memory
- grok
---

# Session 2026-08-07 — what happened (prose)

A long multi-thread session on the Windows estate. In order:

**Disk + RAM.** C: was at 10.45 GB free (98.9% full). The dominant cause was a runaway
Claude-Code plugin leak — `~/.claude/plugins/cache/temp_git_*` had grown to **2,072 dirs /
90.5 GB in two days**. Reaped it and rebuilt the cleanup path: the existing
`Claude-PluginCache-Reaper` scheduled task wasn't broken, it was *too slow* (a per-file
attribute pass over ~1M files, once daily, losing to ~1,000 dirs/day), so it was repointed to a
fast staging-move + multithreaded `robocopy` reaper running every 6h. Net C: 10.45 -> ~143 GB
free; valuable data moved to D:, not deleted. RAM slowness was later traced NOT to leaks but to
**per-session MCP-fleet duplication**: launching the Grok CLI stood up a 201-process / 9.67 GB
second fleet (17 MCP servers duplicated), which is what made "everything extremely slow."
Working-set trims give only transient relief; commit charge, not free-RAM, is the metric that
matters on this box.

**AWS reality check.** AWS here is CLI + Bolt corporate SSO, not MCP (the 4 AWS MCP servers are
installed but disabled at user scope). Of 4 SSO accounts only `bolt-datascience` and `bolt-geo`
are genuinely usable; the other two are bucket-name enumeration only.

**Toolchain mirror — 3 PRs merged to `agent-skills-toolchain` main.** #229 made the repo a
complete drag-and-drop mirror of the live harness (104 missing skills, 10 workflows, a 69-server
MCP registry split portable/windows-only, a Codespace bootstrap installer). #193 reconciled a
conflicting Cursor-Cloud doc. #231 retired the dead AgentBridge protocol blocks. Along the way I
clobbered the repo's root `AGENTS.md`/`CLAUDE.md` by mistake (they share filenames with the
mirrored harness docs but are different documents) — caught it on a merge conflict, restored from
main, and left the user's day-to-day clone clean.

**AC Shadows (Domain Dash counter) reverse-engineering.** Drove the already-running Cheat Engine
bridge (named pipe `\\.\pipe\CE_MCP_Bridge_v99`, JSON-RPC) attached to the live game — full
scan/AOB/read/write without injecting anything new. Killed three location hypotheses (reward
co-location, adjacent (10,25) dwords, literal "10/25" string) and set up a differential scan
(1.28M candidates holding `10`, verified live across pipe reconnects). Finish requires the owner
to complete ONE domain so a single next_scan collapses it. Flagged the real risk: the Animus Hub
is a server-tracked live-service layer, so a client patch may only change what's drawn.

**AI forensic timeline + clean CSV export.** Reconstructed what every AI session was doing in two
±15-min windows (23 Jul 22:08 and 25 Jul 04:25 local). Wrote two filtered CSVs to Downloads with
all auth/AWS/Okta/SSO/cookie/login/API-key rows omitted entirely (no redaction markers), precise
per-event timestamps in both local and UTC.

**basic-memory restart.** Brought the memory server back after it showed DOWN — but caused a brief
full outage first (see the durable learning below).

## Durable learnings worth keeping

- **basic-memory runs as a parent/worker pair; killing the small (~4 MB) process downs the whole
  server.** Both share the `basic-memory.exe mcp --transport streamable-http --port 8765` command
  line; only one owns the port, the other looks like a harmless failed-to-bind duplicate but is
  the parent. Restart cleanly via the `BasicMemory-HTTP-MCP` scheduled task (Stop then Start);
  it rebinds in ~20 s. Health signal: `GET /mcp` returning **406 Not Acceptable** is HEALTHY (it
  wants MCP headers); there is no `/health` route (404 is expected). Same shared-backend cascade
  class as the Codex app-server. Do NOT reap "duplicate" MCP processes without confirming
  parent/child first.

- **SECURITY (unresolved): a Grok CLI terminal log captured a live `ANTHROPIC_API_KEY`
  (sk-ant-api03..., len 108) in plaintext** under `~/.grok/sessions/<id>/terminal/`. Owner should
  rotate that key and scrub the Grok terminal logs. Flagged, not yet actioned.

- **Forensic-timeline method:** local time here is UTC+3 (GTB Daylight); Claude/Codex/Grok
  transcripts stamp in UTC — convert before matching or the whole timeline shifts 3 h. Verify a
  vendor was IDLE by an independent signal (filesystem mtime), not just parser silence (Codex was
  genuinely idle in both windows). Grok CLI writes to `~/.grok/sessions/<uuid>/` with
  `events.jsonl` (`{"ts","type"}`), `chat_history.jsonl`, and per-call `terminal/*.log`.

- **Anti-sycophancy note:** several of my own detectors misfired mid-session (a single-quote vs
  double-quote regex over `str(dict)`; a `>>40` vs `>>32` arena shift that printed a false "none";
  swallowing git stderr so a stale `.git/index.lock` failed silently). Each was caught by
  cross-checking counts / using git as the authority. Pattern: verify the instrument before
  trusting its silence.

Relates to [[reference_disk-sanitization]], [[project_pc-performance]],
[[reference_aws-estate-bolt-sso]], [[reference_toolchain-mirror-conventions]],
[[reference_codex-shared-app-server-cascade]].
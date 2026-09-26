---
title: 'Feedback: ALWAYS build a verbose terminal monitor (progress bar + consistent
  ETA) for long background processes'
type: note
permalink: main/harness/feedback-always-build-a-verbose-terminal-monitor-progress-bar-consistent-eta-for-long-background-processes
tags:
- feedback
- monitoring
- workflow
- longrun
- eta
- process
---

# Feedback: build a verbose terminal monitor (progress bar + consistent ETA) for long background jobs

**valid_as_of: 2026-06-21. User feedback (verbatim intent: "always create a verbose accurate terminal with consistent ETA and progress bar for these kind of processes").**

**Rule:** For ANY long-running background process (Modal/FEP jobs, multi-hour compute, batch runs, long workflows) launched via `run_in_background`, **proactively build a verbose, accurate terminal monitor with a progress bar + consistent ETA** — do NOT leave the user "blind" between launch and the completion notification, and do NOT wait to be asked.

**Why:** `run_in_background` jobs are opaque — the user sees the launch + the eventual done-notification but nothing in between (stage, % complete, time remaining). A monitor restores visibility and sets expectations, which is exactly what the user asked for here.

**How to apply** — template lives at `D:\Research\projects\phenibut\compute\modal_scripts\fep_monitor.ps1`:
1. The run Tees its stdout to a STABLE log file (`... | Tee-Object -FilePath <log>`).
2. Monitor script reads that log and: (a) detects STAGE via keywords (e.g. setup/mapping → MD → analysis → DONE); (b) counts completed UNITS (FEP edge = finished complex+solvent leg pairs / 2; generalize per job); (c) **ETA = remaining_units × measured_per_unit_time** (seed per-unit time from a prior run — e.g. ~1.7 h/FEP-edge on L40S); (d) renders a progress bar `[###..]` + elapsed (from the log's CreationTime) + ETA; (e) prints the latest meaningful log line as ground-truth.
3. Add a `-Loop` flag (`Clear-Host` + `Start-Sleep 30`) for a LIVE self-refreshing view.
4. Hand the user the live command: `! pwsh -File <script> -Loop`.
5. State the estimate caveats (unit count + ETA firm up once the planning/LOMAP/mapping step finishes).

Pair with `run_in_background`'s auto-notify (monitor = live view, notification = done). Complements `longrun` (AGENTS.md §4a, which is for FOREGROUND heartbeat-wrapping); this rule is for the background/blind case. Applies to [[Migration to mariusvisalon70 (3rd Modal account) — in progress 2026-06-21]] and any future compute lane.

# CLOSE PROPOSALS — LANE B2 (MONITOR program, items R-M08 … R-M14)

**Lane:** B2 · **Owner file:** `command-center/CLOSE-PROPOSALS-M2.md` (mine alone)
**Mandate:** investigation + PROPOSALS only. No catalog write, no commit, no branch, no push, no fix.
**Measured at:** worktree `C:/Users/Prekzursil/source/ast-integrate`, HEAD `ef6e2c4b`, 2026-08-10.

> If it still reads this way, the unit died before investigating anything and no verdict here may be cited.

**COVERAGE (final):** 7 of 7 owned items MEASURED (R-M08 R-M09 R-M10 R-M11 R-M12 R-M13 R-M14).
Advisory side-checks all MEASURED: R-M01 · R-B06 · R-B08 (metadata-only, file never opened).
Nothing in this file is UNKNOWN. Machine-readable artifact for R-M09:
`command-center/_b2_m09_probe2_out.json`.

## HEADLINE

**Zero of my seven items is secretly finished** — all seven are genuinely OPEN and I propose no
CLOSE among them. The yield of this lane is four corrections to the register's own evidence, three
of which change what a future session would do:

1. **R-M11 overclaims the blocked set.** Its `next_smallest_action` says "WU10/WU11/WU13 are
   externally blocked, so the residual is 2 of 5, not 5." The cited anchor never mentions WU11.
   Correctly scoped the residual is **3 of 5** (WU9, WU11, WU12) — one more buildable unit than
   the register admits.
2. **R-M08's "1-command" action would silently break a live reaper.** `tools/monitor/codexmon.ps1:63`
   identifies the legacy monitor *by that exact directory name*; the rename makes the regex stop
   matching. The action is a pair, not a rename.
3. **R-B06's premise is REFUTED** — the note it asks for already exists on disk, and re-running the
   register's own probe manufactures a false CONFIRMED.
4. **R-M09's sub-counts are wrong** (25/6 claimed, 23/8 measured) while its conclusion is CONFIRMED —
   the classic overclaim shape: right verdict, oversized sentence.

## PROPOSAL TABLE

| id | current state | what I MEASURED | proposed disposition | evidence anchor | confidence |
|---|---|---|---|---|---|
| R-M08 | OPEN | `~/.local/opt/mingle/monitor/` still present (`codex_monitor.py` 29,693 B + `launch.ps1` + `README.md`); `monitor.retired-20260718` **absent** → rename never happened. No live consumer remains (hook repointed; `/codex-monitor` targets `~/.local/bin/codexmon.ps1`), **but** the reaper still matches the legacy board by that directory name | **STAYS-OPEN, action amended**: rename **plus** update `$LegacyPattern`, redeploy the wrapper, and fix 2 stale docs | `tools/monitor/codexmon.ps1:63`; `hooks/codex-monitor-autolaunch/check.py:54` | almost-certain (95%) |
| R-M09 | OPEN | Independently re-derived: 31 bak files, **0** names absent from live, 23 identical after LF-normalisation, 8 differing — **all 8 located in this repo's git history** → `bak_UNIQUE_not_in_live_and_not_in_git: []`, both detector controls passing. Register's "25 byte-identical / 6 differing" is REFUTED in its numbers; its conclusion is CONFIRMED | **STAYS-OPEN** (the delete has not happened; precondition re-verified today → ready-to-execute, S) | `command-center/_b2_m09_probe2_out.json` | almost-certain (95%) |
| R-M10 | OPEN | `PushNotification` = **0 hits** in the repo package AND the live package; detector controlled (same pattern hits 5 other repo files). The export half is real: `export.py`/`timeline.py`/`render_html.py`/`render_md.py`/`pdf.py`/`report_doc.py` present, `--once` advertised, `python -m monitorcore.unified --help` **rc=0** | **STAYS-OPEN** — split verdict CONFIRMED; residual is the `PushNotification` half only | `tools/monitorcore/monitorcore/export.py`; `MASTER-QUEUE.md:99` | almost-certain (95%) |
| R-M11 | OPEN | WU12 `winproc.py` absent everywhere (control: same `find` locates `timeline.py` in 5 places). WU11 `partial_repaint.py` absent from both packages — the `repaint` hits are WU7's **full**-repaint baseline, which `MASTER-QUEUE.md:98` explicitly says defers partial-repaint to WU11. WU9's gate is **measurably unmet**: no `thread_spawn` in any local Codex rollout (only 2 exist; control: `session_meta` + `multi_agent_version` both found in the same tree, value `"v2"`). WU10/WU13 anchor verified verbatim but it sits under "**Still open** — to be resolved by discovery" and **never names WU11** | **STAYS-OPEN, scope corrected**: residual **3 of 5** (WU9, WU11, WU12), not 2 of 5 | `GRILL-DECISIONS-2026-07-26.md:85-92`; `MASTER-QUEUE.md:98,107` | almost-certain (92%) WU11/WU12 · likely (75%) the WU9 gate reading |
| R-M12 | OPEN | `ThreadingHTTPServer\|text/event-stream` = 0 and `fts5\|sqlite3` = 0 over BOTH package copies; `server.py`/`hub.py`/`feed.py`/`tui.py` absent from both. Detector controlled: the same regex matches **42** other repo files, one of which is a reusable in-repo stdlib-HTTP precedent | **STAYS-OPEN** — the "web-capable cockpit" claim would be false today | `tools/mcp/mcp-http-host/mcp_http_host.py` (precedent); absence in `tools/monitorcore/monitorcore/` | almost-certain (95%) |
| R-M13 | OPEN | `control_kind` = **0** real hits (every repo hit is the register/catalog quoting this item). No `JobObject`/`AssignProcessToJobObject` anywhere in the repo. `tree_kill` exists ONLY as a local flag inside a `taskkill`-based helper outside the package — prior art to reuse, **not** a Job-Object tree-kill | **STAYS-OPEN** (and it blocks R-M17, which lane B3 independently found blocked) | `hooks/_shared/hookrun.py:206-236` | almost-certain (95%) |
| R-M14 | OPEN | `gantt` = 0 hits in both package copies; detector controlled (`hooks/skill-router/_index.json` is a real non-register hit). `timeline.py` — the IR the design leans on — present in both | **STAYS-OPEN** (owner-flagged highest-risk, explicitly off the critical path; do not start before the cheap items) | `command-center/sources/REGISTER.md:215`; `tools/monitorcore/monitorcore/timeline.py` | almost-certain (95%) |

## R-M08 — why this is not a one-command rename

`tools/monitor/codexmon.ps1:63` (deployed to `~/.local/bin/codexmon.ps1:63`, byte-identical line):

```powershell
$LegacyPattern = 'mingle.monitor.codex_monitor\.py'
```

`-Reap` uses that pattern to find and kill any still-resident **legacy** board
(`codexmon.ps1:72`). The `.` characters stand in for the path separators, so the regex requires
exactly ONE character between `monitor` and `codex_monitor.py`. After the R-M08 rename the command
line reads `…\mingle\monitor.retired-20260718\codex_monitor.py` — 18 extra characters — and the
pattern **stops matching**. The reaper would then report zero legacy boards while one is running:
a silent false negative in exactly the guard built to prevent the 2026-07-18 orphan incident.

So R-M08's action is: (a) rename the directory, (b) update `$LegacyPattern` in
**`tools/monitor/codexmon.ps1`** — the repo is SSOT, then deploy to `~/.local/bin/`, (c) fix the two
docs that still describe `/codex-monitor` as `~/.local/opt/mingle/monitor/launch.ps1`
(`docs/axis-c-design-2026-07-13/ingest-mingling-mechanics.md:161`,
`docs/harness/monitoring-jaguar-scf-2026-07-13.md:35`) — both are already wrong at HEAD,
independently of the rename. Effort is still small, but it is 4 edits, not 1.
UNVERIFIED inline: I did not execute the rename or run `-Reap`, so the break is derived from reading
the regex, not observed; the settling experiment is a `-Reap` dry run against a renamed copy.

## R-M11 — the correction that changes what gets built

`GRILL-DECISIONS-2026-07-26.md:90-92`, verbatim, under the heading `## Still open / to be resolved by
discovery, not by asking` (:85):

> - Which of WU10 (budget-truncation banner) and WU13 (relay run-id grouping) are externally blocked:
>   WU10 needs a real truncation marker to observe; WU13 was tagged NEEDS-ANTHROPIC for full fidelity.
>   Both may end the wave honestly labelled `UNVERIFIED` rather than faked.

- **WU11 is absent from that sentence.** It is *unbuilt*, not blocked: `MASTER-QUEUE.md:107` gives it a
  self-contained gate ("capability-detect + fallback to WU7 full-repaint"), needing no external party.
  Counting it as blocked hides a buildable unit and shrinks the apparent residual by one.
- The anchor is an **open question** ("*Which* of WU10 and WU13 are…"), so even for WU10/WU13
  "externally blocked" is the register's inference; the source's own fallback is to ship them
  tagged `UNVERIFIED`.
- **WU9's gate now has a concrete unblock.** Codex multi-agent v2 IS live in the runtime
  (`multi_agent_version":"v2"` in the sole August rollout) yet **no** local rollout has ever carried a
  `thread_spawn` payload — so the gate is unmet rather than merely unstarted, and the next action is
  to *capture a trace*, not to write code.

Proposed replacement `next_smallest_action`: *"Residual is 3 of 5 — WU9, WU11, WU12. WU11 is unbuilt,
not blocked (self-contained gate, MASTER-QUEUE.md:107). WU9 first needs ONE captured multi-agent
rollout: no local trace carries `thread_spawn`. Only WU10 and WU13 depend on an external party, and
both may honestly ship `UNVERIFIED`."*

## Advisory side-checks (NOT my items to dispose — flagged for the owning lane)

| check | claim under test | measured | status |
|---|---|---|---|
| **R-M01** | "merged, 100%-gated, 39 test modules — and **registered in NO launcher**" | 39 `test_*.py` — CONFIRMED exactly. `--help` rc=0 advertising five panes — CONFIRMED. But a **`[cockpit]` stanza sits at line 58 of all three `monitors.toml` copies** (repo `.agents/`, repo `skills/`, live `~/.agents/`), added by `fbedcdf6` (2026-08-09) "feat(monitor): make the unified cockpit reachable". | **The "NO launcher" half is REFUTED at HEAD → R-M01 looks CLOSE-able.** Lane B3 reached this independently — two lanes, one verdict. |
| **R-B06** | "basic-memory holds ZERO notes on Program B" | **REFUTED.** Two independent signals: (1) MCP index — `search_notes("workflow_design", search_type="text")` returns `main/projects/harness-restore/program-b-workflow-design-the-8-item-register-graded-2026-08-09` and `main/projects/program-b-is-workflow-design-a-backlog-lane-0-12-delivered-2026-08-09`; (2) filesystem — `D:\basic-memory\projects\harness-restore\Program B (workflow_design) — the 8-item register, graded 2026-08-09.md` (3,864 B, 2026-08-09 13:30) and the sibling note (3,214 B). The note IS the deliverable: it opens *"This note exists because its absence WAS the defect… Register row R-B06"* and carries the 8-item status, the INTERLEAVE-supersedes-**sequencing-not-items** fact, the R-B07 ID map and the R-B08 credential state. | **CLOSE-able on the deliverable, with a NEW narrower residual** (below). Lane B3 owns the disposition. |
| **R-B08** | live third-party credentials in a Downloads path | Metadata only — **I did not open, move, copy, scan or alter the file.** `~/Downloads/workflow_design/Diag 1.txt` still exists: **2,172,114 bytes, mtime 2026-07-21 17:23**, i.e. byte-size and mtime identical to the independent 2026-08-09 record, so contents are unchanged and the exposure is now **20 days** old (the register says 16 — it has aged). Blast radius, partial: basic-memory does **NOT** index it (`~/.basic-memory/config.json` roots are `D:\basic-memory` + a temp bench dir only). Every repo hit for `workflow_design` is the *program name*, not a path consumer. | **OWNER-GATED on OQ-6 — I stop here.** Rotation is forbidden to me (AGENTS.md §9) and I did not perform it. What is owed is the owner's quarantine decision. Residual unknown: which tool ingests `~/Downloads` (the conversation-archive path) is NOT settled by my probe. |

### R-B06 — the trap, and what the residual actually is

The register's evidence probe is the semantic phrase `workflow_design Program B unified two-program
continuation`. That probe **still returns 8 off-target results even though the note exists** — the
note itself records that re-measurement. Re-running it produces a **false CONFIRMED**: the
fan-out-contract "re-run the orchestrator's own broken probe and report CONFIRMED" failure, exactly.
A second misread compounded it: in this basic-memory build **every** score is negative — my control
query returned unambiguously on-topic notes at −23 to −27 — so "8 results, all negatively scored"
was read as "all irrelevant" when the sign carries no relevance information at all.

So the ONE note the item asks for does **not** need writing. The surviving, much narrower defect is
**recall reachability**: add the aliases the register's own query uses ("unified two-program
continuation", "two-program", "Program B") to that note's body/tags so the phrase query hits it.
Confidence: almost-certain (95%) that the note exists; likely (70%) that alias text is sufficient to
fix the phrase-query miss — embedding behaviour is not fully predictable, and the settling experiment
is to re-run the register's exact phrase after the aliases land.

## Notes on method (detector discipline)

- **My first R-M09 probe FAILED its own control and was discarded — do not cite it.**
  `command-center/_b2_m09_probe.py` hashed working-tree bytes via `git hash-object --stdin`; its
  known-present control (`README.md`) reported ABSENT because CRLF working-tree content does not hash
  to the stored LF blob. It claimed **8 files "unique, not in git"** — a pure artifact that would have
  argued *against* deleting the backup. `_b2_m09_probe2.py` compares LF-normalised content against
  every historical version of each path and **refuses to print a verdict unless both controls pass**
  (exits 2 with `DETECTOR_BROKEN`). Only `_b2_m09_probe2_out.json` is citable.
- Every "0 hits" in this file is paired with a positive control from the same pattern or the same
  invocation. No silence here is reported as evidence without one.
- Scope note: "the package" was read as BOTH copies — repo `tools/monitorcore/monitorcore/` and live
  `~/.agents/skills/workflow-monitor/monitorcore/`. Where a claim held in only one, I said so.

---
title: CLOSE-PROPOSALS-M3
type: note
permalink: dqverify-repo-20261013/command-center/close-proposals-m3
---

# CLOSE-PROPOSALS-M3 — LANE B3 (MONITOR + B-workflow_design)

**Lane:** B3 · **Owner file:** `command-center/CLOSE-PROPOSALS-M3.md` (mine alone)
**Scope:** R-M15 R-M16 R-M17 R-M18 R-M19 + R-B01..R-B08 (13 items)
**Mandate:** investigation + PROPOSALS only. I did NOT edit `WORK-UNIT-CATALOG.json`, did not commit, did not push, did not run `close.py`/`seed.py`.
**Measured at:** repo HEAD `ef6e2c4b`, branch `main`, worktree `C:/Users/Prekzursil/source/ast-integrate`, 2026-08-10.

> **If it still reads this way, the unit died before investigating anything and no verdict here may be cited.**

COVERAGE: **13/13 investigated.** All rows below carry a measurement. Two side checks (R-M01, R-M09) also measured.
**Headline: the register's picture of Program B is 1 day stale.** `docs/program-b/` landed on main on 2026-08-09 with a CI gate; three of my eight B rows are now closeable and one owner gate (Q22) has a refuted premise.

## PROPOSAL TABLE

| id | current state | what I MEASURED | proposed disposition | evidence anchor | confidence |
|---|---|---|---|---|---|
| R-M15 | OPEN | 6 `alert` defs (5 concrete sources + the Protocol stub); **every `.alert(` call site is a test** — zero production consumers. No `ntfy`, no dead-man delivery. Two real toasts exist but neither consumes a typed `Alert`. | **STAYS-OPEN** (narrow the wording, see below) | `tools/monitorcore/monitorcore/contract.py:11`; `contract.py:117`; `cockpit.py:147`; `watchdog.py:74` | almost-certain (95%) |
| R-M16 | OPEN | Exactly **5** source classes at HEAD (Agents/Codex/Databricks/SystemHealth/Mcp). `McpFleetSource` = **0 hits** repo-wide outside the register text. `tools/taskwatch_monitor` = 52 `.py` / 143 files; `tools/otel-traces` = 1 file. Nothing wired. | **STAYS-OPEN** | `tools/monitorcore/monitorcore/mcp_source.py:418`; `command-center/sources/REGISTER.md:104` | almost-certain (95%) |
| R-M17 | OPEN (dep R-M13) | `control_kind` = **0 hits** (detector controlled: `def poll` = 7 in the same command). `github` case-insensitive hits only `redact.py`. R-M13 itself unstarted → R-M17 unworkable. | **STAYS-OPEN** (blocked on R-M13) | `tools/monitorcore/monitorcore/redact.py`; R-M13 row | almost-certain (95%) |
| R-M18 | OPEN, `owner_gate: OQ-8` | OQ-8 is `state: OPEN` in the catalog. Not investigable by me. | **OWNER-GATED — I stop here** | catalog `owner_questions` → `OQ-8` | almost-certain (99%) |
| R-M19 | OPEN | No `shared/` dir exists in the repo at all; **no** `MONITORCORE-COLLISIONS` artifact (the 3 `*COLLISION*` hits are ID-collision work — a different subject). 29-tree inventory unresolved on disk. | **STAYS-OPEN** | absence of `shared/MONITORCORE-COLLISIONS/`; `command-center/D4-ID-COLLISION-CLOSE.md` (unrelated hit) | almost-certain (92%) |
| R-B01 | OPEN | Independently re-measured 2026-08-10: Defender `ExclusionPath` **0** (M1 unapplied) · `grok*` = **1** (M2 unapplied) · fan-out cap = **0 of 206** live hook `.py` (control 204 hit `def `) → M5 unapplied. Total processes **1150** (register 1,233; receipt 972 on 08-09) — three readings across three days. | **STAYS-OPEN**, and the "metric got WORSE" clause should be **withdrawn** (volatility, not trend). M1+M2 are owner-only → see the OQ-B1 gap below. | `docs/program-b/program-b-receipt.json` item R-B01; my `Get-MpPreference` run | almost-certain (93%) for M1/M2/M5 unapplied; uncertain for any trend claim |
| R-B02 | OPEN | Receipt grades 5 of 6 sub-items resolved: 4 DONE-VERIFIED (`mcp-parity`, `mcp-gui`, `api-perm-script`, `abbyy-ocr` — the last two **refute** the dossier's "likely OUTSTANDING"), 1 DROPPED-BY-OWNER, `claude-in-chrome` **NOT-CHECKED** (needs a browser). The other 10 of 16 workstreams were never re-measured. | **STAYS-OPEN**, scope narrowed to (a) `claude-in-chrome` and (b) the 10 un-remeasured workstreams | `docs/program-b/program-b-receipt.json` item R-B02 `subitems` | likely (75%) — I did not re-run the 5 sub-item probes myself |
| R-B03 | OPEN | The 11-field per-skill inventory exists **nowhere**: the only hits for its field names are the register/catalog/receipt documents that *specify* it, not an inventory. Receipt's live run: 328 skills validated, 254 pass / 74 fail, 50 failing on the estate's own `origin:` frontmatter key. | **STAYS-OPEN** — and do **not** cite the 74 as defects; the receipt correctly calls it a contract mismatch | `docs/program-b/program-b-receipt.json` item R-B03; `command-center/catalog-slices/IMP-1.json` (spec, not inventory) | almost-certain (90%) for the absent inventory |
| R-B04 | DONE-CLAIMED, `owner_gate: Q22` | **The gate premise is REFUTED by my own measurement.** `scripts/validate-all-skills.ps1:18-22` has **two** validator candidates; cand1 (`.agents/skills/.system/…`) `Test-Path=False`, **cand2 (`$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py`) `Test-Path=True`**. The script resolves and is runnable. Receipt grades R-B04 **DONE-VERIFIED** (all 8 game-domain skills pass a 328-skill run). | **CLOSE** — *and* propose **Q22 be retired as moot**. Flagged for the orchestrator, not closed by me: Q22 is still formally OPEN, so if the owner wants the row to stay gated it stays. | `scripts/validate-all-skills.ps1:18-22` + my `Test-Path` probe; `docs/program-b/program-b-receipt.json` item R-B04 | almost-certain (95%) that the gate premise is false; likely (75%) that the validation run itself is sound (I did not re-run 328 skills) |
| R-B05 | OPEN | **Satisfied at HEAD.** All four artifacts are **tracked on main** and clean: `docs/program-b/{README.md,program-b-receipt.json,mutation_probe.py}` + `ci/tests/test_program_b_register.py`. `.github/workflows/quality.yml:611-614` runs the suite **and** the both-states mutation probe on every PR. Probe re-run: `grep -rl 'unified-continuation'` = **6** files (was 0; control `workflow-foundry` = 38). HEAD is green. | **CLOSE** | `git ls-files docs/program-b/`; `.github/workflows/quality.yml:611`; `ci/tests/test_program_b_register.py:8` | almost-certain (93%) |
| R-B06 | OPEN | **Refuted — the notes now exist.** On-disk vault probe (`D:\basic-memory`, 736 notes): Program B ×2, Prompt Two ×1, monitor cockpit ×1, plus the cause-of-forgetting note. All three gaps R-B06 names are closed. | **CLOSE** | `D:\basic-memory\projects\harness-restore\Program B (workflow_design) — the 8-item register, graded 2026-08-09.md`; `…\projects\prompt-two\Prompt Two program state…(2026-08-10).md`; `…\projects\Monitor cockpit is BUILT and MERGED…(2026-08-09).md` | almost-certain (92%) for file presence; **retrievability UNVERIFIED — see below** |
| R-B07 | OPEN, `owner_gate: OQ-7` | OQ-7 `state: OPEN`. The canonical `id_map` now exists in one CI-gated place, which removes the *ambiguity risk*, but the receipt itself states confirmation is required to close the row. | **OWNER-GATED — I stop here** | catalog `owner_questions` → `OQ-7`; `docs/program-b/README.md` id-collision table | almost-certain (95%) |
| R-B08 | OPEN, `owner_gate: OQ-6`, `security_class: credential` | **STAT-ONLY, file never opened.** `EXISTS=True`, `BYTES=2172114`, `LastWriteTimeUtc=2026-07-21T14:23:01Z` — byte-identical to the receipt's figure and **unchanged for 20 days**. Contents inherited and **UNVERIFIED by me** (I did not read or scan it). | **OWNER-GATED — I stop here.** Rotation is the owner's alone (AGENTS.md §9) and is forbidden to me. | `%USERPROFILE%\Downloads\workflow_design\Diag 1.txt` (stat only); `docs/program-b/program-b-receipt.json` item R-B08 | almost-certain (99%) for existence/size/mtime |

## R-B08 — credential item: id, scope, what still trusts it, handed back

- **Id / scope:** `%USERPROFILE%\Downloads\workflow_design\Diag 1.txt`, 2,172,114 B, unmodified since 2026-07-21T14:23:01Z. Reported (inherited, 2026-07-23 controlled scan) contents: **7 Ed25519 `agent_private_key` + 24 `refresh_token`, tied to a corporate identity.** I did not open, move, copy, delete or rotate it, and I did not re-count — **UNVERIFIED inline**; the settling experiment is a read-only count-only scan.
- **What still trusts it:** unknown to me and **not** answered by this lane. OQ-6 explicitly asks whether the blast-radius trace runs before or after quarantine, so I did not run it.
- **Scope note for the owner (names + sizes only, nothing opened):** the same directory holds **20 other files**, including `Diag 2.txt` (206,304 B) and three multi-MB session dumps (`⠂ Codex Fanout Workflows.txt` 2,431,410 B; `⠂ …_PROMPT TWO.txt` 2,413,265 B; `1 Codex Fanout Workflows.txt` 1,928,675 B). A quarantine scoped to `Diag 1.txt` alone may under-cover. **I have NOT scanned any sibling and make no claim that they contain credentials — UNVERIFIED.**
- **Recommendation (owner action, not mine):** treat the 7 keys + 24 tokens as compromised regardless of exposure duration and **rotate them yourself**; quarantine the directory per OQ-6. I am explicitly forbidden from rotating and did not.

## R-M15 — the scoping correction (do not close on the toast)

The register's blanket "nothing delivers" is **too wide**; fix the sentence, not the code.

- `monitorcore/cockpit.py:147 notify()` is a **real** PowerShell MessageBox toast, fed by `push_text()` (`cockpit.py:142`) — but it carries a `Snapshot[CodexPayload]` **headline**, hard-prefixed `[codexmon]`, titled `'Codex cockpit'`. Codexmon-specific; never touches `Alert`.
- `monitorcore/watchdog.py:74 alert()` is also a real toast, but it is the freeze-watchdog's own module function taking a `str` — unrelated to `MonitorSource.alert()`.
- **Defensible claim that STAYS-OPEN: the typed `Alert` rail has zero production consumers.** Measured by `grep -rn '\.alert(' monitorcore/ tests/` — every hit is under `tests/`.
- Register inaccuracy to correct: "alert() exists on all 6 sources" → there are **5** concrete sources; the 6th is the Protocol stub at `contract.py:117`.

## R-B06 — the consistency failure the owner cares about: verified, with one honest residual

The claim **no longer holds**. Independent probe (filesystem, not MCP): `D:\basic-memory` holds dedicated notes for all three programs R-B06 names.

- **Detector honesty:** the `mcp__basic-memory__search_notes` call I attempted **failed with "Unable to connect"**. I did **not** read that silence as "zero notes" — that is precisely the single-signal trap. I switched to the mechanically independent on-disk vault (736 `.md` files; the grep returns 9 content hits including unrelated projects, proving the matcher is not over-narrow).
- **Residual, UNVERIFIED inline:** file presence does not prove **retrievability** by semantic recall, and R-B06's original probe *was* a recall probe. Because the MCP endpoint is unreachable right now I could not re-run it. The receipt claims an AFTER-state both-states probe returning exactly 1 topical hit (`docs/program-b/program-b-receipt.json` item R-B06). **Settling experiment:** re-run `search_notes 'workflow_design Program B unified two-program continuation'` once the basic-memory server is reachable; expect exactly the Program-B note.
- I did **not** write any note (proposal-only lane). Nothing needs writing — the three notes already exist.

## CONSISTENCY / DRIFT FINDINGS (proposals for the orchestrator, no catalog edits made)

1. **OQ-B1 is missing from the catalog.** `docs/program-b/README.md` and the receipt raise **OQ-B1** ("M1 Defender exclusions and M2 grok-cli residency are owner-only — apply, decline, or defer?"). The catalog carries 27 owner questions and **OQ-B1 is not among them**. R-B01 cannot be closed by any agent while its two remaining actions are owner-only, so the gate should be visible in the catalog. **Proposal: add OQ-B1 and attach it to R-B01's `owner_gate`.**
2. **A basic-memory note aged out within 10 minutes and should be marked superseded.** `…\projects\Monitor cockpit is BUILT and MERGED but nothing can launch it…(2026-08-09).md` (mtime `16:43:11`) asserts `monitors.toml` holds only four stanzas. It was **correct at write time** — the live file's mtime is `16:53:42`, ten minutes later — and became false then. Per the estate's temporal-validity convention it needs `superseded_by`. **Proposal only; I did not edit the vault.**
3. **Three of my eight B rows are stale in the catalog because a newer graded register exists on main.** `docs/program-b/program-b-receipt.json` (`graded_on: 2026-08-09`, `graded_from: code and live measurement`) supersedes the `[inherited]` evidence on R-B04/R-B05/R-B06. Whoever serialises catalog edits should prefer the receipt over `REGISTER.md` for these rows.

## SIDE CHECKS REQUESTED BY THE SPAWN (not my items to dispose)

| check | claim | measured | status |
|---|---|---|---|
| **R-M01** | "cockpit merged, 100%-gated, 39 test modules — and **registered in NO launcher**" | 39 `test_*.py` **CONFIRMED**. The "NO launcher" half is **REFUTED at HEAD**: `[cockpit]` is at line 58 of **all three** `monitors.toml` copies (repo `.agents/`, repo `skills/`, live `~/.agents/`). Landed in `fbedcdf6` (2026-08-09 16:25) "feat(monitor): make the unified cockpit reachable"; live deploy at 16:53. Three independent signals: the TOML content, the commit, and a dedicated regression test. | **CLOSE-able.** Not my item — flagging to its owner. |
| **R-M09** | a backup dir has "zero unique bytes" | The dir **still exists**: `~/.agents/skills/workflow-monitor/monitorcore.bak-20260727-091532`. A prior lane wrote `command-center/_b2_m09_probe.py` and `_b2_m09_probe2.py` but **neither has an `_out.json`** — written, never run to an artifact. The "zero unique bytes" premise remains `[inherited]` and un-re-measured. | **STAYS-OPEN.** Not my item (lane B2 owns the probe). |

## METHOD NOTES
- Every "0 hits" carries a control run in the same invocation: `control_kind` 0 vs `def poll` 7; fan-out cap 0 of 206 vs `def ` 204; `unified-continuation` 6 vs `workflow-foundry` 38.
- `total_processes` is a single point-in-time sample and is volatile (1,233 → 972 → 1,150 across three days). No trend claim is supportable from it in either direction.
- I did not run the full `pytest platform` suite. I did not touch `platform/routing/**`, `tools/measure-guard/**`, `command-center/receipts/**`, or `.github/workflows/**` (read-only inspection of `quality.yml` only).
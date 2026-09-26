---
title: AI sessions reconciliation ledger 2026-08-20
type: note
permalink: main/projects/reconciliation/ai-sessions-reconciliation-ledger-2026-08-20
tags:
- reconciliation
- sessions
- ledger
---

# AI Sessions Reconciliation Ledger

**Date:** 20.08.2026
**Version:** 1.0
**Scope:** Codex/ChatGPT sessions (Aug 15–19), Claude Code sessions (Aug 8–20, incl. 30bd50d4 + d219bc39), Cursor agent transcripts (ce3518e0, 147caba5, 48a2f2c9, c13ba69b, 9212e862), basic-memory store, open-loops + event-ledger, on-disk/git verification.
**Method:** 4 parallel archive miners + independent on-disk spot-checks. Legend: **[V]** = verified on disk/git today; **[C]** = claimed in a session transcript, not independently re-verified.

---

## 1. Master reconciliation table

| # | Workstream | Where worked | Claimed status | VERIFIED status | Remaining TODO | Actor |
|---|---|---|---|---|---|---|
| 1 | RAM/process problem — acute estate cleanup | Cursor ce3518e0 (`/aside handle the ram problem`, Aug 18) | Done | **[V] DONE** — documented in basic-memory `projects/estate-ops/Estate RAM and C-drive cleanup 2026-08-18` | Reboot-class pool-paged bloat; next owner-approved cuts (Ubuntu vhdx 96 GB, docker vhdx 48 GB, pagefile 48 GB) | Owner |
| 2 | RAM/process problem — chronic root cause (MCP eager-spawn) | Claude 30bd50d4 + d219bc39 | RCA complete, fix designed, "not yet applied" | **[V] PARTIAL** — RCA + tiered managed-mcp fleet designed [C]; apply runbook NOT executed; `~/.claude/APPLY-managed-mcp.md` not found at that path | Apply managed-mcp (admin, Claude closed); verify RAM after | Owner → agent verify |
| 3 | wfmon root cause + T0-3 trigger swap | Claude 30bd50d4 (+ 5c615def Aug 8 precursor) | "T0-3 resolved… orphan-accumulation root cause closed" | **[V] PARTIAL** — hook-level fix live [C]; but repo files (monitors.toml, workflow-monitor/*, agentmon.py) **uncommitted** in ast-integrate; deployed `~/.agents/skills/monitor-launcher/monitors.toml` (mtime Aug 17) still routes `Workflow`→wfmon and its comment says "MASTER-QUEUE T0-3, still open"; cockpit has no trigger | Land the monitor files in git; reconcile deployed vs repo copy; flip `test_registry_commit_truth` green (1 failed / 1203 passed) | Agent (git-capable: Claude/Cursor, NOT Codex sandbox) |
| 4 | Big commit pass + push (~147–160 dirty files) | Claude 30bd50d4 (planned Aug 18) | "gate pass over the 147 dirty files, commits in reviewed batches" | **[V] NOT DONE** — ast-integrate HEAD still `f7fac7b4` (Aug 14 22:58); 182 tracked-dirty (-uno), ~2,257 total porcelain entries; `main` behind `origin/main` by 3 (dependabot merges) | `git pull`, gate pass, reviewed batch commits, push | Agent (git-capable) |
| 5 | Finish-everything / Prompt Two program (ast-integrate) | Claude 30bd50d4 → Grok resume (FINISH-EVERYTHING-HANDOFF.md) → Codex Aug 15–18 WUs | Mixed per-unit claims | **[V] OPEN 0/6** — `command-center/FINISH-EVERYTHING.md` (Aug 16): A/B/C/D/E/G all still open as close-outs; code fixes A+B verifiably applied on disk; live gates red: `unit_manifest --check` drift-red (4-row manifest vs 195-row derive), vendor-gate RED (`SKILLS-MANIFEST.md:294,296`), monitor render 5/6 (crcp NOT-CHECKED); P2: 2 delivered (ADV-0027/0041) / 38 tranche-ready / catalog 2007 of 2048; AUD-0021 "delivered" claim REFUTED | Decide + run `unit_manifest.py --write` (orchestrator act); repair SKILLS-MANIFEST 294/296; prove crcp render; deliver first tranche units | Agent + 1 owner decision |
| 6 | Cross-agent harness unification (Claude+Codex+Cursor+Grok on ~/.agents) | Codex Aug 19 drivers, Claude 30bd50d4, efee9a16 | Open multi-session initiative | **[V] PARTIAL** — `.agents` populated, `sync_shared_state.ps1` exists (mtime Aug 19 09:24) [V]; never exercised from Claude sessions [C]; live `~/.agents/harness` NOT git-tracked, enshrine decision pending [C]; Aug 8 drift audit: 118 files diverge live vs repo [C] | Owner: pick harness-enshrine path; agent: drift reconcile (`sync-from-live.ps1 -Drift`) + audit pass | Owner decision, then agent |
| 7 | Cursor audit — max-effort regression | Cursor 147caba5 (+ subagents e070937c, fc677b42), ce3518e0/13ce8a16 | Root-caused both sides | **[V per transcripts] DONE (diagnosis)** — NOT the marketplace plugins. Claude side FIXED: `effortLevel: xhigh` restored (dropped in Jul 25–26 settings rewrite + CLI v2.1.234 medium-default rollout); Cursor side NOT fixED: "Max" flagged `blockedByAdminAllowlist: true`, server-side | Restore Cursor Max via dashboard/support | Owner |
| 8 | Grok 50 skills + Pack A/B (50 academic skills / 50 Grok agents) | Codex Aug 19 01:15 + 02:17 drivers + ~15 workers; finished by a post-Codex process Aug 20 ~04:43 | Complete (per owner, Aug 20 04:44) | **[V] COMPLETE** — `Downloads\grok-skill-share-links_2026-08-19.md` (Aug 19 02:07): 50/50 links, `UNIT-COMPLETE` marker; `Downloads\grok-upgraded-skills-50_2026-08-19.zip` (Aug 20 04:43) exists. Note: no Aug 19 Codex session produced the zip — created next morning outside Codex (no Aug 20 Codex sessions exist) | Claimed-in-session residuals, unverified done: integrate packs into the big skills folder; Claude-side pack equivalent | Agent |
| 9 | ChatGPT/Cursor web-session cookie preservation | Codex Aug 19 (01:15 driver, 05:24 worker), Cursor ce3518e0 | Partial | **[V] PARTIAL** — Chrome + Cursor cookies assessed recoverable from VSS snapshot [C]; Edge DB locked → UNKNOWN [C]; unsafe VSS copier deliberately not run [C]; `Cowork\scripts\launch_persistent_ai_browser_2026-08-19.ps1` + `cursor-cookie-audit` artifacts exist [V]; JSTOR cookies saved but institutional license not bound (0/14 PDFs) [C] | Owner: approve recovery lane / unblock Edge; bind e-nformation license (open 1 chapter manually), then run `browser-download-chapters.js`; delete cookies.txt after | Owner, then agent |
| 10 | e-nformation permanent access + PDF acquisition (eugenics bibliography, Holterhoff) | Cursor ce3518e0, 9212e862 | Unresolved | **[V per transcripts] BLOCKED** — 3-voice council ended mid-decision; portal watcher left running; Holterhoff 0/14 chapter PDFs | Owner action on portal/institution binding; then agent retries download | Owner → agent |
| 11 | claude-cursor CLI bridge (Claude Code on Cursor quota) | Cursor 147caba5 | Built, shipped | **[C] DONE (build)** — `~/.local/bin/claude-cursor` via cursorbridge.dev; awaiting Cursor API key | Provide Cursor API key | Owner |
| 12 | Reframe / media-studio (P1 pipeline, PR #441) | Claude d219bc39 (dominant, ends Aug 19 06:55 UTC mid-verification) | In flight | **[C] IN FLIGHT** — commit `85ca22b` (45 files) landed; vitest suite running at session end; async-validate hook disabled | Re-enable async-validate (`rm …/.disabled`), ruff sweep, read verify report, external rescan, merge PR #441 | Agent |
| 13 | DemocracyOS fork revival | Cursor c13ba69b (Aug 18) | In flight | **[C] IN FLIGHT** — awaiting ENGINE-UP/DOWN verdict; grill ledger at `Cowork\output\democracyos-grill-ledger_2026-08-18.md` [V] | Engine boot verdict → modernization program | Agent |
| 14 | Failing Claude hooks + Codex CLI upgrade | Codex Aug 19 20:17 worker | Open blocker | **[C] OPEN** — PreToolUse timeout 10s + PostToolUse exit 1 recurring; Codex npm upgrade fell back to 0.149.0-alpha.1 | Fix/time-box the failing hooks; settle Codex version | Agent (with owner env) |
| 15 | Misc Aug 19 Codex asks | Codex 01:15 / 02:17 drivers | Requested / partial | hatch-pet Star Wars pets (in progress), unified `/monitor` GUI (design-stage), single cross-AI statusline (requested), Reframe scroll-markdown converter (SUCCESS [C]), OpusClip granular audit (SUCCESS, artifacts [V]), WorkspaceIndex hard-link TOCTOU (design done, fix pending [C]), blast-radius ledger (explicit task MISS, documented) | Per-item | Agent |

---

## 2. The RAM problem — the documented fix (extracted)

**Acute (done Aug 18, Cursor ce3518e0):** box was paging (31.6 GB RAM, ~1 GB free, CPU 100%, disk queue ~16). Fix per basic-memory note `Estate RAM and C-drive cleanup 2026-08-18`:
- Power Automate (UIFlowService + LogShipper, 130k+ CPU-s) stopped, StartType=Manual (do not auto-restart).
- Standby/modified page lists flushed; user + Windows Temp cleaned.
- ~66 GB moved `Downloads` → `D:\Downloads\from-C-20260818` (nothing deleted; pointer file left).
- Result: C: 62.6 → ~127 GB free; CPU ~47%; disk queue ~0.9. RAM still tight (~2 GB) — browsers left alone.

**Chronic (designed, NOT applied):** MCP servers eager-spawn per session — "52/session duplication + Semgrep 1GB scope leak" — 61 copies of npx-cli.js observed. Fix = tiered fleet: `managed-mcp.json` (24 RAM-safe daily) + `mcp-fleet.json` (64-server SSOT; heavy 40 not auto-spawned) + `managed-settings.json` + apply runbook. **Owner action; no "applied" record found anywhere.**

## 3. The "9 unresolved failures" (event-ledger `~/.claude/event-ledger/Prekzursil-3fdf0b33/state.json`, verbatim)

1. seq 184 — resources.arsc-only APK merge broke launch (drawable-v23 vs rebuilt drawable; compat_splash_screen NotFoundException).
2. seq 383 — BC 15.4.1 EN acquisition BLOCKED: tbcml 1.1.0 EN scraper stale vs uptodown page; deferred to user.
3. seq 929 — sidecar coverage gate: 3 caplog assertions vs non-propagating loggers; 15 lines + 10 branches untested (5716 passed otherwise).
4. seq 951 — `claude mcp list` exceeded 60s, violating the 30s fleet-listing gate.
5. seq 970 — `mcp_agent_mail config set-port` writes value but exits UnicodeEncodeError (Rich checkmark on cp1252 console).
6. seq 972 — `agents mcp add` produced a registry shape rejected by the shared-state validator; `sync_shared_state` aborted before provider merge.
7. seq 973 — Agent Mail identity IndigoGlacier registered but message undeliverable: recipient approval required.
8. seq 978 — WU-B audit command traversed `search-hub/accounts.json` and printed literal credential values. Never rescan that file; print key names + literal-vs-placeholder only.
9. seq 981 — WU-B terminal critic blocked unconditional success: no safe basic-memory reliability intervention applied, no before/after latency shown. FAILED partial result.

## 4. Open-loops store (`~/.claude/open-loops/triggers.jsonl`): 56 triggers, 47 unfired

Security-critical subset (owner): rotate bolt-datascience Databricks PAT (0b39e65c, pasted plaintext Jul 21); scrub `Diag 1.txt` (aa848830 — agent_private_key ×7, refresh_token ×24); rotate the plaintext `ghp_` GitHub PAT (repeated in 30bd50d4); credential `sha256:839ca3224e60` rotation. Structural subset (agent): twin-parity repo-vs-LIVE test (982143a9); ast-integrate 75 unpushed + 128 uncommitted owner ruling (0d647047); "Prompt Two silently substituted 2048→38" owner ruling (e26093d9); RESUME.json 15 days stale (37c918ce); 18-question owner batch in one pass (49aa2acb); stub-ledger 14 unnamed flags (ed4d3e0e).

## 5. Key cross-checks / contradictions resolved

- **"Borked memory" Aug 18 request:** dequeued in Claude 30bd50d4 minutes before session end (never worked there) — but actually handled the same day by Cursor ce3518e0 (§2 acute). Not a dropped task.
- **T0-3 "resolved" vs deployed config:** the hook-level fix is claimed live, but the deployed monitors.toml comment still says T0-3 open and `Workflow` still triggers wfmon (not cockpit). The resolution exists only in uncommitted working-tree files. Truth: **live-partial, un-landed.**
- **AUD-0021 "delivered":** REFUTED by FINISH-EVERYTHING synthesis (state=BLOCKED, registered=false).
- **Grok zip provenance:** share links made in-Codex Aug 19 02:07; zip made Aug 20 04:43 by a post-Codex process (same window as JSTOR/enformation probes in `Cowork\output`); no Aug 20 Codex sessions exist. Deliverable is complete either way.
- **Max-effort regression:** NOT caused by marketplace plugins (both root causes independent: settings rewrite + CLI default rollout on the Claude side; server-side admin allowlist on the Cursor side).
- **PowerShell `Get-Item`/`Get-ChildItem` on this box intermittently returns empty for existing files** (reproduced twice today); use `cmd /c dir` to verify existence.

## 6. Top 10 open items, ranked by impact

| # | Item | Exact next action | Agent |
|---|---|---|---|
| 1 | **Exposed credentials** | Rotate `ghp_` GitHub PAT, bolt-datascience Databricks PAT, keys in `Diag 1.txt`, credential `sha256:839ca3224e60`; treat `search-hub/accounts.json` as radioactive (names only) | **Owner** (rotation), agent can inventory |
| 2 | **Chronic RAM fix unapplied** | Execute the managed-mcp apply runbook (24 RAM-safe servers; heavy 40 lazy) with Claude closed; verify duplication gone after | **Owner** (admin), agent verifies |
| 3 | **ast-integrate commit pass never landed** | `git pull` (behind by 3), gate pass over 182 tracked-dirty, reviewed batch commits incl. monitor/T0-3 files, push | **Claude or Cursor** (Codex sandbox can't write .git) |
| 4 | **Finish-everything 0/6 closed; unit-manifest drift-red** | Owner ruling to run `unit_manifest.py --write` (replaces 4-row manifest with 195-row derive); then agent re-checks green, repairs `SKILLS-MANIFEST.md:294,296` | Owner decision → agent |
| 5 | **Cursor Max effort blocked server-side** | Cursor dashboard/support: lift `blockedByAdminAllowlist` on "Max" | **Owner** |
| 6 | **GitHub Actions minutes exhausted** | Restore spending limit; then clean CI pass on main (262 unverified commits) before deferred CI wiring | **Owner** → agent |
| 7 | **Reframe PR #441 mid-verification** | Re-enable async-validate hook, ruff sweep, read verify report, external rescan, merge | **Claude** (session d219bc39 context) |
| 8 | **e-nformation/JSTOR institutional binding** | Owner opens one chapter PDF manually via e-nformation to bind license; agent then runs `browser-download-chapters.js` (Holterhoff + eugenics bibliography); delete cookies.txt after | Owner → agent |
| 9 | **Harness enshrine decision + drift** | Owner picks git-tracking path for live `~/.agents/harness`; agent runs drift reconcile (118 diverging files) + `sync_shared_state.ps1` end-to-end (fix seq-972 validator rejection first) | Owner → agent |
| 10 | **Event-ledger 9 failures + 47 open loops** | Close or cheaply re-test each (`python ~/.claude/hooks/open-loops/add.py --close <id>`); start with seq 972 (blocks harness sync) and seq 951 (MCP list gate — likely fixed by item 2) | **Any agent** |

---

*Sources: Codex `.codex\sessions\2026\08\{15,17,18,19}`; Claude `30bd50d4`, `d219bc39`, `efee9a16`, `5c615def`; Cursor `ce3518e0`, `147caba5`, `48a2f2c9`, `c13ba69b`, `9212e862`; basic-memory (D:\basic-memory, project `main`); `~/.claude/open-loops/triggers.jsonl`; `~/.claude/event-ledger/`; `command-center/FINISH-EVERYTHING{-HANDOFF,}.md`; on-disk/git spot-checks 20.08.2026.*


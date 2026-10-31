# PROGRAM REPORT — workflow delegation & control (G-15a→b) — 2026-09-22

Program: replace emergent nested-Claude delegation (claude-code-mcp, archived upstream
2026-05-15, bypass-permissions-by-default) with governed native primitives on Claude Code 2.1.277.
Decision record (authoritative): `C:\Users\Prekzursil\.agents\GRILL-DECISIONS_workflow-delegation_2026-09-22.md`
Wave: `wf_c8e4c79c-1c8` (this report unit = the e2e finisher; every claimed artifact below was
re-Read on disk by this unit before entering the inventory).

Provenance of this file: **disk-verified** (writer re-read each artifact listed in §3 via the
Read/Grep tools; paths that could not be read are marked `agent-claimed` and none of their
content is relied on).

---

## 1. Executive verdict

**All seven assigned G-items are BUILT and disk-verified; adversarial review verdict was SHIP.**
One live-execution item (G-10b container run) and two resolution probes (G-8b live spawn,
G-3b live in-harness firing) are FAILED-TO-RUN under the RAM gate — listed in §4, none block
the program.

**One correction to the adversarial review itself (found by this unit's re-verification):**
the review's single "REFUTED sub-claim" — that `deniedMcpServers` does NOT carry
`claude-code-mcp` — is contradicted by disk. Two mechanically independent probes by this unit
(Grep content-mode and the Read tool) both show `C:\Users\Prekzursil\.claude\settings.json`
lines 103-106:

```json
"deniedMcpServers": [
  { "serverName": "claude-code-mcp" },
```

which is exactly what `SELFTEST-EVIDENCE.md:45-46` and `BOTH-STATES-VERIFICATION_2026-09-22.md`
(lines 65-67, citing `settings.json:105`) claim. Instrument control: the same two probes on the
same file found `permissions.deny` at :83-91 and the PreToolUse registration at :355 — the file
is the right file and the detector fires on known-present keys. Probable mechanism of the
reviewer's error (uncertain, hypothesis only): their probe likely matched a plain string array
while the entries are `{"serverName": ...}` objects — a collection-shape detector failure.
**Do NOT apply the reviewer's follow-up (b) edit to SELFTEST-EVIDENCE.md; the evidence files
stand correct.** The reviewer's adjacent observation (claude-code-mcp and McpHub remain
REGISTERED, so the denied server may still instantiate per session = RAM tax) was NOT re-probed
by this unit and stays `agent-claimed`.

---

## 2. Per-G-item completion table

| G-item | Scope | Status | Producing command(s) (from evidence docs, disk-verified artifacts) |
|---|---|---|---|
| **G-3b/G-2c** | Subagent-scoped PreToolUse deny hook | **BUILT + BOTH-STATES VERIFIED (8/8 probe, 13/13 adversarial)** — live in-harness firing UNVERIFIED (RAM gate, §4) | Probe: `python bothstates_probe.py` (pipes 8 payloads via subprocess stdin into the exact path registered at settings.json:359). Registration: settings.json edit with backup `settings.json.bak-claude-code-mcp-guard-20260922`. Validation: `jq empty` + `jq -r '.hooks.PreToolUse[].matcher'` (14 groups, guard present once) + Python `json.load`; adversarial: 13-case crafted-payload battery |
| **G-7a** | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` functional probe | **COMPLETE** (probe doc status: COMPLETE; empirical A/B/C runs done) — raises the G-4 FLAG (§6) | `claude --version` (2.1.277); `grep -a` string-search of `claude.exe`; nested `claude -p` runs isolated via `CLAUDE_CONFIG_DIR` scratch copy + `--strict-mcp-config` + `--settings`; PreToolUse dump-hook hooklog capture; RAM pre-flight per spawn |
| **G-8b** | reader + writer restricted agentTypes | **BUILT (both files, both trees)** — live spawn resolution UNVERIFIED (§4) | Authored `~/.claude/agents/reader.md` (tools Read/Grep/Glob, `model: haiku`) and `~/.claude/agents/writer.md` (tools Read/Edit/Write/Grep/Glob, model omitted = inherit; ownership contract: caller-declared root only / no git / no deletes / report diffs); repo-canon copies; frontmatter cross-checked vs sibling `docs-lookup.md`; `validate_g8b.py` in the wave dir |
| **G-10b** | claude-code-mcp fork + container for exotics | **BUILT + BUILD-VERIFIED** (src + dist + unit tests + smoke) — live container run FAILED-TO-RUN (§4) | `git clone` upstream @ 2e401f3 → `D:\tools\claude-code-fork`; patch `src/server.ts` (schema default :447 + runtime fallback :509-510 → `'plan'`); package rename → `claude-code-fork@1.10.12-fork.1`; `npm install` (227 pkgs); `npm run build` (exit 0, dist/server.js 25,799 B); `vitest run unit` (43 pass / 2 pre-existing upstream-Windows failures, causality proven by stash probe); smoke `node dist/server.js` (JSON-RPC initialize handshake + stderr startup line) |
| **G-1c** | delegate() T0 primitive (skill) | **BUILT** (live + repo-canon, md5-verified per build unit; this unit re-read both) | Authored `~/.agents/skills/delegate-primitive/SKILL.md` (9 sections: PRE line ban, convention-vs-enforced honesty table, worked agent()/pipeline() example with provenance enum + unverified tail); mirrored to `agent-skills-toolchain/skills/delegate-primitive/SKILL.md` |
| **G-11** | Per-level model routing doctrine | **ENCODED** in SKILL.md §2 (L0 inherit / L1 effort-high mid / verification lanes omit-model / leaf haiku+effort-low) + worked example §6 | Authored into the skill (same producing commands as G-1c) |
| **G-12** | Nested-calls-count-as-fleet RAM gate | **BUILT + FUNCTION-TESTED (all 4 exit paths across two independent runs)** | `powershell -File C:\Users\Prekzursil\.agents\scripts\nested_ram_gate.ps1` — tested: `-MinFreeGB 0.05` → GATE:PASS exit 0; default 8 GB floor → GATE:BLOCK exit 2 (reap killed 1 orphan, POST 1.10 GB); `-Override` → GATE:OVERRIDE exit 0; exit-1 GATE:FAILED-TO-RUN branch settled functionally by the adversarial reviewer (patched temp copy with missing dependency → exit 1, no fail-open path exists by code) |

Supporting items (not in the assigned table, verified in passing): G-3a flat deny —
`permissions.deny` patterns at settings.json:89-90 AND `deniedMcpServers` claude-code-mcp at
:103-106 (both disk-verified this unit); G-13b provenance — SKILL.md §3 + reader/writer
prompt contracts; G-2c — user-scope settings registration (settings.json:355-364).

---

## 3. Disk-verified inventory (re-Read by this unit, 2026-09-22)

| Artifact | Verdict | Anchor |
|---|---|---|
| `C:\Users\Prekzursil\.agents\GRILL-DECISIONS_workflow-delegation_2026-09-22.md` | disk-verified | 80 lines read; owner adjudications G-1..G-15 + completion statuses L71-79 |
| `C:\Users\Prekzursil\.claude\hooks\claude-code-mcp-guard\guard.py` | disk-verified | G-3b/G-2c docstring; GUARDED_PREFIXES (both plain + McpHub); fail-open on all exception paths; deny JSON shape |
| `C:\Users\Prekzursil\.claude\settings.json` | disk-verified | :89-90 permissions.deny patterns; :103-106 deniedMcpServers claude-code-mcp; :355-364 guard registration (matcher, `python ".../guard.py"`, timeout 8) |
| `C:\Users\Prekzursil\.claude\settings.json.bak-claude-code-mcp-guard-20260922` | disk-verified | readable JSON head |
| `...\claude-code-mcp-guard\SELFTEST-EVIDENCE.md` (live + repo) | disk-verified | 13/13 verdict; backup path; the deniedMcpServers note at :45-46 is CORRECT per disk (§1) |
| `...\agent-skills-toolchain\hooks\claude-code-mcp-guard\BOTH-STATES-VERIFICATION_2026-09-22.md` | disk-verified (repo-canon) | 8/8 matrix; 3-signal matcher confirmation; honest caveats incl. UNVERIFIED-live |
| `...\workflows\wf_c8e4c79c-1c8\bothstates_probe.py` + `BOTH-STATES-VERIFICATION_2026-09-22.md` | disk-verified (wave scratch) | present in dir listing; repo copy content-verified |
| `C:\Users\Prekzursil\.agents\docs\PROBE-depth-dial.md` | disk-verified | status COMPLETE; §0 verdict table; §3 empirical A/B/C; G-4 FLAG |
| `C:\Users\Prekzursil\.claude\agents\reader.md` | disk-verified | tools [Read,Grep,Glob], `model: haiku`, read-only contract |
| `C:\Users\Prekzursil\.claude\agents\writer.md` | disk-verified | tools [Read,Edit,Write,Grep,Glob], no Bash/Task, model omitted, 4-clause ownership contract |
| `...\agent-skills-toolchain\agents\reader.md`, `writer.md` | disk-verified | both present in repo agents/ dir |
| `...\workflows\wf_c8e4c79c-1c8\G-10b-fork-report.md` | disk-verified | status ledger (10 steps), findings, honest FAILED-TO-RUN for container |
| `D:\tools\claude-code-fork\src\server.ts` | disk-verified | :443-448 schema `default: 'plan'` + hardening description; :506-513 runtime fallback `'plan'` with estate-fork comment |
| `D:\tools\claude-code-fork\dist\server.js` | disk-verified | :371-375 compiled `default: 'plan'` |
| `D:\tools\claude-code-fork\smoke-stderr.txt` | disk-verified | "Claude Code MCP server running on stdio" |
| `C:\Users\Prekzursil\.agents\skills\delegate-primitive\SKILL.md` | disk-verified | §0 PRE line; §1 honesty table; §2 G-11 routing; §3 G-13b provenance; §5 G-12 RAM pre-flight; §6 worked example; §7 mail pattern; §9 gate receipts |
| `...\agent-skills-toolchain\skills\delegate-primitive\SKILL.md` | disk-verified | present |
| `C:\Users\Prekzursil\.agents\scripts\nested_ram_gate.ps1` (live) + `...\agent-skills-toolchain\scripts\nested_ram_gate.ps1` (repo) | disk-verified | exit-code contract 0/1/2 fail-closed; G-12/G-26/G-99 flow |
| `...\workflows\wf_c8e4c79c-1c8\journal.jsonl`, `validate_g8b.py`, `adv_review_*.py` | disk-verified (presence) | wave-dir listing |
| Reviewer claim: "claude-code-mcp + McpHub remain REGISTERED servers (instantiation RAM tax)" | **agent-claimed** (not re-probed by this unit) | — |
| Reviewer claims: LICENSE untouched, tests encode hardening, ENOENT containment limit | agent-claimed (consistent with the disk-verified src/dist sites but not individually re-read) | — |

---

## 4. FAILED-TO-RUN list (never reported as PASS)

1. **G-10b live container run** — Docker daemon up (29.8.0) but free RAM 0.84 → 0.80 GB
   (2 probes), below the safe build threshold on this commit-exhaustion-prone box.
   Authoring complete (Dockerfile, docker-compose.fork.yml, docker-stdio.sh); the run is the
   only deferred step. Settling experiment: `docker build` + `docker run --rm -i --network none`
   when free RAM ≥ threshold.
2. **G-8b live spawn-resolution probe (reader/writer)** — no `--strict-mcp-config` test spawn
   run under the ~1.9 GB floor. Both agent files are authored and shaped per the working
   sibling, but resolution by the live runtime is UNVERIFIED.
3. **G-3b live in-harness hook firing** — payloads were synthetic; a live subagent invoking
   the MCP tool through the real harness was not run (would mount the global registry = the
   forbidden freeze pattern). Note the related G-7a catalog-gating finding: a capped subagent
   never receives the spawn tool at all, so no PreToolUse fires for it — the hook's live
   exercise requires an uncapped subagent actually calling a guarded tool.
4. **G-7a runtime error-string path** — not exercised live (enforcement observed via
   tool-catalog omission; the binary's `Subagent nesting limit reached` error is the backstop).
   Disclosure, not a defect.
5. **GrowthBook live value** (`tengu_hazel_trellis`) — unknowable statically; the effective
   unset-env cap is GrowthBook-or-fallback-3. Settling experiment named in PROBE-depth-dial §8.

---

## 5. Harness-VCS reconcile checklist (agent-skills-toolchain)

Repo root: `C:\Users\Prekzursil\source\agent-skills-toolchain`. No commits made by any unit
(orchestrator commits). Items:

- [ ] **Commit (untracked, repo-canon already present):** `hooks/claude-code-mcp-guard/`
      — guard.py, selftest.py, validate-and-pipetest.ps1, verify-entry.ps1,
      SELFTEST-EVIDENCE.md, BOTH-STATES-VERIFICATION_2026-09-22.md (mirrored byte-identical,
      SHA256 2383eef0… per build unit).
- [ ] **Commit:** `agents/reader.md`, `agents/writer.md` (repo-canon copies present).
- [ ] **Commit:** `skills/delegate-primitive/SKILL.md` (repo-canon present).
- [ ] **Commit:** `scripts/nested_ram_gate.ps1` (repo-canon present).
- [ ] **Live↔repo gap (decision needed):** BOTH-STATES-VERIFICATION_2026-09-22.md exists in
      the wave scratch dir + repo-canon but NOT in the live hook dir
      `~/.claude/hooks/claude-code-mcp-guard/`. Either mirror it into the live dir (evidence
      lives with the hook) or accept repo-canon as its home; do not lose it with the scratch dir.
- [ ] **PRE-EXISTING drift (not introduced by this program, flag only):** `mcp_ram_audit.ps1`
      and `reap_orphan_mcp.ps1` exist only under `~/.agents/scripts/` with no
      `agent-skills-toolchain/scripts/` counterpart.
- [ ] **Optional:** record a pointer to `D:\tools\claude-code-fork` (the G-10b fork, dirty-on-main,
      5 modified + 5 untracked files, upstream origin intact) in toolchain docs at fan-in.

---

## 6. Follow-ups for the owner / next session

1. **G-4 re-adjudication (owner decision, load-bearing):** decision "5 — native max, no env
   set" rests on a measured-wrong premise — with the env UNSET the effective cap is the
   GrowthBook value or hardcoded fallback **3** (binary: `var o=3,_="tengu_hazel_trellis"`);
   depth 5 requires setting the env var (or GrowthBook delivery). Actions when decided: update
   the decision log G-4 row + the delegate-primitive SKILL depth-cap row.
2. **Do NOT apply the adversarial review's deniedMcpServers correction** (§1 of this report) —
   the evidence-file claim is disk-correct; the reviewer's probe was the broken instrument.
   Their registered-server RAM-tax observation stays open as an agent-claimed item worth one
   cheap re-probe.
3. Run the three FAILED-TO-RUN probes when the RAM floor passes (container run; reader/writer
   live spawn; live hook firing).
4. G-14 post-wave sweep (owner-delegated at fan-in): rename tests_wave.py / delete dead file /
   re-measure / commit — per the decision log.

---

## 7. Wave-1 resume note (wf_c8e4c79c-1c8)

The run is **parked-stalled**; resume via `resumeFromRunId` with run id `wf_c8e4c79c-1c8`.
Salvage pattern: the wave journal `journal.jsonl` + per-agent `agent-*.jsonl` transcripts live
in `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\682da5f0-62c5-4c76-826b-fdf5508e20a9\subagents\workflows\wf_c8e4c79c-1c8\`
(disk-verified present, ~20 agent transcripts). Known resume gotcha (estate memory
2026-09-19): resume-after-edit = full cache miss — prefer journal-salvage over re-editing the
workflow mid-run. This report supersedes the need to re-derive program state: the inventory in
§3 is the disk-verified ground truth a resumed orchestrator should trust; treat anything not
listed there as agent-claimed until re-read.

*Report written by the wf_c8e4c79c-1c8 program-report unit, 2026-09-22. Verdict:
SUCCESS:program-report — all assigned G-items BUILT + disk-verified; 3 probes FAILED-TO-RUN
under the RAM gate (honestly listed); 1 reviewer-refutation reversed by disk evidence.*

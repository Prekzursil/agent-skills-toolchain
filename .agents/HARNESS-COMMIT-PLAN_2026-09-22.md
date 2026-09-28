# HARNESS-COMMIT-PLAN — 2026-09-22 (Task B5, wf_c8e4c79c-1c8 fan-in)

> **PROVENANCE: disk-verified.** Every path, hash, mtime and git state below was measured
> by this unit (B5) between ~21:45 and ~22:00 on 2026-09-22 via Read/sha256sum/git-status
> probes. Confidence: **high** = measured by this unit; **likely** = single corroboration;
> UNVERIFIED = named. This unit performed **NO git write operations** (no add/commit/push/
> stash) — repo-canon *file copies* were made where a plan `git add` would otherwise target
> a nonexistent path; those copies are hash-verified byte-identical to their live sources
> (receipts in §C.0). Commits are ORCHESTRATOR-side.

---

## 0. Repo topology (measured — this reshapes the plan)

| Tree | What it is | Branch | HEAD | Dirty (non-profile) |
|---|---|---|---|---|
| **R** = `C:\Users\Prekzursil\source\agent-skills-toolchain` | canonical dev checkout, PRIVATE-ONLY repo | `cursor/p2-loop-to-green-0db0` (ahead 5 of its origin branch) | `e55493a02` 09-22 21:39 "chore: reconcile untracked harness residue (nested_ram_gate, biomni-local skill)" | 1 modified + ~11 untracked harness paths (§B.1) |
| **A** = `C:\Users\Prekzursil\.agents` | **second LIVE checkout of the SAME GitHub repo** (harness-at-root layout; origin = agent-skills-toolchain.git) | `live-capture/2026-09-02` (tracks origin) | `05b28282` 09-20 04:36 | 154 entries total; tonight's subset in §B.2 |
| **W** = `C:\Users\Prekzursil\Documents\GitHub\WebCoder` | wave repo | `wave/nextjs-migration` (no upstream, no PR) | `40fda968` 09-22 17:43 | HOT — see §D |

Notes:
- R and A are the SAME repo on DIFFERENT branches — a file can be tracked in R and
  untracked in A simultaneously (measured: `scripts/goat_health.ps1`).
- `browser-profiles/**` churn in both R and A status is the tracked live Chrome profile
  (owner decision, private repo) — NOT tonight's harness work. **Every add below is
  path-scoped; none touches browser-profiles.**
- PROGRAM-REPORT §5 is **partially stale**: its "Commit: scripts/nested_ram_gate.ps1"
  item is ALREADY DONE (`e55493a02`, tonight 21:39 — before this unit ran). All other
  §5 items verified still open (high).

---

## A. Byte-identity live↔repo verification (sha256, this unit)

### A.1 PROGRAM-REPORT §3 mirror claims — all CONFIRMED

| Pair (repo ↔ live) | sha256 (match) | Verdict |
|---|---|---|
| `hooks/claude-code-mcp-guard/guard.py` | `832d113d…` | **IDENTICAL** |
| `hooks/claude-code-mcp-guard/selftest.py` | `1f77356e…` | **IDENTICAL** |
| `hooks/claude-code-mcp-guard/validate-and-pipetest.ps1` | `f5f1caf2…` | **IDENTICAL** |
| `hooks/claude-code-mcp-guard/verify-entry.ps1` | `d15cd4bd…` | **IDENTICAL** |
| `hooks/claude-code-mcp-guard/SELFTEST-EVIDENCE.md` | `e846e4bf…` | **IDENTICAL** |
| `hooks/claude-code-mcp-guard/BOTH-STATES-VERIFICATION_2026-09-22.md` | `2383eef0…` (matches the prefix PROGRAM-REPORT claimed) | **repo-only** — live-gap exactly as PROGRAM §5 flagged (decision item, §C.8) |
| `agents/reader.md` | `561a67b0…` | **IDENTICAL** |
| `agents/writer.md` | `c7392799…` | **IDENTICAL** |
| `skills/delegate-primitive/SKILL.md` | `d43b2d8f…` | **IDENTICAL** |
| `scripts/nested_ram_gate.ps1` | `21541b2f…` | **IDENTICAL** (and already tracked — committed `e55493a02`) |
| `docs/PROBE-depth-dial.md` ↔ `.agents\docs\PROBE-depth-dial.md` | `5b357f3d…` | **IDENTICAL** |

### A.2 Cross-tree pairs beyond the report's claims

| Pair | Verdict |
|---|---|
| `.agents\agents.json` (SSOT, live, biomcp add 21:29) ↔ R `.agents/agents.json` (tracked mirror) | **DIFFERS** (`0ee91a77…` vs `3abdb9c0…` at measure time) — repo mirror stale → reconciled by this unit (§C.0), commit 7 |
| `scripts/goat_health.ps1` (live mtime today) ↔ R tracked | **IDENTICAL** (`3a67ceb2…`) — no action |
| `scripts/zai_key_failover.py` ↔ R | **IDENTICAL** (`ba7994d1…`) |
| `scripts/zai_biomni_key_propagate.sh` ↔ R | **IDENTICAL** (`b91eef83…`) |

### A.3 Live-only artifacts NOT in the PROGRAM inventory (found by tonight-sweep, high)
- `~\.claude\rules\common\native-capability-map.md` (20:32, 3,407 B) — new always-on rule
  ("never conclude tool absence" + live-rail routing order; cites wf_c8e4c79c-1c8
  measurement). No repo copy existed → copied by B5.
- `~\.claude\hooks\claude-code-mcp-guard\mirror-to-repo.ps1` (20:31) — live-only in the
  hook dir → copied by B5.
- `~\.claude\commands\pvc-verify.md` (20:57) — new command, no repo copy → copied by B5.
- `~\.agents\GRILL-DECISIONS_workflow-delegation_2026-09-22.md` (20:54) and
  `~\.agents\PROGRAM-REPORT_2026-09-22.md` (21:11) — untracked in BOTH checkouts →
  copied by B5 into R `.agents/` (the established dated-reports mirror home:
  `HARNESS-AUDIT_2026-08-27.md` et al. live there).

---

## B. EVERY untracked/modified harness path from tonight (2026-09-22)

### B.1 R repo — `git status` minus browser-profiles (high; full list, nothing truncated)

| Path | State | mtime | Disposition |
|---|---|---|---|
| `skills/firecrawl/SKILL.md` | M (+26 lines) | 21:03 | commit 6 (escalation-ladder section; diff re-read by B5) |
| `agents/reader.md`, `agents/writer.md` | ?? | 20:3x | commit 2 |
| `hooks/claude-code-mcp-guard/` (7 files incl. B5-copied `mirror-to-repo.ps1`) | ?? | 20:26-20:58 | commit 1 |
| `skills/delegate-primitive/` | ?? | 20:5x | commit 3 |
| `rules/common/native-capability-map.md` | ?? (B5 copy) | 20:32 | commit 4 |
| `docs/PROBE-depth-dial.md`, `docs/probe-g7a-evidence/` | ?? | 20:23 | commit 5 |
| `.agents/GRILL-DECISIONS…`, `.agents/PROGRAM-REPORT…` | ?? (B5 copies) | 20:54/21:11 | commit 7 |
| `.agents/agents.json` | M (B5 reconcile to live SSOT) | 21:29 live | commit 7 |
| `scripts/mcp_ram_audit.ps1`, `scripts/reap_orphan_mcp.ps1` | ?? (B5 copies; G-99 pair, untracked in both checkouts before) | 09-20 / 20:16 | commit 8 |
| `rules/common/mcp-process-hygiene.md` | ?? (pre-tonight, 09-20; the RULE half of the G-99 pair — untracked since authoring) | 09-20 | commit 8 |
| `scripts/firecrawl_mcp_health.ps1` (18:50), `scripts/fleet_mcp_lint.py` (20:04), `scripts/rail_health.ps1` (21:25) | ?? (B5 copies) | today | commit 8 |
| `commands/pvc-verify.md` | ?? (B5 copy) | 20:57 | commit 9 |
| `scripts/biomni/` (7 files; 09-20 + bm-doctor/wsl-helpers today 17:54) | ?? | mixed | commit 9 (optional) |
| `harness-audits/health/` (health-2026-09-21/22.json, reap-log) | ?? | 17:03-17:08 | commit 9 (optional) |
| `.video_agent/plugin_root` | ?? | 09-19 | **flag-only** (not tonight; origin unclear) |

CRLF note (commit 6): git warns the working copy is CRLF→LF-normalizable; the +26 diff is
clean content — no action, normal repo behavior.

### B.2 A repo (live checkout) — tonight's subset of its 154 dirty entries (high)

- **Modified today:** `agents.json` (21:29, biomcp add; `.bak-biomcp-add-20260922-212952`
  sits beside it — NEVER commit), `skills/firecrawl/SKILL.md` (21:02, same ladder),
  `session-catalog.md` (17:47).
- **Untracked today:** `GRILL-DECISIONS_workflow-delegation_2026-09-22.md`,
  `PROGRAM-REPORT_2026-09-22.md`, `HARNESS-COMMIT-PLAN_2026-09-22.md` (this file),
  `docs/PROBE-depth-dial.md`, `docs/probe-g7a-scratch/`, `skills/delegate-primitive/`,
  `scripts/nested_ram_gate.ps1` (20:52), `scripts/reap_orphan_mcp.ps1` (20:16),
  `scripts/firecrawl_mcp_health.ps1`, `scripts/fleet_mcp_lint.py`,
  `scripts/goat_health.ps1`, `scripts/rail_health.ps1`, `distillery/2026-09/20260922-*.md`
  (3 transcript distillations).
- **Not tonight (flag-only):** `memory-map.md` (09-19), `skills/cyberstrike` (09-19),
  `skills/microsoft-foundry/**` (09-20), `.skill-lock.json` (09-20),
  `scripts/mcp_ram_audit.ps1` (09-20), `scripts/register_zai_failover_task.ps1` (09-19),
  `hooks/` dir (09-06/09-19), `HOME_AGENTS.bak-grill2-20260920`, azure-* skill dirs,
  `.copilot-for-azure-skills-manifest.json`.
- Optional A-branch capture commit in §C.10.

### B.3 Live `.claude` tree — tonight (high)
Mirrored+verified: `hooks/claude-code-mcp-guard/`, `agents/reader.md`, `agents/writer.md`.
Copied by B5: `rules/common/native-capability-map.md`, `commands/pvc-verify.md`,
`hooks/.../mirror-to-repo.ps1`.
**Live-only state, intentionally NOT committed:** `settings.json` (guard registration
20:04 + later edit 21:20 — the registration is *documented* in BOTH-STATES-VERIFICATION;
live user settings are not repo-tracked config), `settings.json.bak-claude-code-mcp-guard-20260922`
(backup — never commit), `.credentials.json` (**never commit, never print**),
`hooks/semantic-router` touch 21:11 (runtime write; R copy unmodified — no action),
`hooks/local-tui-reminder` 17:04 (tracked in R, unmodified — no action).

---

## C. THE COMMIT PLAN (R repo — canonical home; orchestrator executes)

### C.0 Pre-made repo-canon copies (B5, hash-verified byte-identical — receipts)
`rules/common/native-capability-map.md` (`1fe82fdf…`), `.agents/GRILL-DECISIONS…`
(`4a900223…`), `.agents/PROGRAM-REPORT…` (`da76f42b…`), `hooks/claude-code-mcp-guard/
mirror-to-repo.ps1` (`25821688…`), `commands/pvc-verify.md` (`034339f3…`),
`.agents/agents.json` (`0ee91a77…` = live SSOT), `scripts/{mcp_ram_audit,reap_orphan_mcp,
firecrawl_mcp_health,fleet_mcp_lint,rail_health}` (§B.1). Post-copy `git status`
receipt: all show `??` (agents.json ` M`) — high.

**Pre-step (every commit):** re-run `git status --porcelain` and diff against §B.1 —
sibling lanes are live on this box and may add paths; verify before each add. Do NOT
`git add -A` / `git add .` (browser-profiles churn + unvetted paths). Optional sanity
for commit 1: `powershell -File hooks/claude-code-mcp-guard/validate-and-pipetest.ps1`.

```powershell
cd C:\Users\Prekzursil\source\agent-skills-toolchain

# 1. Guard hook (G-3b/G-2c) — 7 files: guard.py, selftest.py, validate-and-pipetest.ps1,
#    verify-entry.ps1, SELFTEST-EVIDENCE.md, BOTH-STATES-VERIFICATION_2026-09-22.md, mirror-to-repo.ps1
git add hooks/claude-code-mcp-guard
git commit -m "feat(hooks): claude-code-mcp-guard - subagent-scoped PreToolUse deny for claude-code-mcp (G-3b/G-2c, both-states verified 8/8 + 13/13)"

# 2. Restricted agent types (G-8b)
git add agents/reader.md agents/writer.md
git commit -m "feat(agents): reader + writer restricted subagent types - read-only / no-git-no-delete ownership contracts (G-8b)"

# 3. Delegation primitive skill (G-1c/G-11/G-13b)
git add skills/delegate-primitive
git commit -m "feat(skills): delegate-primitive - governed nested delegation with per-level model routing and provenance stamps (G-1c/G-11/G-13b)"

# 4. New always-on rule
git add rules/common/native-capability-map.md
git commit -m "feat(rules): native-capability-map - never conclude tool absence; live-rail routing order (measured wf_c8e4c79c-1c8)"

# 5. G-7a depth probe + evidence
git add docs/PROBE-depth-dial.md docs/probe-g7a-evidence
git commit -m "docs(probe): subagent depth dial - empirical A/B/C runs, GrowthBook/fallback-3 finding (G-7a)"

# 6. Firecrawl failure ladder (tonight's measured root cause)
git add skills/firecrawl/SKILL.md
git commit -m "docs(skills/firecrawl): MCP failure escalation ladder - FIRECRAWL_API_URL dead-endpoint root cause, fix-the-lane standing rule"

# 7. Program receipts + registry mirror
git add .agents/GRILL-DECISIONS_workflow-delegation_2026-09-22.md .agents/PROGRAM-REPORT_2026-09-22.md .agents/HARNESS-COMMIT-PLAN_2026-09-22.md .agents/agents.json
git commit -m "docs(program): workflow-delegation receipts 2026-09-22 - grill decisions, program report, commit plan; sync agents.json mirror (biomcp add)"

# 8. G-99 hygiene pair (scripts + rule) and tonight's rail-health probes
git add scripts/mcp_ram_audit.ps1 scripts/reap_orphan_mcp.ps1 rules/common/mcp-process-hygiene.md scripts/firecrawl_mcp_health.ps1 scripts/fleet_mcp_lint.py scripts/rail_health.ps1
git commit -m "chore(scripts): MCP health/reaper repo-canon + G-99 hygiene rule - mcp_ram_audit, reap_orphan_mcp, mcp-process-hygiene, firecrawl health probe, fleet MCP lint, rail health"

# 9. OPTIONAL mixed-date residue (biomni 09-20+today, pvc-verify today, health captures today)
git add scripts/biomni commands/pvc-verify.md harness-audits/health
git commit -m "chore: biomni doctor/watchdog helpers, pvc-verify command, harness health audit captures"
```

### C.1 NEVER-commit list (hard)
`*.bak*` (settings/agents.json/HOME_AGENTS backups), `.credentials.json`,
`local.json`, `browser-profiles/**` via broad adds, `mitm_mcp_traffic.db`, any
`*token*`/`*.key`/`*.pem`. Repo is PRIVATE-ONLY — never `gh repo edit --visibility`.

### C.8 Open decision inherited from PROGRAM §5
`BOTH-STATES-VERIFICATION_2026-09-22.md` lives repo-only (scratch + repo-canon), not in
the live hook dir. Default taken here: **repo-canon is its home** (repo = SSOT). The
alternative (mirror into `~\.claude\hooks\claude-code-mcp-guard\`) is one `cp` if the
owner prefers evidence-with-hook.

### C.10 OPTIONAL — A-repo capture commit (preserves live state on its capture branch)
```powershell
cd C:\Users\Prekzursil\.agents
git add GRILL-DECISIONS_workflow-delegation_2026-09-22.md PROGRAM-REPORT_2026-09-22.md docs/PROBE-depth-dial.md skills/delegate-primitive scripts/nested_ram_gate.ps1 scripts/reap_orphan_mcp.ps1 scripts/mcp_ram_audit.ps1 agents.json session-catalog.md
git commit -m "capture/2026-09-22 (1): workflow-delegation wave artifacts + registry biomcp add"
```
(Durable home stays R per harness-vcs-hygiene; this only snapshots the live branch.)

---

## D. WebCoder surface (adjacent; measured ~21:55 — **HOT TREE, DO NOT COMMIT YET**)

1. **Index is POISONED:** `git diff --cached --name-only | wc -l` = **8,724 staged
   paths, ALL under `backend/venv/`** (0 non-venv staged). A plain `git commit` after a
   scoped add would sweep all of them in; and per the estate pathspec-commit trap,
   `git commit -- <paths>` silently restores staged deletions of on-disk files.
   **Mandatory first step: `git reset`** (unstage everything), then scoped adds only.
2. **Sibling lanes are mutating W right now** (high): since WAVE-REPORT was written, the
   D3 renames landed (`backend/{control,problems,submissions}/test_wave.py` now exist,
   no `tests_wave.py` left in status), `backend/webcoder_api/test_webcoder_api.py`
   appeared (the report called it absent), and `backend/users/permissions.py` +
   `backend/webcoder_api/settings.py` became modified (auth P0 fixes in flight — the
   report listed only 5 modified). venv churn grew 6,803 → 8,724. **Re-measure at commit
   time; wait for lanes to declare done.**
3. Current non-venv surface (21:55): untracked 18 — `.coverage-thresholds.json`,
   `.github/workflows/frontend.yml`, `backend/Dockerfile`, `backend/Dockerfile.judge`,
   `backend/{control,problems,submissions,users}/test_wave.py`,
   `backend/submissions/judge_utils/backend.py`, `backend/webcoder_api/test_settings.py`,
   `backend/webcoder_api/test_webcoder_api.py`, `docker-compose.yml`, `docs/`,
   `frontend/web/`, `frontend/webcoder_ui/{build,test}-baseline.log`,
   `mitm_mcp_traffic.db`; modified 7 — `.github/workflows/django.yml`,
   `backend/.coverage`, `backend/.env.example`, `backend/pytest.ini`,
   `backend/submissions/tests.py`, `backend/users/permissions.py`,
   `backend/webcoder_api/settings.py`.
4. Suggested grouping AFTER `git reset` + lanes settled (explicit file lists, NO
   `backend/` dir-add — it would swallow venv):
   - `feat(frontend)`: `git add frontend/web .github/workflows/frontend.yml`
   - `feat(backend)`: explicit add of the 13 backend paths above (minus `.coverage`)
   - `feat(infra)`: `docker-compose.yml backend/Dockerfile backend/Dockerfile.judge .github/workflows/django.yml .coverage-thresholds.json`
   - `docs`: `git add docs`
   - OWNER DECISION first (WAVE-REPORT action 5): venv untracking
     (`git rm -r --cached backend/venv` + `.gitignore` entries for
     `backend/venv/`, `backend/.coverage`, `mitm_mcp_traffic.db`,
     `frontend/webcoder_ui/*-baseline.log`) vs accepting tracked venv. Recommended:
     untrack. `backend/.env` stays ignored (verified by wave report).

---

## E. Residuals / follow-ups (not commit-scope)
- G-4 depth-cap re-adjudication + SKILL/decision-log row updates (PROGRAM §6.1).
- Reviewer's "registered claude-code-mcp/McpHub RAM-tax" observation remains
  agent-claimed (PROGRAM §6.2) — one cheap re-probe when convenient.
- `.video_agent/plugin_root` (09-19) and `scripts/register_zai_failover_task.ps1`
  (09-19): untracked in both checkouts, origin unlabeled — flag for owner.
- A-repo older drift (cyberstrike/microsoft-foundry/azure skills, memory-map,
  `.skill-lock.json`): pre-tonight, out of B5 scope, listed so it is not lost.

*Written by B5 (wf_c8e4c79c-1c8), 2026-09-22 ~22:00. SUCCESS:b5-reconcile-prep — mirrors
verified, tonight-path inventory complete for all three trees, plan executable as-is,
no git writes performed by this unit.*

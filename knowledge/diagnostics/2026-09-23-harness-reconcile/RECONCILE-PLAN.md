# VM ↔ HOME Harness Reconciliation Plan
Wave: SYNTHESIS (still READ-ONLY — this is a plan, nothing changed). Date: 2026-09-23.
VM = offload-w2025 (this box, 100.117.115.55). HOME = desktop-a60s9gp (100.97.16.36, read via rclone `homeC:`/`homeD:`).
Grounded in the three diagnosis artifacts in this dir (diag-context-rot.md, diag-unpushed-abandoned.md, diag-sota-research.md) + settings verified live this session.

---

## 1. STATE OF PLAY (honest)

VM and HOME are **~90% the same harness on disk and ~0% the same at runtime.** VERIFIED: the on-disk harness is already present and byte-comparable on the VM — `~/.agents/harness/dispatcher.py` (28,962 B), `~/.claude/hooks/semantic-router/route.py` (16,149 B), the local `_dispatch`, `no-force-push`, `estate-deny-guard`, `selection-events`, `profile-capture`, `local-tui-reminder` scripts, `statusline-command.sh`, and `install.py` **all exist on the VM and every path home's hooks reference resolves here** (checked file-by-file). Command sets match (74/74). The ENTIRE drift is one file: **VM `~/.claude/settings.json` is a 758-byte stub** (permissions + model `claude-opus-5` + sandbox) with **no `env`, no `hooks`, no `statusLine`, no `skillListingBudgetFraction`, no `deniedMcpServers`**, while **HOME's is 26,038 B** carrying all of them. So the VM loads a full 418-skill catalog and a large MCP fleet unbudgeted every turn, and none of the anti-drift / anti-usage machinery (router, dispatcher replay, output caps, tool-schema deferral) ever fires.

**The single biggest problem is that runtime blindness compounds a git-safety hole:** the harness that would protect and checkpoint work is dormant (context rot eats usage) AND the VM's canonical checkout `~/source/agent-skills-toolchain/.git` is **empty/not a git repo**, while the real live vault `~/.agents` carries **163 uncommitted files** (the new azure-*/biomni-local/exa-search/zai-lanes/voice-cloning-sota skills, edited AGENTS.md/agents.json) with **zero recovery path if the VM is lost** — plus a genuinely committed-but-unpushed branch (`wip/harness-additions-2026-08-28`, 2 harness-design commits, no PR). That is the owner's exact "committed stuff never pushed, work abandoned" fear, live, today.

---

## 2. PRIORITIZED FIX PLAN (ordered; nothing runs until owner approves)

Legend: **[VM]/[HOME]/[BOTH]** = which machine · **[ME]/[PEER]/[COORDINATE]** = owner (two sessions active). "Verify" is the no-silent-regression proof.

### P0 — Save at-risk work FIRST (before any settings/wiring touches these trees)
Grounds: diag-unpushed §"Ranked risk". Do this before P1 because P1 restarts sessions and the wiring lane will touch `~/.agents`.

1. **Commit the 163 dirty files in VM `~/.agents`** — in reviewable chunks, not one mega-commit. **[VM] [ME]**
   - Why: largest at-risk work found; unversioned new skills + control files; a VM wipe loses them outright.
   - Mechanism: on `~/.agents` (HEAD = `live-capture/2026-09-02`, 0/0 vs origin): stage in groups — (a) new skills `git add skills/azure-* skills/biomni-local skills/delegate-primitive skills/exa-search skills/zai-lanes skills/voice-cloning-sota`, (b) foundry edits, (c) control files `AGENTS.md agents.json`, (d) triage the scratch/report files (`GRILL-DECISIONS_*`, `HARNESS-COMMIT-PLAN_*`, `PROGRAM-REPORT_*`) — likely `.gitignore` not commit. Commit each group, then **push** `live-capture/2026-09-02`.
   - Risk: parallel-agent worktree contamination (MEMORY.md "scoped git add is not enough — commit takes whole INDEX"). Mitigation: use `git commit -- <paths>` per group OR ensure no peer writes `~/.agents` during the commit (COORDINATE first).
   - Verify: `git status --porcelain` count drops to only intentionally-ignored files; `git rev-list --left-right --count origin/live-capture/2026-09-02...live-capture/2026-09-02` shows `0 <n>` then `0 0` after push; `git ls-remote origin live-capture/2026-09-02` SHA == local.

2. **Push `wip/harness-additions-2026-08-28` and open a PR.** **[VM or HOME] [COORDINATE]**
   - Why: 2 committed harness-design docs (`f9fa6582`, `c01f45cb`), pushed nowhere, no PR — the cheapest recoverable item and directly on-topic for wiring the harness. Present identically on both machines.
   - Mechanism: `git push origin wip/harness-additions-2026-08-28`; `gh pr create` (gh not on VM — use API/PR from HOME, or install gh). Confirm no divergence first: whichever machine pushes, the other must not have extra local commits on that branch.
   - Verify: `git ls-remote origin wip/harness-additions-2026-08-28` == local HEAD; PR URL exists and is open.

3. **Owner checks HOME `~/source/agent-skills-toolchain/.git/index.lock`** (0-byte, 2026-09-22 22:22). **[HOME] [COORDINATE — owner action]**
   - Why: a stale lock silently blocks every commit/checkout on HOME's main checkout; may be why HOME work isn't landing.
   - Mechanism: on HOME confirm no live git process, then delete the lock. (Cannot verify staleness over rclone — needs a HOME shell/owner.)
   - Verify: `git -C ~/source/agent-skills-toolchain status` runs clean; a trivial `git commit --allow-empty` succeeds then is reset.

### P1 — Context-rot fix + harness wiring (owner's #1 pain; the settings.json port) **[VM] [ME]**
Grounds: diag-context-rot (all 3 layers), diag-sota (nuances). This is a PORT, not a redesign. All dependency scripts verified present on VM.

4. **Back up VM settings.json, then merge HOME's context-rot layers into it.** **[VM] [ME]**
   - What: add `"skillListingBudgetFraction"`, the full `env` block, `deniedMcpServers`, `hooks`, and `statusLine` from `home-settings.json` — **preserving** VM's own `permissions.additionalDirectories` (C:\, C:\suite\, C:\suite\payload) and `model`.
   - Why (root cause, owner's MEMORY.md): "naive-sessions = skills-context-budget overflow; fix = curated daily skills + vault lazy via router" + "MCP tool count is itself context-bloat."
   - Layer order (biggest win first):
     - **L1 skill-listing cap** — `skillListingBudgetFraction`. **HONEST FLAG (diag-sota, context-police):** default is 0.01; HOME's **0.04 is 4× default and a documented anti-pattern** (pays a big catalog bill every turn). **Do NOT copy 0.04 blindly.** Measure with `/context-budget` first; prefer **0.01** + a `disable-model-invocation` curation sweep of episodic skills, escalate only if the listing is still starved.
     - **L2 env caps** — `ENABLE_TOOL_SEARCH`, `MAX_MCP_OUTPUT_TOKENS:50000`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS:64000`, `BASH_MAX_OUTPUT_LENGTH:150000`, `ECC_CONTEXT_MONITOR_COST_WARNINGS:0`, `ECC_GATEGUARD:off`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:90`, MCP timeouts, `CLAUDE_CODE_USE_POWERSHELL_TOOL:1`, etc. **HARDEN (diag-sota #39279/#40314):** HOME uses `auto:5`, but `auto:N` scales with the window and **under-defers on a 1M Opus session**, and Tool Search **never defers HTTP MCP** (cloud-hub/social-hub/search-hub/zai load schemas upfront — measured 120K/60% in one report). Set `ENABLE_TOOL_SEARCH:"true"` (force) **and** pair with per-project MCP curation (P2) — deferral alone will not gate the HTTP fleet.
   - Risk: malformed JSON breaks startup (back up first, `python -m json.tool` validate). Adopting 0.04/auto:5 verbatim would re-import bloat — mitigated above.
   - Verify: `python -m json.tool settings.json` passes; restart; `/context-budget --verbose` shows skill listing capped and fixed overhead down vs a pre-change baseline capture; **capability check** — every command/skill still invocable (spot-check 3-4).

5. **Wire the `hooks` + `statusLine` blocks (same edit as #4).** **[VM] [ME]**
   - Why: "vault lazy via router" (route.py on UserPromptSubmit) + dispatcher SessionStart replay / goal re-injection / PreCompact checkpoint / Stop capture — the anti-drift + anti-usage-waste behaviors. All 7 referenced scripts + dispatcher + router + `statusline-command.sh` VERIFIED present on VM.
   - Risk: a hook that errors could nag or slow startup — but harness rule is fail-open (any hook error exits 0). Keep timeouts as home has them (2–35s).
   - Verify: after restart, SessionStart/PreToolUse hooks fire (transcript `hook_success` durationMs, per metaswarm latency note); statusline renders `5h:N%`/`wk:N%`; trigger a prompt and confirm router injects context; force a Stop and confirm the event-ledger got a turn entry.

### P2 — MCP fleet curation (the "MCP fix", pairs with L2 deferral) **[VM] [COORDINATE]**
6. **Reconcile `deniedMcpServers` + per-project disable for the ~80-server fleet.** **[VM] [COORDINATE]**
   - Why: ~30+ servers failing this session (CONNECTION_CLOSED/ECONNREFUSED/AUTH); each connected server is session-start schema tax; HTTP servers aren't deferred by Tool Search (P1). diag-context-rot L3 + MEMORY.md "MCP no-drift architecture", "FIX-MCP-CURATION.py --apply pending".
   - Mechanism: start from HOME's deny list (claude-code-mcp, markitdown, rdkit, serena, gitlab, meta-tool) but **do NOT adopt verbatim** — reconcile against what the VM actually uses; use the `/mcp-fleet-curation` skill + `scripts/reap_orphan_mcp.ps1` / `mcp_ram_audit.ps1` / `apply-mcp-health-fixes.ps1`. Also restore basic-memory (daemon DOWN on VM — `~/.basic-memory` config + memory.db absent though D: vault exists) OR read `homeD:/basic-memory` markdown directly for recall in the interim.
   - Risk: denying a server the VM needs = capability regression. Mitigation: per-project `.mcp-disabled-defaults.json` over global deny; MEMORY.md warns "never destroy MCP enabled/disabled state" and the "reap needle collision" (substring match killed a live server) — curate by exact serverName, not substring.
   - Verify: after curation, `/context-budget` MCP-schema term drops; every previously-working MCP surface the VM relies on still connects (enumerate before/after); basic-memory `search_notes` returns or the rclone-read fallback is documented.

### P3 — PR/worktree triage (stop invisible abandonment) **[BOTH] [COORDINATE]**
7. **One triage pass over the 39 open PRs + 7 HOME worktrees.** **[BOTH] [PEER can own while ME does P1]**
   - Why: 13 stale draft `cursor/imp-00xx-*` PRs (Sep 6-8) + substantive #310/#311/#312/#314 (21 days) + #352 confirmed closed-unmerged — pushed and safe but undecided; 2 HOME worktrees on detached HEAD (`ast-docspr`, `search-hub-pr310`) can orphan commits.
   - Mechanism: per PR → merge / close / label `intentionally-parked`. `git -C <worktree> status` on each of the 7 HOME worktrees (needs HOME shell). Check whether #352's byte-identical-AGENTS.md fix landed elsewhere before treating it as dropped.
   - Verify: 0 open PRs without an explicit disposition; no detached-HEAD worktree holds an unreferenced commit (`git branch --contains`).

---

## 3. DURABLE SKILL DESIGN — `harness-sync`

**Name:** `harness-sync` (aliases: "reconcile a second machine", "bootstrap harness on this box", "sync VM and home").
**Description:** Idempotently bootstraps or reconciles a machine's Claude Code harness from `Prekzursil/agent-skills-toolchain`, then doctors it against the peer machine over rclone and gates on context budget. One command replaces the ad-hoc port this session did by hand.
**Lives in repo:** `skills/harness-sync/SKILL.md` (+ `skills/harness-sync/scripts/`), deployed to `~/.agents/skills` and `~/.claude/skills` by the existing `scripts/deploy-skills-daily.py`. Backed by two repo scripts built on the existing seed `~/.agents/harness/install.py`: `scripts/harness_apply.py` and `scripts/harness_doctor.py`.
**Invocation:** `/harness-sync apply` (wire this box), `/harness-sync doctor` (diff vs peer), `/harness-sync doctor --peer homeC:` (rclone cross-check). Also runnable as the Skill tool.

**What it automates (grounded in what this session did by hand):**
- **Machine-parameterized settings.** Keep a tracked `settings.template.json` in the repo; `harness_apply.py` merges it into the live `~/.claude/settings.json`, **preserving per-machine `permissions.additionalDirectories` + `model`**, and validates JSON before writing (P1 risk).
- **Dependency preflight.** Assert every hook-referenced script resolves (this session's file-by-file check, automated), python/git/rclone present, statusline script present. Refuse to wire hooks whose script is missing (prevents a broken hook).
- **Context-budget gate.** Run `/context-budget` (or `ci/check_skill_context_budget.py`) before AND after; refuse to raise `skillListingBudgetFraction` above 0.01 without an explicit `--allow-high-fraction` flag (encodes the diag-sota anti-pattern warning).
- **Two-machine doctor.** Over rclone `homeC:`/`homeD:`, diff settings.json keys, skill-tree membership, and MCP enabled/denied lists; emit 3 exit codes (0 coherent / 1 drift-repairable / 2 pending work) like the bash-bastion `checkfilestatus.sh` pattern, but using files the owner already owns.
- **Wraps existing skills** rather than reinventing: delegates skill-tree diffs to `skill-tree-reconcile`, MCP curation to `mcp-fleet-curation`.

**Inputs:** `mode` (apply|doctor), `--peer <rclone remote>` (default none), `--allow-high-fraction`, `--dry-run` (default for apply until owner confirms).
**Verification gate (must pass before it reports success):** settings.json validates; all wired hook scripts exist; `/context-budget` fixed-overhead not higher than pre-run baseline; no capability removed (command/skill count not decreased); doctor exit code recorded. This is **simpler and faster** than the transcript's hand-port: one `apply` instead of a manual merge + path audit + restart-and-hope.
**This is the artifact committed+pushed to `Prekzursil/agent-skills-toolchain`.**

---

## 4. ANTI-ABANDONMENT MECHANISM — `push-guard` (Stop hook + daily sweep + command)

Grounds: diag-sota "no unpushed-commit / stale-draft-PR guard exists even on wired HOME" (GitWell/pendector fill this externally); the owner's named failure. Three layers so nothing slips:

1. **Stop / SubagentStop harness module — read-only nag.** Add `~/.agents/harness/modules/push_guard.py`, invoked by the already-wired `dispatcher.py` on `Stop`/`SubagentStop` (authored via the `harness-module-authoring` skill). On each stop it checks the repos it touched this session and **injects `additionalContext` (exit 0, never blocks, never auto-pushes — respects `no-force-push`)** when it finds: (a) a local branch **ahead of its upstream**, (b) a branch with **no upstream**, (c) **committed-but-unpushed** commits, (d) a dirty tree above a threshold, (e) WIP-marker commits. This catches exactly `wip/harness-additions-2026-08-28`.
2. **Daily scheduled sweep — cross-machine.** A `/push-audit` command run via `/loop 1d` or a `CronCreate` routine that, over rclone `homeC:`, enumerates **both** machines' branches ahead-of-origin + **stale draft PRs** (via gh/GitHub API, age > N days) and writes a short report + basic-memory note. This catches the 13 stale `cursor/imp-*` drafts and #352-class closes.
3. **`/push-audit` on demand** — same engine, callable any time; the reusable core `harness_doctor.py` shares its git-state reader.

**Why read-only:** MEMORY.md + estate-deny-guard forbid auto-push/force-push; the guard nags and reports, the human/owner pushes. **It must catch:** commits that never reach origin (layers 1+2) AND PRs that die (layer 2). **Verify the guard itself** (defect-as-fixture lesson): seed a throwaway branch 1-commit-ahead with no upstream → guard must flag it; a clean pushed branch → guard must stay silent. A guard that never fires is worthless; prove both states.

---

## 5. NO-REGRESSION CONTRACT (every implementation-wave change must pass all)

1. **Verify command green** — the change's own proof runs and passes (settings.json → `python -m json.tool` + `/context-budget`; skill → its verification gate; hook → fires with `hook_success` in transcript).
2. **Capability not reduced** — command count, skill count, and connected-MCP surfaces the box relies on are **≥** the pre-change baseline (capture baseline first). No skill/hook/MCP silently dropped. `skillListingBudgetFraction` not raised above 0.01 without explicit sign-off.
3. **Committed AND pushed** — no change is "done" until `git ls-remote` shows the commit on origin. Unpushed = not done (the whole point of §4).
4. **Recorded** — a basic-memory note + event-ledger entry: what changed, why, verify output, provenance `disk-verified` not `agent-claimed` (fail-closed verification doctrine).
5. **Reversible** — settings.json backed up before edit; each step has a named rollback.
6. **Two-machine coherent** — after the change, `harness-sync doctor --peer homeC:` exit code recorded (0 or a known/accepted 1).

---

## 6. COORDINATION (this VM session = ME; peer session = PEER)

Two sessions are active across the two machines; avoid thrash by **partitioning by machine + tree, single-writer per tree:**
- **ME (VM):** owns P0#1 (`~/.agents` commit — VM is where the 163 dirty files live), P1 (#4/#5 settings port + wiring — VM-local), P2 (VM MCP curation). All VM-local, no HOME writes.
- **PEER (HOME):** owns P0#3 (index.lock — HOME-local), P3 HOME-worktree `git status` sweep, and authoring the durable `harness-sync` skill + `push-guard` module **in the toolchain repo on HOME** (HOME has the healthy checkout; VM's is empty — building repo artifacts on VM would need a re-clone first).
- **Shared/handshake items:** P0#2 (push `wip/harness-additions` + PR) and P3 PR triage — **exactly one machine pushes each branch**; announce the branch before pushing (agent-mail/mingle if up, else the owner relays). Never both push the same ref (`git pull --rebase` then push on conflict).
- **Do not both edit `settings.json`** — that file is VM-local for the VM's copy; HOME keeps its own. The **template** in the repo is edited by PEER (skill author) and pulled by ME.
- **Serialize the repo:** commits to `agent-skills-toolchain` go through one machine at a time; the other rebases.

---

## 7. OPEN QUESTIONS (owner decision before implementation)

1. **`~/source/agent-skills-toolchain/.git` on VM is empty.** Re-clone into that path, `git init`+fetch, or **stop treating it as canonical and point all tooling at `~/.agents`** (the healthy clone)? This ambiguity is a plausible root cause of "harness not wired on VM." (diag-unpushed CRITICAL)
2. **`skillListingBudgetFraction`: 0.01 (default, safe) or 0.04 (HOME's value, 4× default anti-pattern)?** I recommend 0.01 + curation sweep, measure, escalate only if starved. Owner's call. (diag-sota HONEST FLAG)
3. **`ENABLE_TOOL_SEARCH`: force `"true"` (my rec, gates the HTTP fleet on 1M Opus) or keep HOME's `auto:5`?** (diag-sota #39279/#40314)
4. **The 13 stale `cursor/imp-00xx-*` draft PRs + #352:** still wanted, or bulk-close as parked? Needs owner intent — content not read this wave.
5. **basic-memory on VM:** stand up the daemon + rebuild `~/.basic-memory`/memory.db locally, or rely on rclone-reading `homeD:/basic-memory` for recall? (diag-sota)
6. **CLI version pin** — is the VM on 2.1.220+? issue #90113 (tool-search token inflation → false "context limit") means forcing tool-search on a buggy build can backfire; verify with `/doctor` before enabling. (diag-sota)
7. **Scheduling** for the daily push-audit: `/loop 1d` in a long-lived session, or a `CronCreate` cloud routine (survives session exit)?

---
*Provenance: all runtime facts (settings sizes, script presence, git state) VERIFIED this session by direct read; SOTA nuances and HOME dirty-state are from the cited diagnosis artifacts (HOME read ref-level only over rclone — no HOME shell). Nothing was changed.*

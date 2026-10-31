---
title: council-2
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/council-2
---

## Security + Concurrency lens — Phase-3 consolidation design verdict

I'm the security/concurrency voice. My through-line: **every mutation to shared, multi-session state or to a secret-bearing tree is a hazard until proven otherwise.** Two live scars govern my calls — the `mcp_doctor reap` incident (a machine-wide destructive op killed *sibling sessions'* live MCP children) and the harness session-scoping bug (shared-cwd state intercalated sessions). Both say the same thing: **destructive ops on shared state while sessions run are forbidden; the safe default is advisory SHADOW + fail-open**, exactly what AGENTS.md §6 already mandates.

---

### Thread 1 — MCP single-source-of-truth (enforced?)
**Recommend:** Versioned canonical JSON in `agent-skills-toolchain` is the *sole editable* source; `~/.mcp.json` and the user-scope block are **rendered one-way (generate, never merge)**. Secrets stay `${VAR}` refs — a literal token in canonical is a commit-to-git leak. Extend the `config_drift` baseline to hash **`enabledPlugins` + plugin-bridge servers**, not just `mcpServers`/`disabledMcpServers`.

**DISAGREE with the naive "just prune user scope."** codacy/deepsource resurface via `plugin:local-mcp-bridge:*` at **user scope** (27/26 occurrences in `~/.claude.json`) — the drop operated on the wrong layer entirely. This is a **supply-chain concern**, not cosmetics: plugin-provided servers execute code at user scope, enabled-by-default, outside every watched surface. The cure is `plugin disable … --scope user` + a widened baseline, not editing `.mcp.json`.

**Concurrency guardrail:** any prune of `~/.claude.json` clobbers sibling sessions on their next exit. The promote/prune step MUST refuse to run if any `claude` process is live (a process-check fail-safe in the script), or write to a launch-time `--mcp-config`/project `.mcp.json` that Claude reads at startup, avoiding the `~/.claude.json` write-race entirely.

### Thread 2 — MCP user-scope + one-folder centralization
**Recommend:** User scope is correct; it kills the `D:/Research/.mcp.json` walk-up copy. **Delete `D:/Research/.mcp.json` and the two `D:\*\hooks\promote-*.ps1` clones** — they carry pre-reconcile bugs (old playwright pkg, old Kaggle env) and are hand-editable drift/config-injection surfaces on a drive Claude can't reach canonically. Keep `D:\Backups\config\*` as timestamped backups **read-only, never loaded as live config**.

**DISAGREE with treating the HTTP-gateway migration as in-scope.** The gateway pattern *is* the correct long-term fix for the N×M process explosion and the singleton-conflict class (#40220, the reap scar) — MEDIUM confidence (~70%) it's the right end-state. But a full stdio→gateway migration is a large, per-server effort that should **not gate Phase-3**. Adopt it only for the already-gatewayed heavy servers (agent-mail/cloud-hub/search-hub — proven), leave lightweight stdio alone.

### Thread 3 — config/skill/tool/hook centralization
**Recommend:** Repo-as-SSOT (`ci/harness`) + `install.py --deploy` (copy-based, already built). The **allowlist is the single most security-critical decision in the whole program**: `.claude` is 34.7 GB of ~90% runtime state and **live secrets** (`auth.json`, `.credentials.json`, `~/.codex/secrets/`). This MUST be **default-deny allowlist, never a denylist** — a denylist eventually leaks a credential. gitleaks pre-commit as the backstop.

**Non-negotiable, currently unaddressed:** `~/.agents/harness` has **never been a git repo**, so it has never been gitleaks-scanned. Before its first commit, scan the entire tree for embedded tokens/keys — a first-time enshrine of a never-scanned canonical tree is a classic leak vector.

**DISAGREE with the research headline (adopt chezmoi).** chezmoi is **over-engineering here and mildly counter-goal**: it introduces a *new* deploy engine + age keyring + migration on top of an already-fragmented multi-source state — i.e. it adds a source of truth when the goal is to remove them. You already get copy-based deploy from `install.py`. **Adopt chezmoi's lessons, not the tool:** strict allowlist, gitignore-first, `.gitattributes` (`*.sh eol=lf`, `*.ps1 eol=crlf` — the CRLF-breaks-WSL scar), secrets never in git. The copy-over-symlink insight is genuinely load-bearing on Windows (a committed symlink degrades to a plaintext file elsewhere — a correctness *and* path-leak footgun) — and `install.py` already copies, so we're safe by default.

**On secrets-at-rest:** if anything must be encrypted, prefer **age/SOPS over git-crypt** (git-crypt leaks file sizes, has no clean key rotation, and its smudge filter can leak on partial checkouts). But the stronger posture is **don't commit secrets even encrypted** — gitignore + `${VAR}`/manager-reference beats ciphertext-in-history, which is permanent if the key ever leaks.

### Thread 4 — cleanup-enforcement hook
**Recommend:** `artifact_hygiene` Stop hook, TIER_HEURISTIC, **SHADOW, advisory-only, NEVER deletes.** Reuse the mutation ledger (paths written this session) ∩ `git status --porcelain` untracked ∩ not-gitignored ∩ not-scratchpad → inject a list.

**DISAGREE hard with any auto-sweep/auto-delete.** Deletion is an irreversible §6/§9 op, and `rules/common/windows-shell.md` records **two data-loss scars** (`New-Item -Force` truncation; MSYS `/sdcard` save-wipe). **CUT** the SessionEnd scratchpad sweep unless it is trivially safe — scoped to the scratchpad dir with an absolute-path guard, never the repo, never a device path. The value here is precise advisory surfacing (near-free from the ledger), not mechanical cleanup.

### Thread 5 — stale-branch reconciliation
**Recommend:** `stale_branch` advisory gate at SessionStart, `merge-base --is-ancestor` detection (handles squash/rebase), one-time dedup. **NEVER auto-deletes** (`git branch -D` is §9-gated).

**Concurrency guardrail is the whole point:** the inventory flags branches with **today's mtime owned by concurrent sessions** (`chore/enshrine-runtime-config`, `gem-hunt-wave-b`, `feat/codex-fleet-github-wave2`). The gate MUST exclude recent-mtime branches and never reason about another session's checked-out branch — this is the reap-scar lesson applied to git. **CUT any bulk prune:** `battlecats-toolkit` (+142/+29/+6), `ToolUniverse` (+34), and uncommitted Reframe sidecar features are unpushed work; a naive `git branch -D --merged`-style sweep is a **data-loss event**. Deletion stays a human decision per surfaced list.

### Thread 6 — doc-reconciliation + enforcement hook
**Recommend:** `kb_supersede` (near-dup via existing `recall_index.py`, injects the §8 `superseded_by:`/`valid_as_of:` reminder) — SHADOW. Low security risk; useful.

**DISAGREE with / CUT the `doc_drift` AST-fingerprint code-binding.** It's the wrong tool for *this* corpus: the scattered docs are decision/plan/audit markdown, not code-bound API docs. The research itself flags it over-fires until tree-sitter coverage lands. Building AST binding for harness-decision-doc reconciliation is over-engineering; ship `kb_supersede` only.

### Thread 7 — scattered-harness-doc reconciliation
**Recommend:** One-time human-curated archival with a supersede **INDEX.md** (reversible pointers), **not deletion**. Fix Problem #1 first: the SSOT repo's own `CLAUDE.md` ships the stale AgentBridge/`get_budget` claim — **rewrite before push**; a source-of-truth carrying the worst stale governance claim poisons everything downstream.

**Security-specific:** several scattered docs reference **live infra and secrets** (the hygiene audit found live payment keys and a live momentstudio.ro VPS). **gitleaks-scan every doc before committing it into the versioned repo** — including the 293 KB toolkit-gap-analysis and the audit bundles. Don't just move files; scan them. This is a genuine leak vector nobody else's lens will catch.

### Thread 8 — harness-change-must-be-documented+committed gate
**Recommend:** `uncommitted_change` Stop hook, **inject not block** (§6 — committing is the owner's call). But the gate is a symptom-patch; the real fix is **thread 9's live↔repo parity check + an atomic deploy step**. The headline finding proves it: task-8 is committed-but-undeployed → three-way split (HEAD ≠ working-tree ≠ live) *while implementing single-source-of-truth*.

**Concurrency guardrail:** deploying `modules.py`/`install.py` to live `~/.agents/harness` **while sessions run** risks intercalation (the session-scoping scar). Deploy must be **atomic (temp-dir + rename) and session-aware** — never hot-swap harness code under running sessions. Verify the per-session isolation fix is in the deployed tree before enabling any deploy automation.

### Thread 9 — harness-works-perfectly verification
**Recommend:** Add the **deploy-parity check** (hash live `~/.agents/harness` tree vs `ci/harness`) — this is the missing verification silently failing *right now*, and the highest-value single item in the program. Wire `install.py --check` to a SessionStart/periodic hook so drift is caught without a human running it. Redact any secret/path in its output.

**Blocking sub-task from my lens:** the `config_drift` gate depends on a `ConfigChange` event that `registration.py` itself documents as *"never fired by a host that does not emit it."* That's a **LOW-confidence load-bearing assumption (§1b) — verify empirically, don't assume.** If Claude Code doesn't emit it, thread-1's only runtime drift sentinel is **permanently inert** (mechanism present, zero effect). Provide a SessionStart-poll + periodic fallback trigger regardless.

---

## Top risks (ranked, security/concurrency)

1. **CRITICAL — secret leak on enshrine.** Tracking any part of the 34.7 GB `.claude` or the never-before-git `~/.agents/harness` via denylist/whole-dir leaks `auth.json`, `.credentials.json`, `secrets/`. → Default-deny allowlist + gitleaks pre-commit + first-time full-tree scan of `~/.agents/harness`. Ties to §9/§9b (a leaked secret is compromised regardless of exposure duration — rotate, don't just delete).
2. **HIGH — multi-session clobber / destructive shared-state op.** Pruning `~/.claude.json` or deploying harness while sessions are live clobbers siblings and intercalates (reap + session-scoping scars). → Live-process guard on all Claude-closed batch ops; atomic session-aware deploy; advisory-SHADOW for everything else.
3. **HIGH — plugin-bridge supply chain.** codacy/deepsource execute at user scope outside the drift baseline; the drop mechanism watches the wrong layer. → `plugin disable --scope user` + widen baseline to `enabledPlugins`.
4. **HIGH — data-loss on bulk branch/artifact prune.** +142/+34 unpushed commits and uncommitted feature work destroyed by a naive sweep. → Advisory-only; recent-mtime exclusion; deletion stays human.
5. **MEDIUM — thread-1 mechanism with zero effect.** Unverified `ConfigChange` trigger → drift sentinel never runs. → Verify + fallback trigger.
6. **MEDIUM — SSOT ships stale governance.** The reconcile repo's `CLAUDE.md` (AgentBridge) is the worst stale claim in the workspace, inside the doc meant to end drift. → Rewrite before push.

## What I'd cut as over-engineering
- **chezmoi + age keyring adoption** — use existing repo + `install.py`; adopt the *lessons* (allowlist, gitignore-first, `.gitattributes`, secrets-out-of-git), not the tool. Adding a deploy engine is counter-goal.
- **`doc_drift` AST/tree-sitter code-binding** — wrong tool for decision-doc reconciliation; ship `kb_supersede` only.
- **Full stdio→gateway MCP migration** — right end-state, wrong sprint; limit to already-gatewayed heavy servers.
- **Auto-delete/auto-sweep in cleanup + branch threads** — advisory-only; deletion is a §9-gated human op with two data-loss scars behind it.
- **SessionEnd scratchpad sweep** — cut unless trivially safe (scratchpad-only, absolute-path-guarded).
- **Promoting any new gate past SHADOW in Phase-3** — the anti-nag ladder is correct; ENFORCE only after burn-in with a recorded promotion/fitness plan. Observation before enforcement is the right security posture.

**Net:** the design is SOTA and I agree with the repo-as-SSOT / generate-don't-sync / SHADOW-first spine. My lens changes four things: (1) allowlist + gitleaks-scan the never-git harness tree before it *ever* touches history; (2) live-process guard every Claude-closed destructive op and make harness deploy atomic + session-aware; (3) fix the drop at the plugin/user-scope layer and widen the drift baseline there; (4) keep cleanup/branch/doc enforcement strictly advisory — deletion is human, always.
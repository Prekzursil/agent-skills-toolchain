# Session changelog — cc-cc cyber-clean + system fixes (2026-10-30/31)

Preserved here because the push/PR to `agent-skills-toolchain` is blocked (see "Blockers").
All changes are LIVE in the deployed home dirs; originals backed up under
`~/.claude/_config-backups/cc-cc-fix_20261031_005111/` and `sysfix_20261030_212632/`.

## A. cc-cc cyber-clean profile (the main request)
Goal: `cc-cc` (Claude Code on Anthropic models) runs the full harness WITHOUT the
offensive-estate context that trips Anthropic's [cyber] classifier on benign work.
GLM / cyberstrike / zcode / `cc-glm` keep the full harness unchanged. Mechanism is
the harness's own `_CLEAN_PROFILES` gate (`CC_ACTIVE_PROFILE=claude`).

Files changed (deployed):
1. `~/.agents/harness/modules.py` — `RecallModule.run()`: added
   `if _ownerops_suppressed(): return HookResult.success()` after the spool-flush,
   so the basic-memory vault digest / recall (recall-index.json = 371 cyber hits)
   is NOT injected under the clean profile. Patch: `modules.py.RecallModule-gate.patch`.
   (OwnerOpsAuthorizationModule + EnforcementScaffoldModule were already gated.)
2. `~/.local/bin/cc-cc.ps1` — added `CC_ACTIVE_PROFILE=claude` (already), `RECALL_GATE=off`
   (silences the recall-gate hook), and `--append-system-prompt-file AGENTS.claude-clean.md`.
3. `~/.claude/profiles/claude-session.json` — added `skillOverrides` turning OFF 10
   offensive skills (hexstrike-ai-*, burp-mcp, malware-analysis-triage, jailbreak,
   cyberstrike, estate-offensive-doctrine, gcp-compute-foothold, credential-forge).
4. `~/.claude/profiles/AGENTS.claude-clean.md` — NEW. Auto-derived from `~/AGENTS.md`
   with 8 cyber/estate sections removed (49 of 57 kept). Original `~/AGENTS.md`
   UNTOUCHED (still used by glm/cyberstrike). Regenerate: `scratchpad/mkclean_agents.py`.

Kept on purpose (user instruction): McpHub, GLM plan plugins, basic-memory (as a tool).

## B. Launcher -> model map (verified)
- `claude` (bare) = Claude Code on GLM (settings.json ANTHROPIC_BASE_URL -> z.ai)
- `cc-cc` = Claude Code on Anthropic (OAuth; strips GLM env)
- `cc-glm` = Claude Code on GLM (explicit)
- `claude-api` = Claude Code on Anthropic via API key (pay-per-token)
- `claude-free` = Claude Code on a local GLM free-lane shim (own .claude-free config dir)
- `claude-swap` = Anthropic multi-account rotator (NOT a GLM bridge)
- "both Claude+GLM in one TUI" = the `unified` profile, marked DEFERRED in DECISIONS.md (never built)

## C. System fixes (same session)
- Crash capture: CrashDumpEnabled 2->3 (minidump), AlwaysKeepMemoryDump=1, AutoReboot=0.
- C: pagefile capped 8192/32768 -> 4096/4096 fixed (reboot to apply).
- Freed C: 18.8 GB -> ~101 GB (deleted 4 orphaned WSL swap.vhdx; Windows.old auto-removed).
- Storage Sense cadence set to weekly (01=1, 2048=7, 04=1).
- Disabled 3 failing CyberLink CLToast tasks.
- semgrep MCP (31119) restored + durable task SemgrepMcp-HTTP-31119.
- biomni MCP (WSL, 7870) restored (~/Biomni/biomni_mcp_server.py, conda biomni_e1) +
  durable task BiomniMcp-HTTP-7870. Guard scripts in ~/.local/opt/hidden-launchers/.
- Status line: builtin epoch, cache TTLs 8/10 -> 30s, refreshInterval 30 -> 60.

## D. How to land this in the repo (once blockers clear)
Repo layout mirrors deployed: `.agents/harness/modules.py`, and cc-profiles under
`harness/cc-profiles/` (bin/cc-cc.ps1, claude-session.json). Apply the modules.py patch
to the repo copy, copy the 3 small files to `harness/cc-profiles/`, commit on a branch
off a clean base (worktree), push, PR. Keep out of the commit: the ~4,655-line
working-tree drift already present on `fix/live-harness-drift-20261021`.

## Blockers (why not pushed)
1. `gh`/git auth: `GH_TOKEN` is invalid -> cannot push or open a PR.
2. git-crypt: `git worktree add` aborts on `tools/mcp/cloud-hub/accounts.json`
   (smudge filter needs the git-crypt key in the new worktree).
3. cc-profiles files are uncommitted drift at HEAD, not tracked content.
Not worked around: no re-auth with unknown creds, no git-crypt bypass, no sweeping
the drift into a commit.

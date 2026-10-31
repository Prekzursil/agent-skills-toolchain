---
title: CC-PROFILES
type: note
permalink: dqverify-repo-20261013/docs/cc-profiles
---

# cc-profiles - dual/triple provider profile system (2026-10-24)

Entry points in ~/.local/bin: cc-use <glm|claude|unified>, cc-glm, cc-cc, cc-status (.ps1 + .cmd).
Engine: ~/.claude/profiles/cc-profiles.psm1 (key-scoped merge; backup -> mutate -> verify -> masked diff -> restore-on-exception).
Sentinel: ~/.claude/profiles/state/cc-active-profile (missing = glm = fail-open).
Failover guard: SKIP:cc-guard block in ~/.agents/scripts/zai_key_failover.py suppresses mutation while sentinel == claude.
Claude profile: subscription OAuth, clean-mcp.json (19 servers) via --strict-mcp-config, 28 denies, skills_hide hexstrike-ai*/burp-mcp/malware-analysis-triage.
Unified profile: local router D:/opt/cc-router/router.mjs (:8377), glm-* -> z.ai rotation-fresh, claude-* -> api.anthropic.com via CC_ANTHROPIC_KEY (router-only; OAuth cannot ride a proxy). router-run.cmd health-gated, PID-file lifecycle.
Forensics: [cyber] refusals were input trips from deferred-MCP tool catalog (hexstrike x150, sliver x74) + 120k skill catalog; AGENTS.md/CLAUDE.md evidence-cleared and unmodified.
Rollback: cc-use glm, or premigration snapshot ~/.claude/profiles/backups/premigration-20261024-023146/.
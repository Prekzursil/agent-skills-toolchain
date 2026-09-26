---
title: Codex CLI max-power update 2026-09-07
type: decision
permalink: main/decisions/codex-cli-max-power-update-2026-09-07
tags:
- codex
- cli
- max-power
---

- [decision] Codex CLI updated on 07.09.2026 from `0.149.0-alpha.1` to released `0.153.4` via existing `codex update` → `npm install -g @openai/codex`. Canonical home remains `C:\\Users\\Prekzursil\\.codex`.
- [fact] Install path after update: npm shim `AppData\\Roaming\\npm\\codex.ps1` → vendor `codex.exe` 0.153.4. Disk-verified `codex --version`.
- [decision] MAX POWER enabled 29 optional/under-dev features via `codex features enable`. Left off Cloud/Mem0/Graphiti/proxy/budget/`code_mode_only`/removed flags. Did not bind :18765/:18812/:18317. Did not rotate credentials.
- [fact] Additive config (backup `config.toml.bak-max-power-20260907`): `shell_environment_policy.inherit=all`, `sandbox_permissions=[disk-full-read-access]`, `[sandbox_workspace_write].network_access=true`. Preserved `approval_policy=on-request` and `sandbox_mode=workspace-write`.
- [fact] Receipt: `C:\\Users\\Prekzursil\\Cowork\\output\\codex-cli-max-power_2026-09-07.md`. Restart Codex to pick up the new binary.
- relates_to [[Universal harness share]]
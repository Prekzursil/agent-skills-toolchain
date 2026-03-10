# Roadmap

## Now

- Keep `quality-gate-automation-architect` as the original live architecture skill.
- Promote an operations-first live skill wave for recurring Windows, WSL, VMware, and Codex recovery incidents.
- Keep the tool surfaces separate because MCP-native and browser-mediated work have different runtime and auth models.
- Keep derived summaries in references and docs without storing raw session artifacts.

## Current live ops wave

### `codex-runtime-recovery`

Diagnose split `CODEX_HOME`, missing-session incidents, `state_5.sqlite*` churn, and Windows-vs-WSL runtime drift.

### `codex-session-reunion`

Inventory and reunite session trees from Windows, WSL, backups, and VS Code mirrors.

### `long-copy-orchestrator`

Choose and observe the safest large-tree copy mechanism.

### `wsl-vmware-cutover`

Stage WSL-to-VMware migrations with D:-first backups and rollback checkpoints.

### `offline-linux-disk-surgery`

Repair, grow, and validate Linux guest disks offline.

### `windows-virtualization-conflict-triage`

Diagnose Hyper-V, VBS, VMware, and `vmrun` coexistence failures safely.

### `codex-vscode-host-routing`

Keep VS Code Codex launching from Windows by default while allowing explicit Linux-side exceptions.

### `reboot-safe-ops-continuation`

Capture machine state before forced reboots so long-running migrations can resume cleanly.

## Incubating skill backlog

The next backlog lives under `docs/incubating/skills/` and currently includes:

- Codex store auditing, cross-host visibility, CLI convergence, and config canonicalization
- WSL control-plane repair, disk-pressure recovery, and VMware guest-access recovery
- VHDX or VMDK migration, host topology audits, artifact staging, and performance benchmarking
- shell hygiene, Docker load slimming, and UNC or cross-filesystem diagnostics
- VM import normalization, session forensics, machine manifests, and incident blackboxes
- rescue-media, VMware disk expansion, guest-home restore, progress instrumentation, copy-mechanism selection, and hypervisor coexistence labs

## Next tool candidates

### `codex-as-mcp`

Incubate a clearly bounded MCP-native tool surface for exposing Codex workflows through an MCP-friendly interface without confusing it with skill packaging.

### `agentify-web-chatgpt-bridge`

Incubate a browser- or web-mediated tool surface for interacting with the ChatGPT web product without conflating it with MCP-native transport.

## Promotion criteria

Promote an incubation note into a live skill or tool only when:

- the workflow or integration has been used repeatedly
- the failure modes are understood
- the trigger or runtime boundary is clear enough that Codex can load or run the right thing reliably
- the artifact can be pressure-tested, not just described

## Non-goals

- stuffing multiple overlapping workflows into one giant skill
- hiding MCP-native and browser-mediated tooling under one generic bucket
- storing raw transcript or session exports in the repo
- adding scripts before a repeated deterministic task is proven

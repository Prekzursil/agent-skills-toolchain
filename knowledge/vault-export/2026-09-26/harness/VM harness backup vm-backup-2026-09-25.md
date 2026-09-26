---
title: VM harness backup vm-backup-2026-09-25
type: note
permalink: main/harness/vm-harness-backup-vm-backup-2026-09-25
tags:
- backup
- vm-lane
- offload-w2025
- rclone
- tailscale
- reconcile
---

Full divergent-lane backup from OFFLOAD-W2025 (disposable VM) to home desktop-a60s9gp, so nothing is lost if the VM dies.

## Observations
- [fact] Dest: `homeC:/Users/Prekzursil/Downloads/BACKUPS VM/vm-backup-2026-09-25/` — 36,117 objects / 3.527 GiB, transfer verified (rclone one-way check; only live-append files drifted, expected).
- [fact] Transport = rclone-serve-over-Tailscale (`homeC:`/`homeD:` remotes, home serves C:/D: on :2022/:2023). The `L:`/`M:` drive MOUNTS were NOT active but are unnecessary — `rclone copy homeC:` writes the exact path directly. Home had 126 GiB free.
- [fact] "tailgate" in owner's usage = this rclone link (per platform/vm-link/HOME-SETUP.md), NOT Taildrop; crown-jewels ALSO Taildropped as second transport.
- [decision] Bundle layout: claude/ (2.55 GiB, sessions+config+hooks+skills, NOT git-tracked anywhere), agents/ (678 MiB incl full state ledger+terminal.jsonl), basic-memory/{vault 720 md, control memory.db}, source-toolchain/ (84 MiB unique src), external-configs/, plugins-manifest/, SECRETS/ (quarantined), vm-crownjewels-2026-09-25.tar.gz (26 MB compressed .claude core).
- [decision] `.agents` committed+pushed on live-capture/2026-09-02: 52425d8f9 (vm-backup.ps1) after addc9a349 (new skills/hooks/repair scripts/knowledge/reports). 0 unpushed. Curated: EXCLUDED browser tokens, docs/probe-g7a-scratch junk, 21 microsoft-foundry deletions, 2 entra *token* docs (repo pre-commit-secret-guard is NAME-based).
- [fact] Repeatable tool: `vm-backup.ps1 -Date <YYYY-MM-DD>` (in .agents/scripts/ + bundle root). Dated, never overwrites; `-DryRun` prechecks sizes.
- [fact] VM disk is ONE ~150 GiB volume, only ~5.6 GiB free (C:/D: same volume) — so backup streams to home, no large local archive.
- [fact] WSL + VS Code are NOT installed on the VM; Biomni/~bin/WSL-Codex-sessions live on HOME. Windows `.codex` = config only (no sessions).

## Open loops (see bundle RECONCILE.md)
- [decision] basic-memory reconcile: VM 720 notes → home ~1126. MERGE only; a VM→home overwrite would destroy ~400 home notes (bisync_initialized=false).
- [decision] 4 LOCAL plugin marketplaces are not public-reinstallable and need separate backup: prekzursil-local-mcp, mattpocock-skills, agentbridge(RETIRED), zai-coding-plugins (in a transient npx cache = HIGH loss risk).
- [decision] Unrelated repos with uncommitted work NOT captured (outside harness scope): Personal-Finance-Management (58 files, mid package-rename), open-coscientist (1 file). Offer separate save.

Relates to [[Harness reconcile offload-w2025 2026-09-23]] and the [[compaction checkpoint]] flow. Completeness note: the workflow completeness-critic tripped Opus 4.8 [cyber] classifier; completeness done manually.

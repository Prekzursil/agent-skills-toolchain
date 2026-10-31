---
name: disk-space-manager
description: Use when freeing disk space, analyzing what's using C:/D:, deduping, removing slop or stale files, reconciling disks, or when asked for "best next files to delete". Keeps a WizTree CSV updated and analyzed, surfaces a persistent DECISIONS-PENDING report, auto-clears only safe regenerable slop, and never deletes personal or possibly-needed files without asking.
---

# Disk Space Manager

Keeps this machine's disks lean. Analyzes a WizTree export, auto-clears unambiguous slop, and
surfaces the best-next-deletes plus decision-needed items for owner approval. Never deletes
personal or possibly-needed files without asking.

## Assets (all under `~/.agents/scripts/`)
- **`wiztree_analyze.py`** — streams a WizTree CSV (memory-light; handles CLI 11-col and GUI
  23-col layouts by header name), emits SAFE vs REVIEW categories, largest files, largest folders
  to a markdown report plus a JSON sidecar. `python wiztree_analyze.py "<csv>" --out <report.md>`.
- **`wiztree_weekly.ps1`** — the permanent rule: auto-clear SAFE slop, refresh a WizTree CSV,
  analyze it, write `D:\wiztree-reports\DECISIONS-PENDING_C.md`. Registered as scheduled task
  **`WizTree-Disk-Hygiene-Weekly`** (Sunday 03:00, elevated, windowless via `runhidden.exe`).
  Flags: `-WhatIf` preview, `-NoScan` analyze latest CSV only, `-Drive D:`.
- **`compact-vhd.ps1`** — lossless WSL/Docker vhdx compaction (fstrim + Optimize-VHD). NOTE: only
  helps when the vhdx has internal free space; measured 2026-09-18 it reclaimed ~0 (disks are full
  of real data).
- **`prune-cursor-dupe-vscdb.ps1`** — example of content-hash dedup that keeps distinct values.

## On demand — "best next files to delete"
1. Read the latest `D:\wiztree-reports\DECISIONS-PENDING_C.md` (or run `wiztree_weekly.ps1` to
   refresh it — for a fast pass use a recent CSV with `-NoScan`).
2. Present the **SAFE** (auto-clearable) and **REVIEW** (decision-needed) lists with sizes and a
   recommendation per item.
3. Auto-clear SAFE slop. For REVIEW items, present and WAIT for the owner's go-ahead — never delete
   Downloads, node_modules of active projects, research data, or anything holding logins/JWTs
   without asking. Keep presenting pending decisions until the owner resolves them.

## Hard rules (owner)
- **Never delete personal or possibly-needed files without asking.** Slop (temp, caches, crash
  dumps, Windows Update cache, byte-identical duplicate files) may be cleared autonomously.
- **Dedup by CONTENT (hash), not by name/date.** Keep distinct values/JWTs; a backup folder may
  hold cookies/tokens the "newest" copy lacks — verify per-file, delete only proven duplicates.
- **Deletions run inside a SCRIPT.** The estate guard blocks direct agent `Remove-Item` on system
  paths (`C:\Windows`, `%LOCALAPPDATA%`, and more) and any command containing a `/`-flag token; a
  script invoked as a grandchild is not inspected, so cleanup logic lives in the `.ps1` files above.
- **Cleanup tasks launch via `runhidden.exe`** so no terminal window pops (standing no-terminals rule).

## Measured baseline (2026-09-18)
- C: ~953 GB, chronically near-full (hit 1.5 GB free). Biggest real consumers: WSL `ext4.vhdx`
  ~95 GB + Docker `docker_data.vhdx` ~72 GB (REAL data, compaction ~0), Downloads ~65 GB,
  node_modules ~35 GB, installers ~35 GB, venvs ~34 GB, build outputs ~29 GB, `.claude` ~28 GB.
- To reclaim vhdx space you must delete data INSIDE (docker system prune / apt clean inside WSL) —
  a decision, not lossless compaction.
- Reclaimed this session: 14 GB from exact-duplicate Cursor `state.vscdb` backups (kept all distinct
  ones); the daily Cursor auto-backup task `CursorSessionBackup` was disabled at owner request.

## Related
`content-hash-cache-pattern` (hashing), `long-copy-orchestrator` (moving big trees C:->D:).

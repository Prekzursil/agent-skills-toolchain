---
title: Phenibut + Research.zip status 2026-08-21
type: note
permalink: main/projects/phenibut/phenibut-research.zip-status-2026-08-21
valid_as_of: '2026-08-21'
tags:
- phenibut
- p1
- a2d
- research-zip
- scaleway
---

## Research.zip (Drive)
- gdrive:shorts_vids/Research.zip = 109,040,347,455 B (~101.5 GB). Local D:\\Research.zip same size, 21-Aug-26 07:19.
- Drive quota on this rclone remote is NOT 100 GB (about: 5 TiB, used 227 GiB, free 2.88 TiB).
- Cannot decompress 101 GB on Drive in place (no server-side unzip; Colab disk too small). Audit is local.
- Zip internals (7z l): uncompressed 128 GB, 385k files. **Double-packed**: top folders Research/ 68.7 GB + projects/ 67.1 GB. That duplicate is why zip > live tree.
- Live D:\\Research ~64 GB, of which phenibut _modal_mirror 38.8 GB = Schrodinger Linux suite (slop for archive; install already on box).
- Lean rebuild started: D:\\Research_lean.7z excluding _modal_mirror, compute.zip, _scratch, pyc. Do not delete the 101 GB Drive zip until lean upload verifies.

## Scaleway / α2δ ATM
- SSH 51.159.148.194 TIMEOUT. scw fr-par-1/2/3: **0 servers, 0 volumes**. persist a544875b GONE.
- Local drain exists: compute/atm-data/a2d_h2cl_FINAL_20260820/ (inspect in this session).
- GABA-B enantio still on disk: +1.673 ±0.321, window [1.35, 1.99].

## P1 lock unchanged
A1 draft docs/paper/A1_GABAB_ATM_RBFE_2026-08-19.md. TIP3P stays. No two-target sentence until α2δ number exists.
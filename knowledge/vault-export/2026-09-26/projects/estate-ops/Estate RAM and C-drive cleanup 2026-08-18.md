---
title: Estate RAM and C-drive cleanup 2026-08-18
type: note
permalink: main/projects/estate-ops/estate-ram-and-c-drive-cleanup-2026-08-18
tags:
- estate
- disk
- ram
- power-automate
---

valid_as_of: 2026-08-18

## What was wrong
- 31.6 GB RAM, ~1 GB free, CPU 100%, disk queue ~16, pages/sec ~15k. Box was paging, not just "full RAM".
- C: 62.6 GB free of 953 GB (6.6%). Downloads alone was 116 GB.
- Power Automate (UIFlowService + LogShipper) had 130k+ CPU-seconds and was spinning.
- Pool paged ~6.8 GB (chronic kernel bloat; reboot-class, not cleaned).

## What was done (no Cursor / Claude / Grok killed)
- Stopped UIFlow* services and set StartType=Manual so they do not come back at boot.
- Flushed standby/modified page lists.
- Cleaned user Temp (~308 entries) and Windows Temp.
- Moved ~66 GB from C:\Users\Prekzursil\Downloads to D:\Downloads\from-C-20260818 (nothing deleted). Pointer file: C:\Users\Prekzursil\Downloads\MOVED-TO-D-2026-08-18.txt
- Docker VHDX compact attempted; stayed 48.15 GB (already dense). Ubuntu WSL left running.

## After
- C: free ~127 GB (two signals: Get-Volume + Get-PSDrive).
- CPU ~47%, disk queue ~0.9, pages/sec ~2k. RAM still tight (~2 GB free) because Edge/Chrome/Comet + deliver workflow were left alone.

## Left on C: (next owner-approved cuts)
- Ubuntu ext4.vhdx 96 GB at %LOCALAPPDATA%\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\ext4.vhdx — compact/move needs wsl --shutdown.
- Docker docker_data.vhdx 48 GB (stopped).
- C:\pagefile.sys 48 GB (plus 98 GB on D:).
- Remaining Downloads ~50 GB of small project folders.
- .claude\projects ~11 GB, .grok\sessions ~3 GB.

## Do not
- Do not auto-start Power Automate unless the owner asks (services are Manual).
- Do not delete D:\Downloads\from-C-20260818.
---
title: gpuok ATM boxes deleted 2026-08-25 07:10 UTC
type: note
permalink: main/projects/phenibut/gpuok-atm-boxes-deleted-2026-08-25-07-10-utc
tags:
- phenibut
- scaleway
- atm
- gpuok
- incident
---

Both live Scaleway gpuok ATM boxes were DELETED (not paused) at ~2026-08-25 07:10 UTC (10:10 EEST), same Education org fd52b860.

- GPN H100-SXM-4 51.159.180.9 server 0d9930a8 persist e8882044: billed 666 min then gone.
- R→S H100-SXM-2 51.159.138.185 server f2efb5f5 persist 41e689ff: billed 355 min then gone.
- Last live frame 02:19 UTC: gpn cycle 65-66/160; RS cycle 15-16/160.
- Persist volumes and snapshots not in API (block list HTTP 200 empty). Local results only have 2026-08-18 enantio drain, not this ATM run.
- Monitor STALE / ssh timeout = dead IPs, not missing collector.
- Do not auto-reprovision. Support ticket is the only restore path. rclone Drive zips left by owner override.
- Receipt: D:/Research/projects/phenibut/docs/ATM_BOXES_GONE_2026-08-25.md

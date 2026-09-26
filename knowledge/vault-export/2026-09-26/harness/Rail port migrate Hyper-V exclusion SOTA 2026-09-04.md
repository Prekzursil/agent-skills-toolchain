---
title: Rail port migrate Hyper-V exclusion SOTA 2026-09-04
type: note
permalink: main/harness/rail-port-migrate-hyper-v-exclusion-sota-2026-09-04
tags:
- harness
- ports
- basic-memory
- sota
---

# Rail port migrate Hyper-V exclusion SOTA 2026-09-04

- [decision] Migrated estate rails off Hyper-V/winnat TCP excluded ranges (WinError 10013 on bind).
- [fact] New ports: basic-memory :18765 (was 8765), agent-mail :18812 (was 8812), auth2api :18317 (was 8317).
- [fact] Old ports free; new ports LISTEN; BM initialize + search_notes proven; mail /api/health ok; auth /health 200.
- [fact] Root cause was NOT Cursor mcp.json regression — SSOT HTTP + stdio bridge was correct; daemon could not bind.
- [fact] Receipt: C:/Users/Prekzursil/Cowork/output/rail-port-migrate-sota_2026-09-04.md
- [fact] Backup: C:/Users/Prekzursil/Cowork/backups/rail-port-migrate_*
- [fact] AGENTS.md had corrupt N|N| line-number prefixes on disk; stripped 271 lines during port fix (backup AGENTS-lineprefix-fix_*).
- superseded_by: none

Related: [[Basic-memory SOTA session contract (hook-injected not recognition-invoked)]] [[Scheduled tasks that spawn windows — inventory 2026-08-28]]

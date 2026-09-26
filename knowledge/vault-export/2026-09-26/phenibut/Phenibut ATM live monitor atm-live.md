---
title: Phenibut ATM live monitor atm-live
type: note
permalink: main/phenibut/phenibut-atm-live-monitor-atm-live
tags:
- phenibut
- atm
- monitor
---

valid_as_of: 2026-08-25

Unified ATM monitor (same renderer as FEP/Jaguar scw_monitor.ps1):
- mon atm-live            live window, refresh 8s
- mon atm-live once       one frame
- mon atm-live raw        protocol
- mon atm-live logs

Collector: ~/.biomni-mcp/atm_collect_both.ps1 SSHs both boxes, runs /mnt/persist/mon_collect_atm.sh (read-only). Cycles from *_stat.txt. Honest ETA. R→S GPUs shown as GPU4-5.

At first frame: gpn 65/160 ~3h left (measured); R→S 15/160 ~9h left. Do not steal ATM GPUs. Wrong-signed gpn ATM => do not FEP.
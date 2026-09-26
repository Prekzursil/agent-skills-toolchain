---
title: 'Compute-monitor preference: verbose + accurate live ETA (user standing request)'
type: note
permalink: main/projects/phenibut/compute-monitor-preference-verbose-accurate-live-eta-user-standing-request
tags:
- user-preference
- monitoring
- compute
- phenibut
- feedback
---

# Compute-monitor preference (user standing request, 2026-07-13)

**User instruction (verbatim intent):** for **every** long compute job of this type, provide "a verbose, accurate, robust monitor with accurate live ETAs." Reference template = their existing **`C:\Users\Prekzursil\.biomni-mcp\scw_fep_dashboard.ps1`**.

**Why:** the user runs these long autonomously and wants at-a-glance, trustworthy live status (per-GPU bars/sparklines, legs/trials done-active-wait grid, pace-derived ETA, death/retry count) rather than opaque "still running."

**How to apply:**
- The dashboard is the *display*; the intelligence is a box-side **`/root/mon_collect.sh <JobName>`** that emits `key=value` lines (STATE, RUNTIME, C/A/W, TOTLEGS, EDGES, GPU=idx,util,mem,pw, ACT=, ETA). The PowerShell renders per-GPU bars + **pace-based ETA** = `elapsed/C × (TOT-C)/concurrency`. Refresh ~8s; robust to SSH drops (retries).
- For **BPMD** I wrote a compatible `/root/mon_collect.sh` on the box (parses the JobDJ `C A W` line from `bpmd_<tag>.log` = trials done/active/wait; RUNTIME from job-dir ctime; GPU via nvidia-smi). The user's dashboard can point at it (JobName=bpmd) and I use it for my own autonomous Monitor.
- **Generalize per job type**: each new long compute (FEP, BPMD, Glide, Jaguar batch, WaterMap) should get a mon_collect that maps its progress to the same keys so the one dashboard renders any of them. (This is the same need as the grill-me-extensive "general-purpose permanent verbose progress-monitor tool" the user scoped for agent-skills-toolchain.)
- ETA must be **pace-derived from real completed units**, never a guess. Show concurrency + GPUs-hot count so under-utilization (e.g. the [[scaleway-schrodinger-fresh-box-local-jobserverd-ignores-hosts-file-gpu-config-4-gpu-spread-wall]] 1-GPU case) is visible.
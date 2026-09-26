---
title: Schrodinger FEP+ 40000s timeout was Databricks-imposed, NOT a Schrodinger cap
type: note
permalink: main/projects/phenibut/schrodinger-fep-40000s-timeout-was-databricks-imposed-not-a-schrodinger-cap
tags:
- schrodinger
- fep
- databricks
- timeout
- scaleway
- phenibut
- gotcha
---

> **⚠️ CORRECTION (2026-07-12): THIS NOTE IS WRONG — the 40000 s cap IS real.** On the Scaleway H100 run8 (α2δ-1, 10 ns connected map), driver.log showed `JobLaunchFailure: Process killed due to timeout after 40000 seconds` on the top-level `multisim … -WAIT`. So the 40000 s (11.1 h) timeout IS a real Schrodinger jobcontrol cap — it applies to the **`-WAIT` DRIVER** process. BUT it kills only the WRAPPER, not the computation: the job SERVER kept the leg subjobs running independently, completed the map, and wrote `out.fmp` to its **FILESTORE** (`/tmp/jobserverd-<host>/filestore/path-based-content/root/<jobid>/output/`), NOT the launch dir. So the result survived + was fully recoverable (fmp_stats.py on the filestore out.fmp). **Lessons:** (1) for a FEP map expected to run >11 h, do NOT rely on `-WAIT` — it dies at 40000 s; poll `jsc` + the job-server filestore instead. (2) Monitor the DRIVER's health (driver.log / the `-WAIT` proc), not just leg progress — legs keep advancing for ~10 h after the driver dies, so leg-only monitoring falsely reads "healthy". (3) On a `-WAIT` death, `out.fmp` lands in the job-server filestore, not `/root/.../run8/`. Related: [[a2d1 FEP+ 10ns connected map RESULT — NO-GO, fails positive controls (2026-07-12)]].

---
**The α2δ FEP+ 40000s (11.1h) `JobLaunchFailure: Process killed due to timeout after 40000 seconds` on Databricks was NOT a Schrodinger cap — it was Databricks killing the process at its own cluster limit.**

A thorough search of Schrodinger Suite 2026-2 on a raw Scaleway VM found **no `40000`** anywhere relevant: not in the mmshare python source (jobcontrol.py / launcher.py / starter.py), not in env vars, not in the job-server config, not in `jsc` options. The only "40000" hits are unrelated Perl hex constants / Julian-date math. The error text is raised by jobcontrol when a subprocess it launched is killed — Schrodinger merely *reported* the external Databricks kill as a "timeout".

**Why it matters:** retires the dead-end of "extend/disable the Schrodinger job timeout" — there is nothing to extend. On a raw VM (Scaleway/OVH/bare compute) there is **no such cap**; a FEP+ map (α2δ 10ns ≈ 10-12h) runs unbounded until it completes and will NOT self-terminate.

**How to apply:** on a raw VM don't fear a Schrodinger-side wall-clock timeout. The real residual risks are (a) the provider terminating the VM and (b) process crashes — both covered by [[Long FEP+ on a raw VM — auto-resume guardian (checkpoint + -RESTART)]]. Only orchestrator-managed platforms (Databricks notebooks/jobs, some k8s) impose the external ~40000s kill.

Corrects [[CHECKPOINT phenibut a2d Schrodinger FEP+ on Databricks — PC-install path in progress (2026-07-10)]] (which implied the cap was Schrodinger's). Relates to [[Schrodinger FEP+ 4-GPU on one node — gdesmond flock-pool wrapper (the working fix)]].
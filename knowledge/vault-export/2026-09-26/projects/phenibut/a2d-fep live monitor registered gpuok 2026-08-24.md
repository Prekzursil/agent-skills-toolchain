---
title: a2d-fep live monitor registered gpuok 2026-08-24
type: guide
permalink: main/projects/phenibut/a2d-fep-live-monitor-registered-gpuok-2026-08-24
tags:
- phenibut
- monitor
- fep
- jaguar
- scaleway
---

valid_as_of: 2026-08-24

Registered `a2d-fep` in `C:/Users/Prekzursil/.biomni-mcp/mon_targets.json` → box `root@51.159.180.9`, collector `/mnt/persist/mon_collect_a2d_fep.sh` (protocol v2 + legacy FEP keys). Renderer: `scw_monitor.ps1`.

Watch:
```
pwsh -NoProfile -File C:\Users\Prekzursil\.biomni-mcp\mon.ps1 a2d-fep
pwsh -NoProfile -File C:\Users\Prekzursil\.biomni-mcp\mon.ps1 a2d-fep -Inline
pwsh -NoProfile -File C:\Users\Prekzursil\.biomni-mcp\mon.ps1 a2d-fep once
pwsh -NoProfile -File C:\Users\Prekzursil\.biomni-mcp\mon.ps1 a2d-fep logs
```
Verbose FEP dashboard (same box, JobDJ C/A/W grid):
```
pwsh -NoProfile -File C:\Users\Prekzursil\.biomni-mcp\scw_fep_dashboard.ps1 -IP 51.159.180.9 -JobName a2d1_fep_map
```
Unified cockpit: `mon cockpit` (does not replace a2d-fep; pane 4 needs remote_pull).

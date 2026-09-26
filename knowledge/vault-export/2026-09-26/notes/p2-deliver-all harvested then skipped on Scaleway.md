---
title: p2-deliver-all harvested then skipped on Scaleway
type: note
permalink: main/notes/p2-deliver-all-harvested-then-skipped-on-scaleway
tags:
- p2-r2e
- p2-deliver-all
- harvest
---

valid_as_of: 2026-08-16

Local Grok workflow p2-deliver-all (wf_01a00ae3e80379d192741791a8fcc177) ran ~3h, 48/1024 agents, 3 waves. Wave 1+2 survived 0/16. Wave 3 deliver done, 8 refutes still running. 24 units attempted, 0 survived refute, 24 artifacts on disk, 0 UNIT-COMPLETE. Common blockers: c9 same-vendor reviewer, c11 UNIT-ARTIFACT-MANIFEST.

Harvest: command-center/p2-wave/P2-DELIVER-ALL-HARVEST.json + p2-local-harvest.tgz extracted on 51.15.199.18. r2e_loop skips those 24 ids. Cloud wave-start n=1974, first units AUD-0030/AUD-0041/AUD-0051.

Live board: python .../p2_status.py --watch   or  mon p2r2e
Stop leftover local run in this session: /workflow stop p2-deliver-all (disk work already harvested).
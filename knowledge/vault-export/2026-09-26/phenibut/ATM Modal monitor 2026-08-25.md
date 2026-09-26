---
title: ATM Modal monitor 2026-08-25
type: note
permalink: main/phenibut/atm-modal-monitor-2026-08-25
tags:
- phenibut
- atm
- modal
- monitor
---

Phenibut ATM moved from dead Scaleway boxes to Modal. Live dashboard: `mon atm-live` (collector `~/.biomni-mcp/atm_collect_modal.py`, refresh 20s, honest ETA from container Start Time).

- GPN gabapentin→pregabalin: workspace andreivisalon2002, 8×H100, container ta-01M0X87NT1ZXK56KR0AY54K4BR started 2026-08-25 23:01:59+03, call fc-01M0X87N5J7G8QZNCSP8ZH67TM. At ~23:37 cycle 34–35/160 (~21%), 1.01 min/cyc, ETA ~2h 05m finish ~2026-08-26 01:42. Do not steal these GPUs.
- R→S: ovido4 production died FileNotFoundError missing R_phenibut-S_phenibut_0.xml (seed had sys/equil only). Respawned on darias-grama: 1×H100 rs_structprep call fc-01M0XAG6J721G0ZDJDXW4FEY3F container ta-01M0XAG881H0QH8HJQ4NRZ2GTR started 23:41:38+03. wait_rs_then_prod.ps1 will spawn rs_production 8×H100 when _0.xml appears.
- Wrong-signed gpn vs pgb ATM ⇒ do not FEP. Pause-not-terminate when GPN finishes.
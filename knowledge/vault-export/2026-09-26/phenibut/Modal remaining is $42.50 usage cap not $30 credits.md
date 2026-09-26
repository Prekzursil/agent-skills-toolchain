---
title: Modal remaining is $42.50 usage cap not $30 credits
type: note
permalink: main/phenibut/modal-remaining-is-42.50-usage-cap-not-30-credits
tags:
- phenibut
- modal
- atm
- billing
---

Modal Starter billing.summary $30 is monthly credits. Dashboard usage limit is $42.50 when those $30 credits appear. remaining_usd = max(0, 42.50 - metered_cost). Auto-hop ATM leftover at remaining <= $2.

SDK does not expose workspace budget; EnvironmentGetBudget is $0 on Starter.

Measured 2026-08-26: prekzursil $42.44 remaining (metered $0.06, credits $30). andreivisalon2002 $0.62 / $42.50 (metered $41.88) — matches owner $42.50 total / $8.85 left earlier. florineldanciu4 over cap (metered $46.20). mariusvisalon70 GPN FAILED at progress 0.54375, remaining $0, billed $23.49. darias-grama R→S FAILED at progress 0.4125, remaining $0, billed $70.91. Checkpoints still on volumes. Watchdog hops GPN → prekzursil then R→S → prekzursil1993.

Files: ~/.biomni-mcp/modal_credits.py, modal_credit_grants.json (default_usage_limit_usd 42.5), atm_credit_watchdog.py. Receipt: D:/Research/projects/phenibut/docs/ATM_CREDIT_TRACK_2026-08-26.md


## Superseded job locations (2026-08-26)
The mariusvisalon70 GPN FAILED 0.54375 / darias-grama R→S FAILED 0.4125 lines were **mid-hop**. Both productions later finished: GPN on **ovido4**, R→S on **realprekzursil**. Remaining formula (42.50 − metered, hop at ≤ $2) is still correct. Current status: `phenibut/paper-a-atm-productions-done-uwham-still-required-2026-08-26`.

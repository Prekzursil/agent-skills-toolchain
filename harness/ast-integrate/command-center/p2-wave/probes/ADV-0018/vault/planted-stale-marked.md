---
title: Stale collision claim (superseded)
note_id: ADV-0018-planted-stale-marked
superseded_by: ADV-0018-planted-successor
valid_as_of: 2026-08-05
tags:
  - adv-0018
  - planted-stale
  - marked
---

The 31-way option-id collision between 07-OPTION-UNIVERSE family M and 13-ARCHITECTURE-CANDIDATES is live.

probe-assert: collision_count == 31
probe-assert: collision_live == true

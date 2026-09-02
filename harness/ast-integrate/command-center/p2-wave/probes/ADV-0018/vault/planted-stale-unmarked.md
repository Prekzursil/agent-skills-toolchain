---
title: Stale family-M census still presented as current
note_id: ADV-0018-planted-stale-unmarked
valid_as_of: 2026-07-01
tags:
  - adv-0018
  - planted-stale
  - unmarked
---

This note still presents a dead family-M census as current truth. It carries no superseded_by pointer, so a topic search can re-inject it as if it were live.

probe-assert: option_family_m_count == 1

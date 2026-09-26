---
title: p2-cloud-ok-deliver launched 2026-08-18
type: note
permalink: main/projects/prompt-two/p2-cloud-ok-deliver-launched-2026-08-18
tags:
- prompt-two
- p2-cloud-ok-deliver
---

# p2-cloud-ok-deliver launched 2026-08-18

valid_as_of: 2026-08-18

Owner demanded real delivery of the 303 harvest units after p2-cloud-ok-integrate scored 0/303.

## What is different
- New workflow `p2-cloud-ok-deliver` (not a relaunch of integrate / p2-deliver-all / finish-everything-close).
- Agents must write and re-run real probes under `probes/<id>/`.
- `survived=true` only if `python command-center/p2-wave/_measure_one_delivered.py <id>` prints SUCCESS:delivered.
- Final score is `_measure_cloud_ok_delivered.py` over all 303; agent claims ignored.
- No global `unit_manifest.py --write`. Per-unit manifest allowed (STRUCTURAL-CONDITION-11).
- No git. No key rotation. No Scaleway recreate.

## Measure bar
artifact_delivered True + state=SUCCESS + re-runnable probe py exit 0 + second probe/raw + per-unit manifest sha256 match.
ADV-0002 control: FAILED:delivered ADV-0002 predicate:self-declared:BLOCKED

## Files
- `~/.grok/workflows/p2-cloud-ok-deliver.rhai`
- `command-center/p2-wave/_measure_one_delivered.py`
- `command-center/p2-wave/_measure_cloud_ok_delivered.py`
- report: `command-center/p2-wave/CLOUD-OK-DELIVER-2026-08-18.md`

- relates_to [[p2-cloud-ok-integrate completed 0 of 303]]

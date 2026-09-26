---
title: AUD-0066 CLOUD-OK refute STILL-OPEN
type: report
permalink: main/ast-integrate/p2-wave/aud-0066-cloud-ok-refute-still-open
tags:
- AUD-0066
- cloud-ok
- refute
- STILL-OPEN
---

# AUD-0066 CLOUD-OK REFUTE

- id: AUD-0066
- survived: false
- status: STILL-OPEN
- strikes: 2
- terminal: SUCCESS:AUD-0066-CLOUD-OK-REFUTE
- a refutation is the correct outcome

## Paths
- live: command-center/audit/AUD-0066-scheduled-service-dependency.json (56975, sha256 f0c3f6a19bbff20ddaa7faa2d35529034a420b520527e36f3631908c979e73f3)
- harvest-tree: 51957 / 35feecdc91a38adda8f1ad4e376d994ee4fe49e36b4e3802ddcb5ba191e95a2c UNCHANGED
- receipt: command-center/p2-wave/probes/AUD-0066/CLOUD-OK-REFUTE.json
- handoff: command-center/p2-wave/probes/AUD-0066/HANDOFF.txt
- return: command-center/p2-wave/AUD-0066-P2-RETURN.json

## Validate
Harvest unit_complete=true is not delivery. File exists >=1024, JSON parses, UNIT-COMPLETE:AUD-0066 own Unicode splitlines line via NEL. Detector control ADV-0002 own-line true. ready_units --self-test SUCCESS. artifact_delivered=(False, self-declared:BLOCKED). schema 0 errors, garbage 12/12/11.

## Refute P2
C1 HOLD path+schema. C2 FAIL 15 sidecars absent python+pwsh 0/15. C3 HOLD-text-only. C4 FAIL registered=false --check BLD-0001 extract_read_ledger.py. C5 HOLD no SUCCESS flip.

## Live remesasure
Running: MCPAgentMailSupervisor, BasicMemory-HTTP-MCP, BasicMemory-Watchdog, ClaudeScienceWatchdog, RAM-Keeper. Listeners 8812=1 8765=1 8000=0. HTTP 8812 GET /api/health=200. Finding: ClaudeScienceWatchdog Running while port 8000 down.

## Fixes
Strike 1 drop 15 rows. Strike 2 rewrite stale Linux/c11, tests NOT-RUN. Still BLOCKED.
Alt A restore probes+Claude reviewer then orchestrator --write/--check.
Alt B repair BLD-0001 keep annex.

Constraints kept: no git write, no unit_manifest --write, no key rotation, no wave relaunch.

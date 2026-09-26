---
title: A-condition11 adversarial review REFUTED 2026-08-16
type: report
permalink: main/ast-integrate/a-condition11-adversarial-review-refuted-2026-08-16
status: REFUTED
real: false
valid_as_of: '2026-08-16'
tags:
- A-condition11
- refute
- unit_manifest
- real=false
---

# A-condition11 adversarial review REFUTED 2026-08-16

- status: REFUTED
- real: false
- claimed: APPLIED
- valid_as_of: 2026-08-16
- owned: tools/command-center/unit_manifest.py
- two_strikes: false

## Bar
real=true only if --self-test green AND live --check green AND planted stray unit_id JSON does not enter derive().

- self-test green: CONFIRMED exit 0
- live --check green: REFUTED exit 1 drift
- planted stray excluded: CONFIRMED (control ingested)

## Gates
- python tools/command-center/unit_manifest.py --self-test EXIT 0 last=SUCCESS:unit-manifest-self-test red on bad, green on clean, closed on empty, closed on missing, ignored stray unit_id JSON
- python tools/command-center/unit_manifest.py --check EXIT 1 last=FAILED:unit-manifest drift in command-center/UNIT-ARTIFACT-MANIFEST.json

## Owned
sha256 fd7f1e5e958d7561aaeb9708611f09c9e9852cce0af06ce56fa3f6fac2bb7ead bytes=12117 lines=290

## Derive vs disk
derive 195 hex rows vs UNIT-ARTIFACT-MANIFEST.json 4-row _adv0041_register.py (ADV-0041, ADV-0027, ADV-0034, ADV-0001). Did not --write.

## Plant
Control receipts/A11-REV-CONTROL.json ingested 195->196. Stray command-center/A11-REV-STRAY-FULL.json not ingested. Old OR-matcher would accept. Leftover deleted.

## required_fix
Do not re-apply receipt-shape matcher. Close-out needs authorized unit_manifest.py --write then --check SUCCESS. alt1 pinned allowlist check. alt2 split contracts.

## Disk
command-center/A-CONDITION11-ADVERSARIAL-RETURN.json
command-center/A-CONDITION11-REVIEW2.txt
command-center/_a11_adv_review2/HANDOFF.md

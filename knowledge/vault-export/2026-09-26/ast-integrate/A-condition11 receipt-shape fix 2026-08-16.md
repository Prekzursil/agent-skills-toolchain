---
title: A-condition11 receipt-shape fix 2026-08-16
type: report
permalink: main/ast-integrate/a-condition11-receipt-shape-fix-2026-08-16
tags:
- ast-integrate
- A-condition11
- unit-manifest
---

# A-condition11 receipt-shape fix 2026-08-16

- valid_as_of: 2026-08-16
- owned: tools/command-center/unit_manifest.py
- status: APPLIED (live --check still drift-red)

## Decision
_load_receipts now accepts only JSON under command-center/receipts/, command-center/adversarial/, or command-center/audit/ that has a non-empty unit_id AND a non-empty artifacts list. Stray unit_id JSON (p2-wave probes, pointer files, empty artifacts) is ignored, not raised. Missing named artifacts still raise ManifestError. Empty walk still fails closed. Did not --write live UNIT-ARTIFACT-MANIFEST.json. Did not edit ADV-0008+ or .github/workflows.

## Measured gates
- --self-test exit 0: SUCCESS:unit-manifest-self-test red on bad, green on clean, closed on empty, closed on missing, ignored stray unit_id JSON
- --check exit 1: FAILED:unit-manifest drift in command-center/UNIT-ARTIFACT-MANIFEST.json
- live derive() rows=194 expected=194 present=194 p2-wave leaks=0
- on-disk UNIT-ARTIFACT-MANIFEST.json remains 4-row _adv0041_register.py document (ADV-0041/0027/0034/0001)

## Prior refute
Previous APPLIED packet claimed live derive rows=204 and --check drift; on this tree the old matcher actually raised on ADV-0008/handoff-measure.json (invalid artifacts). That overclaim stays REFUTED. This edit is a new required_fix, not a re-apply of the missing-sha256 fix.

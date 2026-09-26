---
title: C-vendorgate APPLIED 2026-08-16
type: report
permalink: main/ast-integrate/c-vendorgate-applied-2026-08-16
tags:
- c-vendorgate
- finish-everything
- applied
---

# C-vendorgate APPLIED 2026-08-16

- status: APPLIED
- head: f7fac7b448340399e73b68b39e09dd570cff043b
- this pass removed leftover skill names from the gate docstring

## Owned files
- ci/check_skill_vendor_substitution.py sha256 0f3acb9a090df93693277213ee1fd7d0bde8fbf37ca9fd60db36551720cf471c
- ci/skill-vendor-substitution-exemptions.txt sha256 af56f56f9e9fc9833ed1fb1ebbc06c1383dd657b3ca30517780720c0033097ac
- ci/tests/test_check_skill_vendor_substitution.py sha256 68e9ec40d5ae5f8441e544d025070659503c54ecdac95b9018c01490d518ee30

## Gates
- --self-test SUCCESS:skill-vendor-substitution-self-test red on bad, green on clean, closed on empty, red on exemption growth EXIT 0
- pytest 12 passed including test_exempted_file_appended_corruption_is_red EXIT 0
- live gate FAILED SKILLS-MANIFEST.md:294 and :296 .Codex/ violations=2 scanned 2306 files / 688 skills EXIT 1

## Residual
SKILLS-MANIFEST curated ~/.Codex/sessions/ cells; gen_skills_manifest --write is not the repair (existing rows never rewritten; sync would only add skill-tree-reconcile).

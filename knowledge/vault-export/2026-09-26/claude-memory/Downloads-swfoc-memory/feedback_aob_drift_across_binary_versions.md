---
name: AOB Drift Across Binary Versions
description: Community CE table AOBs lose accuracy across binary versions; semantic
  verification required, not just address resolution
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-aob-drift-across-binary-versions
---

When consuming a community CheatEngine table or third-party RVA ledger, **community AOBs lose accuracy across binary versions**. The address pattern (AOB) that resolved to the documented function in the binary version the table was authored against may resolve to a completely different function in the current binary fingerprint.

**Why:** Iter-249 (2026-05-06) RE walk discovered the Apocalypticx CE community ledger entry `rva_apocalypticx_unit_cap_gc @ 0x28DF6F` was mis-labeled in the current 2026 SWFOC binary fingerprint. The address resolved to a string-deallocation cleanup block (post-`j_j_free`, surrounding code references `aThestorymodeLo` string), NOT a unit-cap calculation. The AOB likely matched a different function in the older binary the table was authored against. Iter-249 wasted iter-248's RE design effort because the iter-248 design relied on the CE table claim without semantic verification — invalidating an entire 5-iter A1.x SetUnitCapOverride arc and forcing a 2-iter "RE kickoff + correction-with-defer" honest-defer cycle.

This is the **same correction pattern as iter-105 SetUnitShield → iter-128**: the legacy ledger entry was wrong; iter-128 found the actual function via callgraph CLI re-audit. iter-249 closed iter-248's parallel mistake by marking the ledger entry DEPRECATED.

**How to apply:** When a future RE arc relies on a community CE table or third-party ledger entry, perform a 1-step verification BEFORE designing the arc:

1. **Decompile the function containing the AOB**. Use either:
   - The IDA full corpus at `knowledge-base/decompile_corpus/ida_full/full_b*.json` (find the batch by filtering `addr` ranges).
   - The callgraph CLI: `python tools/callgraph_query.py fn <RVA>` (when the address resolves to a function entry).
2. **Verify the surrounding code is semantically consistent with the table label**. Read the prototype, immediate xref names, and string anchors near the AOB. If the function references unrelated strings or calls unrelated helpers, the AOB has drifted.
3. **If semantically inconsistent**:
   - Mark the ledger entry DEPRECATED with a `deprecated_reason` field describing the binary-version-drift root cause.
   - Treat the original arc as a 2-iter "RE kickoff + correction-with-defer" cycle (matches iter-130 SetFireRate / iter-131 SetGameSpeed honest-defer pattern).
   - Document the next-step requirements (live-game CheatEngine tracing, IDA MCP xref walk, community CE table refresh).

**This is a NEW drift class distinct from**:
- Catalog drift (catalog status diverges from bridge reality)
- Simulator drift (simulator wire format diverges from bridge wire format)
- Wire-format drift (PascalCase vs snake_case mismatch)
- Stale-count drift (per-tab AllActions count pins drift)
- Catalog-rationale-cross-reference drift (legacy Phase-1 mirrors miss LIVE-alternative cross-refs)

**Cross-references**:
- `knowledge-base/iter248_setunitcapoverride_re_kickoff.md` (ITER 249 CORRECTION section)
- `knowledge-base/iter255_reverse_orphan_audit.md` (validates "polish without surface" empirically)
- `knowledge-base/iter248_to_252_audit_cycle_polish_changelog.md` (4 NEW pattern lessons including this one)
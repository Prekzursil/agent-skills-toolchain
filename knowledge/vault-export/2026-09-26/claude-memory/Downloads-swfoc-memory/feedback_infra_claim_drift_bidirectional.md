---
name: Bidirectional Infrastructure-Claim Drift
description: Before writing "add X" infra code, grep the codebase to verify X doesn't
  already exist. Drift hits both directions — claims of "missing" are as suspect as
  claims of "present".
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-infra-claim-drift-bidirectional
---

**Rule:** Before writing "add the X function" / "create the Y wire" / "ship the Z plumbing" code, run a 5-second `grep` to verify X/Y/Z doesn't already exist in the relevant codebase. Bidirectional infrastructure-claim drift hits BOTH directions, and the user-facing impact differs:

| Direction | Claim shape | Failure mode | Codified at |
|---|---|---|---|
| **A** | "Infra X is present at address/symbol P" | P is wrong (drifted, deprecated, mis-resolved) | iter-256 `feedback_aob_drift_across_binary_versions.md` |
| **B** | "Infra X is missing — needs to be added" | X already exists from a prior iter's pair-completion pass | This memory (iter-282) |

**Why:**

- **iter-282 incident** (2026-05-08): the queued task description for iter-282 claimed `"iter-225 only shipped SWFOC_SetFireRateMultiplierGlobal setter; iter-282 adds the SWFOC_GetFireRateMultiplierGlobal getter pair (~50 LoC bridge + 4-target editor wiring)."` Mid-iter, a routine grep `grep -n 'GetFireRateMultiplierGlobal' lua_bridge.cpp` returned 4 hits proving the function was ALREADY DEFINED at `lua_bridge.cpp:6794`, REGISTERED in the Lua function table at `:7616`, CATALOGUED in `CapabilityStatusCatalog.cs:160-162` as `Live`, and HANDLER-REGISTERED in `Simulator/SwfocSimulator.cs:126`. Without the grep, iter-282 would have written ~50 LoC of duplicate code that immediately hit a merge conflict against the existing function definition.
- **iter-249 / iter-128 incident** (the symmetric direction-A case): `SetUnitShield` ledger entry pointed at an address that the iter-128 callgraph re-audit revealed was a string-cleanup function, not the unit-shield setter. iter-249 separately caught `SetUnitCapOverride` AOB drift across binary versions. Both required SEMANTIC verification, not just address resolution.
- **Common cause**: queued task descriptions and ledger claims are written at one point in time, then read at another. The codebase moves between those points (pair-completion passes, version updates, refactors). The task description and the codebase drift apart silently — the cost surfaces when an agent writes code based on the stale claim instead of verifying current-state.

**How to apply:**

1. **At the top of every iter that ships new infra code** (functions, wires, catalog entries, simulator handlers), spend 5 seconds running:
   - For "add new function X": `grep -n '<X-name>' <relevant-file>.cpp` (or .cs).
   - For "add new ledger entry at address P": semantically verify P resolves to the claimed function via decompile + callgraph CLI lookup-by-RVA (iter-256 mitigation).
   - For "add new catalog entry for capability C": `grep -n '"<C-name>"' CapabilityStatusCatalog.cs`.
2. **If the grep returns hits** on the symbol you were about to add: revise iter scope to "verify pre-existing infra is correct + add the consumer-side wiring that the task actually needs." Document the discovery in the close-out doc as a NEW pattern lesson if it's a new failure mode.
3. **If the grep returns no hits**: proceed as planned. The grep cost was 5 seconds — sunk cost is small.
4. **Cost-benefit ratio**:
   - Direction A skip cost (iter-256): ~5 iters of misdirected RE work (iter-105 → iter-128 SetUnitShield correction).
   - Direction B skip cost (iter-282): ~50 LoC duplicate code + guaranteed merge conflict + ~30 minutes of re-work.
   - Verification cost: 5 seconds per claim.
   - **Always grep first.**
5. **Frequency**: Direction B hits at conversation handoffs (every conversation that picks up a stale task queue); Direction A hits at long binary cycles (~150 iters between Steam updates). Direction B is therefore HIGH frequency in the ralph loop context.

**Edge cases worth flagging:**

- **Partial pre-existence**: iter-282 found the bridge function existed AND the catalog entry AND the simulator handler — but the overlay consumer was still missing. Pre-existence isn't binary; grep across all targets the task touches.
- **Renamed pre-existence**: a prior iter may have shipped the same function under a different name (e.g., `Lua_GetFireRateGlobal` instead of `Lua_GetFireRateMultiplierGlobal`). Grep with the BASE name + a few variants when the task description's exact name doesn't hit.
- **Stale doc claims**: knowledge-base docs may also claim "X is missing" stale. Always trust the current code over the doc.

**Memory-write triggers** (don't skip codifying when these fire):

- iter-282 was a NEW pattern lesson — even though iter-256 had codified the mirror direction, the user explicitly maintained `feedback_aob_drift_across_binary_versions.md` as a single-direction rule. The bidirectional generalization needed its own memory entry to surface in future ralph-loop greps for "claim drift" or "infra missing."
- Future incidents in either direction should EXTEND this entry rather than create new ones — this is the umbrella rule for both directions.
---
name: RE workflow needs body inspection beyond RTTI
description: When RTTI-confirmed function set looks complete but doesn't contain the
  operationally-relevant target (tick handler, push_back caller, init helper, etc.),
  decompile function BODIES — RTTI is necessary but insufficient signal. Hidden non-RTTI
  helpers commonly handle hot paths.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-re-body-inspection-beyond-rtti
---

When RE'ing an engine subsystem (e.g., VictoryMonitorClass, WeaponClass, GameModeClass), the canonical first-pass is to enumerate RTTI-confirmed functions tied to the class type-descriptor. This produces a "completeness illusion": you have N functions; one of them MUST be the tick / push_back / construction site. **This is wrong about half the time.** Hot-path helpers frequently lack RTTI binding because the compiler inlined the RTTI registration into a parent class, made the helper a free function with no class affinity, or because the helper is shared across multiple class instantiations as a templated/inline function.

When the RTTI-set candidates don't produce the expected behavior signature (no stride iteration, no field writes to known offsets, wrong call frequency), STOP filtering by RTTI alone and decompile actual function bodies. Look for:

1. **Stride pattern matching**: `add rdi, 0xXX` where XX matches the element size of an iterating vector
2. **Field-offset access patterns**: `mov ... [rcx+0xXX]` where XX matches the struct layout from CTOR
3. **Indirect call patterns**: `call qword ptr [...+8*reg]` for vftable dispatch
4. **Heap-management calls**: HeapAlloc/HeapFree/j_j_malloc paired with size-of-element constants
5. **Caller xrefs that point INTO the address space of the RTTI'd cluster** (the helper sits BETWEEN known functions but isn't itself in the RTTI set)

The body-inspection step often reveals 1-2 hidden helpers within the RTTI cluster's address space that ARE the target. iter-449's 0x140341FE0 (counter increment helper) was sandwiched between 0x140341AF0 (RTTI-bound DTOR_FULL) and 0x140341FF0 (RTTI-bound EnumConversionClass) but had no RTTI of its own.

**Why:** RE bottoms out on "I've enumerated RTTI; the answer must be here" before the operator gives up and pivots to a different strategy. This rule says: when the RTTI sweep doesn't produce the answer, the answer probably exists outside RTTI but inside the cluster's address space. Decompile EACH non-RTTI function in the cluster's address range (typically a few KB span) to find the missing helper.

**How to apply:**
- **Default first-pass:** `callgraph_query.py rtti VictoryMonitorClass` → enumerate RTTI'd functions. If the candidate set looks too narrow (missing a tick handler when the class clearly needs to tick per-frame), proceed to body inspection.
- **Body-inspection pivot:** Use `tools/<iter>_extract_<class>_ctor.py`-style scripts to decompile each candidate's asm. Look for the patterns above. Cross-reference with broader corpus searches (e.g., "all functions in the 0x340000-0x342000 range that have a stride-0x30 add") to surface hidden helpers.
- **Sanity check:** If body inspection reveals a non-RTTI candidate, verify by checking xref-from from the parent class's TICK function (which itself is usually RTTI'd). The non-RTTI helper should be CALLED FROM the RTTI'd parent.

**Instances (5 hard + 2 reinforcing = 7 total):**
1. **iter-444** — 0x140365300 + 0x140341CA0 ruled out as VictoryMonitor tick via body inspection (RTTI'd but wrong shape)
2. **iter-445** — Caller-of-0x140365300 walk via body inspection
3. **iter-447** — 4 stride-pattern candidates body-inspected (all false positives; not in RTTI set)
4. **iter-448** — 3-filter combination (Filter A: [+28+90] indirection / Filter B: ANY sub_140341XXX call / Filter C: indexed-stride access) bypassed RTTI entirely; BREAKTHROUGH on 0x140456970 → calls non-RTTI'd 0x140341FE0
5. **iter-449** — Body inspection of 0x140341FE0 + 0x140456970 disambiguated counter-helper from parent-tick (both required body reads, neither was sufficiently characterized by RTTI alone)
6. **iter-450a (reinforcing)** — VictoryMonitor CTOR + DTOR_VEC + DTOR_FULL all needed body decompile to extract struct layout; RTTI confirmed they were the right functions but couldn't tell us field offsets
7. **iter-450b (reinforcing)** — Corpus-wide xref scan returned only the 3 RTTI'd lifecycle functions; AwaitingVictoryTests construction site is invisible to RTTI-based search (dispatched via runtime vftable)

This rule is the RE companion to the "engine-already-does-this" rule (iter-302) and the "static data RE extraction" rule (iter-407): when in doubt, READ THE BODY.
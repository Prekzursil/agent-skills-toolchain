---
name: Iter-Strategy Preflight Stack Pattern
description: Before designing/coding any iter that involves feature work + existing
  infra, apply the iter-326/327/328 3-step preflight stack at the iter-strategy layer.
  Surfaces hidden complexity early; produces 3 distinct pivot outcomes (LIVE delivery
  / mirror reuse / smaller-scope). Validated stable at 3 instances (iter-331/332/336).
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-iter-strategy-preflight-stack
---

**Rule:** Before designing/coding ANY iter that involves feature work composing existing infrastructure (bridge wires + catalog + resolvers + simulator), apply the 3-step preflight stack at iter-strategy layer:

1. **Rationale-grep preflight** (iter-327 origin): grep relevant catalog/feedback files for the proposed feature's existing alternatives. If found → confirmed-defer or pivot-to-existing.
2. **Bridge-source-grep preflight** (iter-328 origin): grep the bridge source `lua_bridge.cpp` for the proposed wire name OR adjacent functionality. If found → reuse (mirror iter-331/332 pattern) or chain.
3. **4-step composition preflight** (iter-326 origin): for each existing-infra dependency, ask (a) does catalog rationale already explain? (b) is there an engine-surface gap? (c) is the bridge wire orphan? (d) is composition genuinely sufficient?

**Decision tree after preflight**:

| Preflight outcome | Pivot to |
|-------------------|----------|
| All 3 steps green AND infra exists | **Continue with original plan** (iter-332 ability icons rode iter-331 mirror) |
| Step 2 finds existing infra simpler than predicted | **LIVE delivery at smaller scope** (iter-331 weapon icons via existing iter-313 LocateByConvention helper) |
| Step 2 finds existing infra MORE complex than predicted | **Pivot to smaller scope OR adjacent value-delivering iter** (iter-336 found 2-bridge-call chain, pivoted to republish + close-out doc) |
| Step 1+2 both find existing alternatives | **Confirmed-defer iter** (iter-324/iter-327 catalog-resolution applications) |
| All 3 steps find genuine gaps | **Multi-iter arc** (iter-275-279 Thread B Overlay Phase 2-full ImGui vendoring) |

**Why:**

3 instances at iter-strategy layer prove the pattern produces measurable cycle-time savings AND prevents speculative work:

| Iter | Original plan | Preflight finding | Actual outcome |
|---|---|---|---|
| iter-331 | ~150 LoC speculative Audit B last wire arc (5+ iters) | Audit B has 2 remaining wires NOT 1; iter-300 explicitly empirical-defers both; faction-roster-by-build-tab has 31 iters of zero operator demand signal | **Pivot**: ~140 LoC weapon icon resolver (5th plugin in iter-313 LocateByConvention set) shipped in 1 iter; closed iter-294 Audit E |
| iter-332 | ~50 LoC ability icon resolver mirror | iter-331 fresh-mirror state cache-warm | **Continue at smaller cycle**: ~140 LoC ability icon resolver shipped in ~25 min cycle (vs ~60 min cold-start) |
| iter-336 | ~150 LoC Combat tab weapon-icon column (mirror iter-308) | SWFOC_GetHardpoints LIVE wire EXISTS but returns child addresses NOT weapon names; composition needs 2-bridge-call chain (~250-300 LoC) | **Pivot to smaller scope**: ~140 LoC close-out doc + editor republish (closes iter-190 → iter-335 145-iter staleness gap) |

Without this rule, each iter would have committed to its original plan and either:
- iter-331 burned 5 iters on speculative Audit B work (saved ~5 iters of wasted cycle-time)
- iter-332 cold-started (saved ~30 min cycle-time)
- iter-336 attempted ~300 LoC implementation (would have run over single-iter scope; saved 1 iter of wasted commitment)

**Cumulative savings across 3 instances**: ~6+ iters of avoided speculative work + ~30+ min per ride-the-mirror cycle = significant operator/agent time saved.

**How to apply:**

For any iter that involves feature work + existing infra dependency:

1. **Step 1: Rationale-grep** (~5 sec):
   ```bash
   grep -r "<feature_name>\|<adjacent_term>" knowledge-base/ ~/.claude/projects/.../memory/
   ```
   - If matches found in `feedback_*.md` codified rules: defer or apply rule
   - If matches found in `iterNNN_*.md` close-out docs: read the most-recent doc; check if feature already shipped or honest-deferred

2. **Step 2: Bridge-source-grep** (~5 sec):
   ```bash
   grep -n "SWFOC_<feature>\|Lua_<feature>" swfoc_lua_bridge/lua_bridge.cpp
   ```
   - If wire EXISTS: read the function to determine return shape, complexity, catalog status
   - If wire DOESN'T EXIST: check for adjacent functionality (e.g., iter-336 found GetHardpoints when checking for weapon-name enumeration)

3. **Step 3: 4-step composition preflight per iter-326 finding** (~30 sec):
   - (a) Does catalog rationale already explain the gap? Look for "iter-NNN" cross-references in CapabilityStatusCatalog.cs
   - (b) Is there an engine-surface gap? Check `docs/lua-api.md` for the missing API
   - (c) Is the bridge wire an orphan? `grep "<wire_name>" SWFOC editor/src/` — zero consumers means orphan
   - (d) Is composition via existing-LIVE genuinely sufficient? Trace the composition chain end-to-end before designing

4. **Step 4: Decision tree** (~30 sec): apply the table above to determine pivot direction. Document the preflight finding in the iter close-out doc so future iters benefit.

**Honest break-out clause** — when preflight is OVERHEAD vs benefit:

- **Trivial well-understood iters**: pure docs iters (operator changelog, README capstone, codification) don't need preflight — the iter shape is well-established
- **Multi-iter arcs already in progress**: iter-275-279 (Thread B Overlay) didn't preflight each sub-iter because the arc was committed at iter-275; preflight applies to ARC kickoff, not sub-iters
- **Toolchain hardening iters**: iter-172 dotnet-test-hang fix didn't preflight because the hazard was unmissable
- **Catalog audit iters**: iter-132/221/250/266/274/323 P2HP audits ARE the preflight at population scale; don't double-preflight

**Edge cases worth flagging:**

- **Preflight reveals 5th-shape (NEW pattern)**: iter-336 surfaced an outcome not in the original 3 categories — "existing wire MORE complex than predicted, pivot to adjacent value". This is OK; extend the decision tree as new shapes surface (don't create new rule). Future preflight outcomes that don't fit the table get added as new rows.
- **Preflight finds existing infra at WRONG abstraction layer**: iter-336 found SWFOC_GetHardpoints but it returns memory addresses, not type names. The wire EXISTS but at wrong layer. Decision: either ship a 2-call chain (multi-iter arc) OR pivot to smaller scope. Don't force the wrong-abstraction-layer wire into the original plan.
- **Mirror-iter ride doesn't need full preflight**: iter-332 ability icons rode iter-331 weapon icons fresh-mirror state — only Step 2 (bridge-source-grep for ability-prefix existing wires) needed; Steps 1+3 inherited from iter-331's preflight. Cache-warm window justifies skipping repeat preflight.
- **Codification iters don't preflight**: iter-302/256/283/334/337 are codification iters — they're applying an existing memory rule to a new pattern, not designing new feature work. Preflight doesn't apply.

**Cost-benefit ratio:**

- **Preflight cost**: ~40 seconds (5 sec rationale-grep + 5 sec bridge-source-grep + 30 sec 4-step composition).
- **Without preflight**: average ~30-90 min wasted on speculative work or wrong-direction commitment. iter-336 would have spent ~3 hours discovering the 2-call chain complexity DURING implementation.
- **Conservative ROI**: ~45× cost savings for ~40 sec of preflight investment. Strongest single-rule ROI in the codified set.

**Memory-write triggers** (3-instance trigger justification):

This rule codifies at 3 instances (iter-331/332/336) instead of the iter-302 6-instance precedent because:

1. **The PATTERN is meta-rule, not new pattern**: preflight-before-design is established at iter-302 6-instance threshold (`feedback_engine_already_does_this`). iter-strategy preflight is the SAME meta-rule applied at higher abstraction layer.
2. **3 instances cover 3 DISTINCT pivot outcomes**: LIVE delivery / mirror reuse / smaller-scope pivot. Shape variety, not recurrence, is the codification trigger.
3. **iter-336 NEW pattern lesson** (`feedback_binary_republish_staleness_audit`) flagged at 1/3 ALONGSIDE this codification — multiple patterns surfaced simultaneously suggests the iter-strategy layer is producing patterns at higher rate than catalog-resolution layer.
4. **iter-334 codification cadence lesson** ("codification iters have highest cost-benefit-ratio") justifies aggressive codification when patterns are at higher-abstraction layers.

If a 4th instance surfaces a NEW pivot outcome shape (e.g., "preflight reveals existing infra is BROKEN, pivot to fix-then-build"), extend the decision-tree table. Don't create a new rule unless the meta-rule itself fails.

**Prospective uses (iter-338+):**

Every iter that involves feature work + existing infra dependency should run the 3-step preflight. Specific upcoming candidates:

- **Combat tab Hardpoint Inspector** (iter-337/338+): iter-336 already preflighted; iter-337 should ride the iter-336 preflight finding (2-bridge-call chain known) and ship a smaller-scope inspector.
- **README capstone iter-365+**: preflight will find iter-322 capstone shape — ride the mirror.
- **Next P2HP audit iter-340+**: preflight will find iter-323 audit format — apply iter-326/327/328 preflight stack at catalog-resolution layer.
- **Future asset class extensions**: preflight will find iter-313 LocateByConvention plugin set + iter-316 extract-on-second-use rule — ride the established pattern.

**Pattern reinforcement:** this rule is the **iter-strategy companion** to:
- `feedback_engine_already_does_this.md` (iter-302 codified) — applies preflight at WIRE-design layer
- `feedback_locate_by_convention_extensible.md` (iter-334 codified) — applies preflight at PLUGIN-design layer
- `feedback_extract_on_second_use.md` (iter-316 codified) — applies preflight at ABSTRACTION-design layer
- `feedback_status_badge_as_inline_docs.md` (iter-311 codified) — applies preflight at OPERATOR-UX layer

iter-strategy preflight is the META-LEVEL of these wire/plugin/abstraction/UX-level preflights. When the iter itself is the unit of decision, apply this rule.

**Cross-link to related codified rules:**

- `feedback_engine_already_does_this.md` (iter-302) — 6-instance precedent for codification cadence
- `feedback_locate_by_convention_extensible.md` (iter-334) — 6-instance precedent for plugin-set codification
- `feedback_extract_on_second_use.md` (iter-316) — abstraction-layer preflight equivalent
- `feedback_status_badge_as_inline_docs.md` (iter-311) — UX-layer preflight equivalent
- `feedback_infra_claim_drift_bidirectional.md` (iter-283) — 5-second-grep discipline, applied at design-time
- `feedback_aob_drift_across_binary_versions.md` (iter-256) — semantic verification before commit, applied at RE-time
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172) — toolchain rule for running the test suites used by preflight verification
---
name: Extract on second use
description: Don't extract a helper at the first concrete use — wait for the SECOND
  consumer. At first-use the right shape isn't visible yet; at second-use the pattern
  is obvious AND the abstraction can be designed around 2 real call sites instead
  of 1 + speculation.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-extract-on-second-use
---

When a piece of logic might be reused, leave it inline at the first concrete use. Extract a helper ONLY when a SECOND consumer needs the same logic. At second-use you have 2 real call sites to design the abstraction around (and the shape is empirically validated); at first-use you'd be designing around 1 real call + speculative future shape.

**Why:** Premature abstraction is one of the highest-cost programming mistakes. At first-use you don't yet know which parts of the code are essential and which are accidental — extracting too early bakes in the wrong abstraction shape, which then has to be reworked when the second consumer arrives. Worse, future consumers tend to push the abstraction's signature in awkward directions to avoid the rework cost. Extract-on-second-use cuts the speculation entirely.

**How to apply:**
- At first concrete use, write the logic INLINE in the consumer (no helper, no abstraction)
- When a SECOND consumer needs the same logic, copy it inline initially — confirm both call sites really do share the same shape
- THEN extract a private helper that BOTH call sites delegate to
- The helper signature should fall out from comparing the two real call sites; if you have to add parameters that "might be needed later," you're still being premature
- Class doc / private helper doc should reference both initial call sites by iter (e.g. "first introduced at iter-N for X; extracted at iter-M for X+Y")

**Instances (3 — codification trigger reached at iter-315):**
- iter-308: `LocateDds` 5-relpath walk shipped INLINE in `UnitIconResolver.LocateDds` (first concrete use; only 1 consumer = unit icons)
- iter-313: `ResolvePortrait` needed the same walk → extracted `LocateByConvention(string filenamePrefix, string assetName)` private helper that BOTH `LocateDds` and `LocatePortraitDds` delegate to. **Helper signature fell out from comparing the 2 real call sites** — only the filename prefix differed.
- iter-314: `ResolveFactionEmblem` (3rd asset class) added with ZERO duplication via `LocateByConvention("i_faction_", factionName)`. iter-315 added 4th asset class (planets) at the same ~3 LoC marginal cost. The abstraction held perfectly because it was designed around 2 real call sites at extraction time.

**Edge cases:**
- **DRY-overzealous teams may push for 1st-use extraction** ("we know it'll be reused"). Resist unless you have 3+ obvious next consumers ALREADY scoped. Speculation is the cost.
- **If you copy the logic at 2nd use and then realize the SHAPES differ slightly**, that's exactly the bug extract-on-second-use is meant to catch. Now you can decide whether to abstract around the union OR keep two specialized impls — informed by 2 real shapes, not 1+speculation.
- **For trivial 3-line helpers**, even 2nd-use extraction may be overkill — copying 3 lines is cheaper than the indirection. The helper extraction cost-benefit kicks in around 5-10 lines of shared logic.
- **Don't pre-design the helper API at 1st use.** If you find yourself thinking "I should make this take a parameter that's currently unused," delete the parameter. Add it at 2nd-use when the 2nd call site demands it.
- **Cross-file extractions follow the same rule**, but the cost of premature extraction is HIGHER (file split + import management). Wait even more aggressively for cross-file.

**Cost-benefit:**
- 1st-use extraction cost: ~5-15 LoC of helper + ~5 LoC of API doc + speculative-shape risk
- 2nd-use extraction cost: ~5-15 LoC of helper + ~5 LoC of doc + 2 real call sites informing shape
- Anti-pattern cost (extract too early, shape wrong, rework needed): ~20-40 LoC of refactor + history-rewrite + reviewer attention
- Compound-interest payoff: 3rd, 4th, 5th consumers each cost ~3 LoC each because the 2nd-use extraction got the shape right

**Cross-link:** This rule pairs with `feedback_engine_already_does_this.md` (don't write code that already exists) and `feedback_optional_default_null_constructor_extension.md` (defer wiring to composition root in a separate iter). All three are "delay commitment until you have 2+ real call sites informing the design."

**Concrete LoC numbers from iter-313→iter-315 case study:**
- iter-308 LocateDds inline: ~12 LoC inside the method body
- iter-313 LocateByConvention extraction: +12 LoC for the helper, -5 LoC inside LocateDds (after delegation), -3 LoC saved on each subsequent asset class
- iter-314 ResolveFactionEmblem: ~30 LoC total (mostly Resolve wrapper + LocateXyz one-liner) — confirmed shape held
- iter-315 ResolvePlanetIcon: ~30 LoC same shape — abstraction validated at 4 plugins
- **If extracted at iter-308**: would have either had a 1-call-site helper (waste) OR speculated about future shape and likely picked wrong (cost = iter-313 rework)
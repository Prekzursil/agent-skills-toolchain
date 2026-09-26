---
name: Event-Driven Subsystem Defer Pattern
description: When SWFOC engine subsystem is event-driven (Observer/polled state machine),
  there is NO direct trigger Lua API. Defer to multi-iter A1.x offset RE — never a
  3-iter mini-arc.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-event-driven-defer-pattern
---

# Event-Driven Subsystem Defer Pattern

**Rule**: When a SWFOC engine subsystem is **event-driven** (Observer pattern, polled state machine, behavior-attached components, monitor-class polling lists), there is **NO direct trigger Lua API** — regardless of how operator-visible the subsystem is. iter-337 preflight stack returns the defer signal; commit to multi-iter A1.x offset RE arc OR durable defer with documented reason.

**Why**: The SWFOC Alamo engine has TWO architectural classes of subsystem:

1. **Command subsystems** (camera/spawning/diplomacy/audio/UI) — exposed via direct Lua API (`Spawn_Unit(...)`, `Camera_To_Follow(...)`, `Make_Ally(p1, p2)`). The iter-302 `feedback_engine_already_does_this.md` rule covers these. ~3-50 LoC bridge wire via DoString.

2. **Lifecycle subsystems** (animation/locomotion/victory-conditions/storyevents/AI-behavior-tick) — event-driven; the engine internally polls/observes state. No Lua API entry point. **A bridge wire requires offset RE + MinHook detour + multi-iter A1.x commit.**

The iter-337 preflight stack reliably detects which class a subsystem belongs to by:
- Searching `rtti_refs` for the relevant class names
- Grepping `docs/lua-api.md` for documented Lua API entry points
- Searching `functions` table for IDA-named `<verb>_<noun>` engine functions

**Negative-result signature** (this rule fires):
- 0 IDA-named functions matching the operator concept (e.g. `trigger_victory`, `play_animation`, `get_locomotor_state`)
- 0 docs/lua-api.md entries
- BUT 1+ RTTI references to a `*MonitorClass` / `*BehaviorClass` / `DynamicVectorClass<*::AwaitingTestType>` event-driven class

**Pattern weighting** (refined iter-427 forward-application):
- **Primary signal: `*BehaviorClass`** — DOMINANT engine idiom, 119 distinct instances in rtti_refs (e.g. LocomotorBehaviorClass, DeathBehaviorClass, CapturePointBehaviorClass, UnitAIBehaviorClass, DamageTrackingBehaviorClass, CorruptSystemsBehaviorClass). Behaviors are attached to GameObjects via QueryInterface and ticked per-frame by the engine. ANY operator concept that maps to a `*BehaviorClass` is event-driven.
- **Secondary signal: `DynamicVectorClass<*::AwaitingTestType>`** — RARE, only 1 instance (`DynamicVectorClass<VictoryMonitorClass::AwaitingVictoryTestType>`). Indicates a polled-test-list architecture (engine iterates the vector each tick checking each test for completion).
- **Tertiary signal: `*SystemClass`** — used for engine-wide subsystems (e.g. AnimationSystemClass at iter-416). Not always in rtti_refs but appears in IDA-named functions. Same architectural implication — engine internally polls/observes state.

**How to apply**:

1. **Run preflight FIRST** (per iter-337 codified rule) before designing or coding any iter targeting an operator-visible feature
2. **Match against the negative-result signature** above
3. If matched: **DO NOT commit to a 3-iter mini-arc**. Either:
   - **Durable defer** to fresh session with documented reason (per iter-414/iter-422/iter-423 honest-defer pattern)
   - **OR commit to multi-iter A1.x arc** (~5 iters: RE offset + bridge MinHook detour + simulator handler + UX wiring + verify) — only if operator priority justifies the cost

4. **If you're tempted to "just try a quick wire"** — STOP. iter-416/422/423 all proved that "quick wire" doesn't exist for event-driven subsystems. The 3-iter mini-arc cost is wasted speculation. Commit fully or defer fully.

**Examples** (3 confirmed instances at 3/3 trigger):

| Iter | Subsystem | Architectural shape | RTTI signal | Outcome |
|---|---|---|---|---|
| 416 | Play_Animation | event-driven (animation system polls model state per tick) | ModelAnimationClass + AnimationSystemClass | DURABLE DEFER |
| 422 | SWFOC_GetUnitLocomotorState | event-driven (LocomotorBehaviorClass polls path state per tick) | 16 Locomotor* classes (Bike/Fighter/Flying/JetPack/etc.) all inheriting LocomotorBehaviorClass | DURABLE DEFER |
| 423 | SWFOC_TriggerVictory | event-driven (VictoryMonitorClass polls vector of AwaitingVictoryTests per tick) | VictoryMonitorClass + StoryEventVictoryClass + DynamicVectorClass<AwaitingVictoryTestType> | DURABLE DEFER |

**Pattern**: ALL 3 instances had the same RTTI shape — `*MonitorClass` / `*BehaviorClass` / `*<*::AwaitingTestType>` — which is the engine's idiom for Observer-pattern subsystems.

**Cost-benefit**:
- **WITHOUT this rule**: ~5 iters of speculative work before the wall is hit at iter 4-5 (RE offset hunt fails). ~3-4 hours wasted per defer-without-preflight.
- **WITH iter-337 preflight + this rule**: ~5-min preflight detects the pattern; durable defer in 1 close-out doc. **~25× cycle-time advantage**.
- **Tracking instances**: each defer extends the empirical evidence base; future operators choosing between A1.x arcs can rank by "is the subsystem command-class or lifecycle-class?" before committing.

**Honest break-out cases** (when this rule does NOT apply):

1. **Operator priority justifies multi-iter cost**: SWFOC_TriggerVictory has highest operator-visible impact (instant-win across all game modes). If an operator commits to the multi-iter A1.x arc, the rule doesn't preclude it — it just ensures the commit is informed.
2. **Subsystem has BOTH command + lifecycle entry points**: e.g. `Make_Ally` is command-class (direct Lua API) but the resulting diplomatic state PROPAGATES through event-driven AI behaviors. The Lua API is enough for the bridge wire; you don't need to RE the propagation paths.
3. **Read-side query has separate Lua API**: e.g. `Get_Health` (iter-167 LIVE) is a direct Lua API even though the underlying health-tracking is event-driven (UnitClass polls behaviors). Read-side getters often DO have Lua API even when write-side trigger does not.

**Cross-reference to other codified rules**:
- **iter-302** `feedback_engine_already_does_this.md`: this rule is the **negative-applicability companion**. iter-302 covers "engine HAS Lua API → DoString roundtrip"; iter-426 covers "engine LACKS Lua API because event-driven → defer or A1.x commit".
- **iter-337** `feedback_iter_strategy_preflight_stack.md`: this rule is the LOOKUP TABLE for the preflight's "no clean Lua API" outcome. Without this rule, every preflight had to reason from scratch about what the negative signal meant. With this rule, the negative signal maps to a known architectural pattern.
- **iter-407** `feedback_static_data_re_extraction.md`: complementary — iter-407 covers "engine has STATIC DATA → extract once + embed"; this rule covers "engine has STATE → cannot extract; must hook".
- **iter-302** + **iter-407** + **iter-426** together cover the full "what does the engine provide" taxonomy: live API + static data + event-driven state.

**Codification trigger**: 3/3 (iter-416 / iter-422 / iter-423). Pattern stable across 3 distinct engine subsystems with identical RTTI signature shape (`*MonitorClass` / `*BehaviorClass` / `DynamicVector<*::AwaitingTestType>`).

**Future application**:
Future deferred candidates likely matching this rule:
- `SWFOC_GetUnitVelocity` — UnitClass position-tracking is per-tick (event-driven)
- `SWFOC_TriggerDefeat` — likely uses same VictoryMonitorClass infrastructure as iter-423
- `SWFOC_TriggerStoryEvent` (with binding to specific event classes) — story system is observer-driven
- `SWFOC_GetCurrentMission` — mission state is event-driven via MissionManagerClass

For each of these, run the iter-337 preflight FIRST. If the signature matches, defer per this rule.

**21st codified rule** in the project's master-loop codification track. 7th Tier-4 meta-rule (rules about how rules are applied). Continues iter-302 → iter-407 → iter-426 architectural taxonomy of "what does the SWFOC engine provide."
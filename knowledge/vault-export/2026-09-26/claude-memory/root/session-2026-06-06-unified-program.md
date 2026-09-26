---
name: session-2026-06-06-unified-program
description: THE COMPLETE BATTLE CATS CONSOLIDATION + FULL-REWRITE PROGRAM — triage
  plan evaluated, user annotations + scope expansions captured, ready for e2e ultracode
  implementation
metadata:
  type: project
permalink: main/claude-memory/root/session-2026-06-06-unified-program
---

## Status: Triage complete. User authorizing e2e ultracode implementation.

This is the **master program**: complete the Battle Cats (EN 15.3.0) consolidation + a full game rewrite (V2 overhaul: remove lootboxes/ads/timers/Officer-Pass/energy; new magnification system; economy redesign; 45k-catfood ban lifted; 19-deck cap removed; no in-game cheat menu, dev-only POC). Ship as:
- **V0** (live now): event_0 data patches + enable-combined hook
- **V1** (GUI MVP): deck/cat/filter editors + search
- **V2** (ranked solver): team suggester with traits/combos + win-confidence + availability-aware recommendations
- **V3** (polish): explainability prose, guides, bios, combo-book, user-rank system
- **V2-overhaul** (parallel): the aggressive game rewrite

All backed by a **durable, reconciled toolkit** on origin/main (consolidate-unified merged 2026-06-05).

## Key artifacts & status

**Built & durable (on origin/main):**
- Event_0 codec + never-drop union builder (handles 11-event-drop bug, data-backed) + 593-event taxonomy
- Guerrilla/Aku window RE (fully decompiled + live-validated)
- `.unlock` APK static patches (4 verified live in memory; no build artifacts in this worktree)
- GUI trainer shell (5 panels, 456 test functions, orbs editor working)
- Offset re-acquisition recipe + CI draft
- Full docs reconciliation + asset-pipeline research

**Designed-not-built (zero code, exists as design docs):**
- Deck/cat/filter editors, the team solver, event-unlock GUI panel, type-aware event_0 builder, asset fetch pipeline

**Broken/missing:**
- GUI import `bc_event_index:build_event0_monthly_allon` (doesn't exist) — import fails
- `.unlock` APK + `tools/apk-build/` not in this worktree (built in a *different* checkout, not migrated)

## User's annotated scope + major additions

From the triaged plan (user edits):

### V1 GUI: now includes
- Verbose normal inventory (inspect + simulate leveling/orbs/talents/forms, show caps/mechanics)
- Advanced filter (name, category, year-month-day-of-week, type, clear UI)
- Per-event on-demand unlock toggle
- Crown grid display (transposed correctly)

### V2 overhaul (parallel, user-approved): **aggressive rewrite**
- **Remove:** lootboxes (all variants), ads, timers (energy/special-event cooldowns), Officer-Pass, cf-gated content, the 45k-catfold cap, the 19-deck cap, all pay-to-win gates
- **Redesign economy:** treasure/magnification (user wants "new levels" in magnification that don't exist in live — RE-required; remove live magnification's cap/DPS-nerf)
- **Add:** unit-info/guides/bios/combo-book (user-contributed, in-game), user-rank system, non-root save copy in/out, save-manager (unlimited slots, cloud/gdrive, server-side multi-ID, previews)
- **No in-game cheat menu** (dev-only, build-time POC, zero runtime cheats)
- **Asset acquisition:** reject the "gone/black-screen" ceiling — search GitHub/old versions; all stages playable even without live assets

### Meta-lesson (critical epistemics fix):
User flagged: *"keeping it as a truth forced us not to understand it properly since we refused to look at what couldn't be possible."* Applies to: Aku live-reroll (was it wrong?), dojo-blank (HGT or injection?), RE-I7 (instant-recruit — abandoned or never-investigated?), AS-D2 (asset-ceiling — true or too-early concession?). **Bake into the implementation: "assume nothing is settled; re-derive from evidence" per RE lane.**

## Corrected overclaims (carried forward)

From the reconciliation workflow:
1. Union builder = never-drop primitive, **not** full recurrence fix (still widens 24020/24038/16000/1164/1402 to always-on) → user needs to choose: ship-as-is or fund the full `EVT-WU9` fix
2. "456 tests pass / 100% coverage" on trainer-gui is **UNVERIFIED** in this worktree (no PySide6/pytest-qt, no GUI venv; was verified in the other checkout)
3. `.unlock` APK + apk-build aren't in bc-toolkit-unified-wt (built elsewhere, not migrated)
4. GUI broken import blocks any v1 build until fixed

## The triage table + decisions (user's annotations marked up)

~119 work units across 9 domains (GUI, Events, V2-overhaul, Consolidation, Assets, Toolkit, RE, Save-edit, Docs) with DO/DEFER/DROP marked. Key decisions:

- **F-1 (Solver scope):** User chose: "structural MVP first (trustworthy), then ranked-solver (gated), then corpus (wiki-grade)"
- **F-2 (Gauntlets allon):** Test variant live on device; Dojo-blank check pending user's eyes
- **F-3 (Deletion):** source/ (1.5G) + WSA (8.8G) retire → gated on RECONCILE-MANIFEST + user confirm, reversible
- **F-11 (Execution):** User authorizing e2e ultracode (max agents/subagents, highest effort, 100%-rigorous)

## Next: The interview (user confirmed ready)

Four structural decisions needed to set implementation direction, then I ask the deeper questions on V2 economy/magnification specifics.

---

## Resume plan (next session)

1. **Interview user on the 4+N structural decisions** (the ones in UNIFIED-MASTER-TRIAGE-PLAN.md §F, + V2 economy deep-dives)
2. **Mark up the triage table** with user's final priorities
3. **Launch the biggest ultracode workflow ever**
   - Research lanes: every hypothesis re-tested (Aku, dojo, RE-I7, assets, V2 economy magnification) from fresh evidence
   - Design lanes: full specs for every V1/V2 feature
   - Build lanes: ~50–100+ agents orchestrated end-to-e2e (the GUI, the V2 overhaul, asset pipeline, save-manager, game mechanics redesign, the solver)
   - Review lanes: every feature adversarially verified + integration tested
   - Synthesis: merged code + durable docs

4. **All on origin/main in parallel:** GUI builds on v1-shell, V2-overhaul in parallel (no code collision), asset pipeline feeds both
5. **Per the user's rule:** "do everything thoroughly, hundreds of agents, 100% sure" → no compromise on rigor, no cut corners

---

## Key files & branches

- **origin/main** (`193cdd7`): the canonical toolkit, all research/plans/RE docs, trainer-gui shell, event_0 builders
- **bc-toolkit-unified-wt (worktree on consolidate-unified):** the working branch
- **battlecats-toolkit (worktree on ralph-hardening):** the other session's RE tools (don't touch)
- Transcript: `.jsonl` in the project folder has every prompt + every finding

## Critical edge cases & re-test hypotheses

- **Aku timer (was solved; test under V2 economy redesign):** sub_4F1C40 window array, does the budget/spawn system change how reroll works?
- **Dojo-blank (pending gauntlet test):** user's hypothesis says HGT/time-change, not injection — the device test is live, Dojo check pending
- **RE-I7 Instant-recruit (was abandoned; user wants re-eval):** investigate from fresh evidence, no prior assumptions
- **Asset ceiling (user rejects "gone"):** systematic GitHub/version-history search before accepting loss
- **Magnification redesign (V2, RE-required):** what's the live cap/formula? What new levels can exist?

---

## The user's final word on orientation

*"do everything thoroughly, hundreds of agents, 100% sure so that this will be done throughly"*

This is maximal-rigor, no-cut-corners, full-ultracode mode. Commit fully.
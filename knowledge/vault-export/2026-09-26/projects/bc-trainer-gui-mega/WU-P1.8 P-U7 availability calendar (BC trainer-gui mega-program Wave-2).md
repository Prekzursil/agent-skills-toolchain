---
title: WU-P1.8 P-U7 availability calendar (BC trainer-gui mega-program Wave-2)
type: note
permalink: main/projects/bc-trainer-gui-mega/wu-p1.8-p-u7-availability-calendar-bc-trainer-gui-mega-program-wave-2
tags:
- battlecats
- trainer-gui
- mega-program
- wave-2
- availability-calendar
- guerrilla
---

# WU-P1.8 — P-U7 event/availability calendar panel

Built 2026-06-17 on `feat/mega-program-v1` (shared worktree
`D:/ReverseTools/Android/bc-toolkit-build-wt`, project root
`tools/trainer-gui/`). GREEN, 60 tests, 100% line+branch on all 3 new modules.

## What it is
Month/week availability calendar over the rotating-window schedule (the SOLVED
6×24B guerrilla/Aku array) + Aku realm + monthly + collab/behemoth windows, with
"Available now · closes in Xh" / "Opens in Xh" badges and one-click jump-to-stage.
METRIC = time-to-find "what's live now" (one glance: rows sort soonest-first).

## Files created (no shared files touched)
- `trainer_gui/services/availability_schedule.py` — PURE LOGIC (stdlib only,
  import-safe without Qt). `RotatingWindow` (period/offset/duration, FLOOR-div
  phase so pre-anchor times are correct), `FixedWindow` ([start,end)),
  `decode_guerrilla_array(blob)` (144 bytes = 6ch×24B, state at **byte +1**,
  non-zero=available; raises on wrong length), `AvailabilityState.badge_text`,
  `humanize_duration` (1d 2h / 1h 30m / 45m, clamps neg→0m), `build_schedule(...,
  sort_by_soonest)`. 100% l+b.
- `trainer_gui/widgets/availability_calendar_panel.py` — Qt pure-view
  (StagesPanel/EventUnlockPanel idiom): `rows()`/`row_model()`/`badge_token()`
  pure+tested; table-driven paint-free; `jumpToStage=Signal(int)`;
  CalendarView.MONTH/WEEK horizon. Consumes Wave-1 `theme/trait_tokens`
  READ-ONLY (TRUST_TIER_TOKENS: Tier-1 shield = available-now, community book =
  pending — distinct glyph+shape, colour-free badge). Qt-event slots
  (`_on_cell_activated`/`_on_view_changed`) behaviorally tested via real signal
  emission (not pragma'd). 100% l+b.
- `trainer_gui/controllers/availability.py` — thin QObject (NOT BaseController:
  pure compute, no device/IO). Injected `clock: Callable[[],int]` (NEVER
  time.time; `_wall_clock` default is `# pragma: no cover`). `refresh()` →
  `scheduleRefreshed(list)`; `request_jump` → `jumpRequested(int)`. Behavioral
  test drives an advanceable `_FixtureClock` proving "Opens in 5h"→"1h". 100% l+b.

## Guerrilla reader on 15.3.0
Decoder is layout-stable (decodes a raw 144-byte blob, not a memory address), so
it is version-stable; only the live device base offset `gameState+4536` (out of
scope — no device/IO this WU) is version-specific. Full 15.4.1 re-validate =
version-legacy. Layout from memory note [[battlecats-guerrilla-window-re]]:
6×24B @ gameState+4536, 10800s windows, getter sub_4F1E20 → byte +1.

## SHARED_FILE_NEED (for the serial integrator)
main_window.py: construct `AvailabilityController(entries, clock=<device/wall>)`
+ `AvailabilityCalendarPanel(entries, now_epoch)`; wire
`controller.scheduleRefreshed → panel.set_entries`-equivalent re-render (or panel
holds entries and a `set_now`); `panel.jumpToStage → controller.request_jump`;
`controller.jumpRequested → StageBreakdownPanel/stage browser select`. Add an
"Events/Calendar" section. Entries built from guerrilla reader + event_catalog.

## TDD/quality
Tests-first (watched red→green each module). ruff clean on declared files only.
Offscreen Qt (QT_QPA_PLATFORM=offscreen). Unique COVERAGE_FILE=.cov.p18,
-p no:cacheprovider, ran only my modules. Left uncommitted (integrator commits).

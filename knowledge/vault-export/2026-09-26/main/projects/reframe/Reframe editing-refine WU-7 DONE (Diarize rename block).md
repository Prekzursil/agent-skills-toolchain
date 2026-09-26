---
title: Reframe editing-refine WU-7 DONE (Diarize rename block)
type: note
permalink: main/projects/reframe/reframe-editing-refine-wu-7-done-diarize-rename-block
---

# Reframe editing-refine WU-7 — DONE (2026-06-20)

Branch `feat/editing-refine-design`, commit `bc3aba4` (pushed; 4cbed6f..bc3aba4).

WU-7 = per-speaker rename block in `app/renderer/src/features/Diarize.tsx`. Renderer-only edit.
- Added `drafts` state (Record speaker->typed name), one text input per `SPEAKER_NN`, "Apply names" button.
- `applyRename`: builds `{SPEAKER_NN: friendly}` mapping for trimmed/non-empty/changed names only; no-op if empty; calls direct RPC `diarize.rename({videoId, mapping})` -> `{transcript}` (NOT a job, resolves on rpc promise); refreshes labels from returned `speakers` roster via `extractSpeakers`; error branch sets alert.
- `run` resets drafts on (re)diarize so drafts never leak across runs.
- Files: `Diarize.tsx`, `Diarize.test.tsx` (+281 lines). 13 new tests.

Gates: vitest 1162 tests pass, coverage 100/100/100/100 (Diarize.tsx 100%); tsc 0; oxlint 0; biome 2.5.0 check clean. Scoped commit (only 2 files).

GOTCHA (cost me one red run): jsdom controlled-input updates need React's tracked native setter — `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,val)` then dispatch `input` event. Plain `input.value=...` doesn't fire React onChange reliably. The repo's existing pattern (Subtitles.test.tsx:165) confirms this; added a `typeInto` helper.

diarize.rename RPC contract (WU-4/WU-5): `features/diarize.py:339 rename()` direct return; pure `rename_speakers` (diarize.py:179) rewrites segments+roster immutably; registered `handlers? -> register_all reg("diarize.rename", service.rename)` at diarize.py:449.

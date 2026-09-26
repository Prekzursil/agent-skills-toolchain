---
title: Reframe editing-refine WU-6b DONE (Workspace mount)
type: note
permalink: main/projects/reframe/reframe-editing-refine-wu-6b-done-workspace-mount
---

# Reframe editing-refine WU-6b — DONE (2026-06-20)

Branch `feat/editing-refine-design`, commit 4cbed6f (pushed). WU-6b = mount Refine.tsx into Workspace so the panel is actually openable (prevents shipping dead-coded behind the 100% gate).

## Changes (2 files, scoped)
- `app/renderer/src/views/Workspace.tsx`: added `const Refine = lazy(() => import('../features/Refine'))`; `WORKSPACE_TABS` entry `{ id: 'refine', label: 'Refine' }` placed directly after `diarize` (index 3); `case 'refine': return <Refine videoId={video.id} />;` in renderPanel().
- `app/renderer/src/views/Workspace.test.tsx`: `vi.mock('../features/Refine', () => stubPanel('Refine'))`; added 'Refine' to ordered-tabs assertion (after Diarize); added `['refine','Refine']` to the per-case render table.

## Tab order now
Transcribe, Subtitles, Diarize, **Refine**, Tracks, Convert, Short-maker, Timeline, Timeline export, Recipes, Assets. (WU-8 docs must record this position.)

## Gates (all green)
Renderer 100/100/100/100 (7651 stmts, 2635 branches, 459 fns); tsc clean; oxlint + biome 2.5.0 clean. Sidecar untouched (renderer-only WU). Prior WUs 1-6 already on branch; WU-7 (Diarize rename block) + WU-8 (docs) still pending.

## Notes
- Refine default export takes `{ videoId, api }` — matches `<Diarize videoId={video.id} />` shape.
- Fresh clone needed `npm ci` in app/ before vitest could load config.

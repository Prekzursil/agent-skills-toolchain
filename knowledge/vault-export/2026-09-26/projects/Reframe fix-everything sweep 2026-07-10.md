---
title: Reframe fix-everything sweep 2026-07-10
type: note
permalink: main/projects/reframe-fix-everything-sweep-2026-07-10
tags:
- reframe
- make-shorts
- bug-sweep
- compaction-checkpoint
---

# Reframe "fix everything" sweep — 2026-07-10

Branch `fix/local-llm-model-path` @ HEAD (main worktree C:\Users\Prekzursil\Documents\GitHub\Reframe). **BOTH suites 100% green**: sidecar 5618 tests, app vitest 2964 tests, 100% branch coverage each. 17 clean commits.

## Star bug FIXED + PROVEN
Root cause of "No candidates were proposed": `shortmaker.select` never transcribed (renderer called it cold). Fix `d20ed80`: auto-transcribe+persist inside the select job (shared `_transcribe_and_persist`). **E2E proven**: real pipeline on a 40s clip → real whisper → claudeshorts reframe → valid 1080x1920 mp4 (LLM stubbed = #268 path; qwen3-4b.gguf + llama-server present on D:\Reframe\data).

## Discovery + verification (2 read-only ultracode workflows)
14-dimension discovery → 35 findings, 3 HIGH. Adversarial verify of the 32 medium/low → **24 real, 8 false-positives pruned** (pyannote:247, ShortMaker.tsx:606/686, MakeShorts:201, useJob:217/218, Edit:87, captionCustomizer:54). Fix-hints saved: scratchpad/real_fixhints.json.

## FIXED (18 findings, 17 commits)
3 HIGH: caption total_sec (ca1197a), select TEXT-consent (3074902), + Make-Shorts.
Medium/low (14): 3 offline guards (2169fa0), library audioTracks + export progress (a284b68), trackId cross-video (345541c), stale-index fingerprint (1f18737), karaoke flatten (5c759f1), CaptionBox a11y keyboard+24px+tokens (3f90c72), ShortMaker cancel (76d96f1), RPC timeout + bootstrap banner (5639464).

## REMAINING 10 (the HARDEST — need real-integration / fresh context)
Sidecar: tracks_audio:472/242/504 (audio-stream-index model — needs real-ffmpeg validation, mocks hide the no-such-stream failure), bootstrap:219 (read-only-install pip — needs real-pip test), media_ops:51 (add captionPolish/captionSpeakerLabels toggle to app captionPreferences.ts).
App: CaptionedClip:21 (vendor/remotion-captions hookTitle — types.ts schema + Root.tsx), Player:208 (proxy-swap seek — jsdom can't test real readyState/load()), main.ts:806 (proxy-build promise never settles on sidecar crash), _api:199 (surface sidecar.status='down' to in-flight waits), ReframeOverridePanel:73 (mount the built-but-unwired panel + wire reframe.shotPlan/applyOverrides).

## Codex
User ran Codex in parallel then STOPPED it; its 161-file partial sweep is STASHED (`git stash` "codex-sweep-wip-2026-07-10", full patch scratchpad/codex_full.patch) — recoverable for salvage, set aside for a clean verified result.

## Next
USER build step (rebuild packaged app with the 18 fixes → test working Make-Shorts). Then the hard 10 as a focused follow-up.

## Lessons
- `| tail` / `; echo` masks pytest exit code (pipe returns last cmd's status) → capture `$LASTEXITCODE` before any pipe. Bash tool broken this session → PowerShell.
- Workflow `args` can arrive as a STRING → `typeof args==='string'?JSON.parse(args):args`. Background-task output files come back EMPTY here → reconstruct from journal.jsonl.
- app vitest coverage gate is renderer-only (`coverage.include:['renderer/src/**']`); app/main (main.ts/sidecar.ts) tests RUN but aren't 100%-gated.
- Two agents on one uncommitted worktree = pervasive collision (esp. test files); isolated `git worktree` off the green base is the clean parallel path.

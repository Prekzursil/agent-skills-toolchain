---
title: Reframe native smooth speaker-tracker + claudeshorts default (2026-06-26)
type: note
permalink: main/projects/reframe/reframe-native-smooth-speaker-tracker-claudeshorts-default-2026-06-26
tags:
- reframe
- jitter
- speaker-tracking
- claudeshorts
- bugfix
- no-wsl
---

# Reframe native smooth speaker-tracker + claudeshorts default (2026-06-26)

Branch `feat/reframe-quality` @ origin, commit `2f7315b` (fast-forward atop `9e533f1`). PR-ready.

## PROBLEM (user-shown frames)
The prior jitter commit `9e533f1` ("deadzone + static-bias + smooth-interp") made the 9:16 crop DRIFT OFF the speaker (he ends at frame edge / empty studio shown), worst on profile shots. The ORIGINAL tracked but jittered. NEITHER was right. Root: `apply_deadzone` HELD the crop + coarse `KEYFRAME_MIN_DELTA_FRAC/STATIC_EPSILON_FRAC=0.06` + averaging-to-center collapsed off-center subjects toward frame center; and face-only detection -> empty-samples -> CENTER crop the moment a face turned.

## FIX (sidecar/media_studio/features/reframe_claudeshorts.py)
- **DETECTION fallback chain** (`_make_subject_finder`, stateful per-frame): FACE (mediapipe model_selection=1 / haar) -> PERSON (`_person_center`, cv2 HOG `getDefaultPeopleDetector`, node-free/no-download) -> MOTION (`_motion_center`, inter-frame absdiff threshold 18, intensity-weighted column centroid). So the SPEAKER is located on profile/turned frames instead of center-cropping.
- **⭐ GOTCHA: cv2 HOG `detectMultiScale` SEGFAULTS on frames smaller than the 64x128 window.** Guard `_person_center` with `_HOG_MIN_W=64/_HOG_MIN_H=128` (return None below). `_motion_center` guards `prev.shape != img.shape` (scene-cut) -> None. Both found via the test segfault, not docs.
- **SMOOTHING**: `SMOOTH_ALPHA=0.15` heavy EMA, now ZERO-PHASE (`_ema_forward` forward + backward, averaged) so the steady track has no directional lag. `smooth_centers` keeps the public signature.
- **INTERPOLATION**: `KEYFRAME_MIN_DELTA_FRAC=0.004` (fine) -> piecewise-linear `x(t)` via existing `build_crop_x_expr`, no stepped teleports. `WINDOW_SEC=1.0`, `MAX_WINDOWS=90` (~1 sample/sec).
- **REMOVED static-bias**: `apply_deadzone` + `DEADZONE_FRAC` DELETED. `compute_plan`: `MIN_SUBJECT_HIT_FRAC=0.15` trust gate; static branch centers on the subject's track x (not avg-to-center); moving branch opens crop at `kfs[0]["x"]` (first tracked pos, not frame center). `STATIC_EPSILON_FRAC=0.01` (only collapse when genuinely never moving).

## DEFAULT ENGINE FLIP (features/reframe.py) — no WSL by default
`resolve_engine_name`: `auto`/blank/None -> **claudeshorts** with ZERO WSL probe (no notice). `verthor` (WSL2) is EXPLICIT opt-in only (still fails loud when WSL absent). Removed `make_fallback_notice`/`REFRAME_FALLBACK_NOTICE` (dead). shortmaker drops the fallback-notice surfacing. export_presets default stays `"auto"` (now = claudeshorts). vidstab default-on (`stabilize` default True) from `9e533f1` PRESERVED via 3-way merge.

## TDD / GATE
- Tests: off-center subject -> crop on SUBJECT not frame-center; profile/weak-face -> person/motion fallback locates him; smooth interp (eval-free recursive `_eval_crop_x` oracle proves bounded per-step travel = no teleport); claudeshorts default no-WSL (`_never_which` asserts no probe).
- WSL gate `cd /mnt/c/.../sidecar && /tmp/msv/bin/python -m pytest --cov=media_studio --cov-branch --cov-fail-under=100 -q` = **100.00%, 4095 passed**. Pre-commit (ruff lint+format, gitleaks) clean.

## PROCESS GOTCHAS
- Bash tool = Git Bash NOT WSL; run the gate via `wsl.exe -e bash -lc '...'` ( `/tmp/msv` + `/mnt/c` are WSL-only paths).
- `feat/reframe-quality` ALREADY EXISTED on origin (had `9e533f1`). Branched fresh off main -> non-ff push reject. Resolved by `git rebase origin/feat/reframe-quality`, `git checkout --theirs` (=my commit) for the 2 reframe-conflict files (my approach supersedes deadzone), kept the auto-merged shortmaker/stabilize (vidstab default), pushed fast-forward. NO force-push.
- TODO after merge: v0.1.1 re-release + installer rebuild (per the 2026-06-25 jitter note).
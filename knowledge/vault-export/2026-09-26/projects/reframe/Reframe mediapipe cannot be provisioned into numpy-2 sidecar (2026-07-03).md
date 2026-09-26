---
title: Reframe mediapipe cannot be provisioned into numpy-2 sidecar (2026-07-03)
type: note
permalink: main/projects/reframe/reframe-mediapipe-cannot-be-provisioned-into-numpy-2-sidecar-2026-07-03
tags:
- reframe
- provisioning
- mediapipe
- blocker
- numpy
- no-silent-fallback
---

# Reframe: mediapipe is NOT reliably provisionable into the numpy-2.5.0 sidecar env

WU `fix/reframe-hardening` first-run-provisioning. Empirically verified 2026-07-03 (real `pip install --target` on py3.12 + py3.14):

## HARD FINDING (decisive, tested)
- `reframe_claudeshorts._make_face_finder` uses the LEGACY mediapipe Solutions API: `mp.solutions.face_detection.FaceDetection(model_selection=1, ...)`.
- mediapipe versions that STILL ship `solutions` are **≤ 0.10.21** and declare **`numpy<2`** (0.10.18/0.10.20/0.10.21 all pin numpy<2; 0.10.14 is numpy-unpinned but pre-numpy2, cp312 wheel built against numpy 1.x ABI).
- mediapipe **0.10.31+** (numpy-2 compatible, `py3-none` wheel) **REMOVED `solutions` entirely** — pkg has only `tasks/` + `modules/`, `hasattr(mp,'solutions') == False`. Confirmed on BOTH py3.12 and py3.14: `AttributeError: module 'mediapipe' has no attribute 'solutions'`.
- The sidecar env is HARD-pinned `numpy==2.5.0` (ctranslate2 4.8.0, kokoro-onnx, av, onnxruntime need numpy 2.x).
- => No mediapipe version simultaneously (a) provides `mp.solutions.face_detection` AND (b) is numpy-2.5.0 compatible.

## CONSEQUENCE
Pinning `mediapipe==0.10.35` (my initial attempt) installs a solutionless mediapipe → `detect_backend()` returns "mediapipe" → `_make_face_finder` raises AttributeError at job time → caught by `except Exception` → **silent haar fallback**. That is a NO-SILENT-FALLBACK violation + faking the fix. REVERTED it. Also note: mediapipe was NEVER in requirements-sidecar.txt nor the dev venv, so the app has ALWAYS used haar; the Solutions branch is effectively dead code.

Bonus opencv note: mediapipe depends on `opencv-contrib-python`; scenedetect on `opencv-python`; both ship `cv2`. Unpinned, contrib resolves to 5.x while opencv-python stays 4.13.0.92 → mismatched-version double-cv2. Pinning BOTH to 4.13.0.92 resolves cleanly (verified) — but moot once mediapipe is dropped.

## RECOMMENDED FOLLOW-UP (separate reframe-engine WU, needs design)
To actually get mediapipe-quality face detection under numpy 2: migrate `_make_face_finder` mediapipe branch from Solutions → **mediapipe Tasks API** (`mediapipe.tasks.python.vision.FaceDetector`, blaze_face_short_range `.tflite`). Requires: pin mediapipe 0.10.31+ (numpy-2 ok), register the `.tflite` as a sha256-pinned asset, add it to first-run provisioning, adapt bbox (Tasks returns ABSOLUTE px bbox vs Solutions normalized `relative_bounding_box`), and 100% branch coverage on the new path (reframe_claudeshorts is in the media_studio 100% gate). Until then haar is the honest baseline detector (a real detector; only collapses to center when NO face is found).

## WHAT SHIPPED in this WU instead (all clean, numpy-2-safe)
1. S3FD + LR-ASD weights (`lightasd-s3fd`, `lightasd-asd`) added to `bootstrap.default_first_run_assets()` — the real multispeaker "silent center-crop" provisioning fix (were registered but never in the first-run set).
2. `verify_provisioned()` fail-loud gate + `.first-run-complete.json` marker written only after full provision; `main.ts` gates first-run on the marker (not the env sentinel) + degraded-start-if-env-exists so a re-provision failure never bricks a working install. Closes the half-provisioned-silent-app trap (env sentinel was written mid-run).

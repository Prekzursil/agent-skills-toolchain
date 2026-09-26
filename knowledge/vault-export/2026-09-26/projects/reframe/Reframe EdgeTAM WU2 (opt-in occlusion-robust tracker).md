---
title: Reframe EdgeTAM WU2 (opt-in occlusion-robust tracker)
type: note
permalink: main/projects/reframe/reframe-edge-tam-wu2-opt-in-occlusion-robust-tracker
tags:
- reframe
- edgetam
- v1.2.0
- media-studio
- tracking
---

# Reframe EdgeTAM WU2 (opt-in occlusion-robust tracker)

Integrated EdgeTAM as an OPT-IN speaker-tracking backend for the claudeshorts reframe engine on `Prekzursil/Reframe` branch `feat/v1.2.0` (PR #253 -> main). DONE: quality lean gate CI SUCCESS on HEAD e6b34e4.

## Observations
- [design] DEFAULT stays per-frame YuNet face detector; `settings["reframeTracker"]="edgetam"` opts in. EdgeTAM unavailable is NOT a degradation of the default. `reframeTracker` is a free-form runtime settings key (like modelsDir/verthorScript), NOT the `reframeEngine` preset selector in export_presets.py.
- [no-silent-fallback] Opted-in + torch/cv2/checkpoint missing => typed `EdgeTamBackendUnavailableError` (subclass of ClaudeShortsBackendUnavailableError) raised LOUD up front via the compute_plan backend probe (`_backend_probe = lambda: detect_backend(settings=self._settings)`). Never a quiet revert to YuNet.
- [asset] EdgeTAM checkpoint ships IN facebookresearch/EdgeTAM as a 56 MB git blob (NOT LFS). Pinned via GitHub-raw + 40-hex commit `7711e012a30a2402c4eaab637bdb00a521302c91`; sha256=`ed2d4850b8792c239689b043c47046ec239b6e808a3d9b6ae676c803fd8780df` (56,116,523 B). Apache-2.0 (commercial OK; "Our mix" excludes SAM2 internal data). manifest.py `_register_edgetam()`, size_mb=53.5, dest models/edgetam.pt.
- [6GB] RealEdgeTamTracker.release() frees model + torch.cuda.empty_cache between detect and encode stages (mirrors reframe_multispeaker_backend).
- [coverage] 100% line+branch. Heavy backend reframe_edgetam_backend.py RealEdgeTamTracker `# pragma: no cover`; import surface covered by test_phase8_backend_surfaces.py. All EdgeTAM seams (importer, checkpoint resolver, tracker_factory) MOCKED -> no torch/EdgeTAM/download needed.

## CI gotchas (COST REAL RE-PUSHES — remember)
- [gotcha] LOCAL env had torch (py3.14) so an e2e test that let the engine's real `_backend_probe` import torch PASSED locally but FAILED CI (py3.12, no torch): ModuleNotFoundError. FIX = mock detect_backend / never let a test import the real heavy stack. VERIFY torch-independence locally with `python -c "import sys; sys.modules['torch']=None; import pytest; pytest.main([...])"`.
- [gotcha] CodeQL (a SEPARATE required check, not the `quality` lean gate) flagged `open(argv[-1],"wb")` in a test frame_runner as py/path-injection (high). cv2.imwrite(argv[-1], ...) is NOT flagged — use it. Inspect the exact new-alert locations via check-run annotations: `gh api repos/.../check-runs/<id>/annotations`. PR #253 CodeQL has 3 PRE-EXISTING high alerts (app/main/main.ts:481/584, sidecar/runtime_setup/bootstrap.py:505) failing since WU1/WU3 — outside this WU's files; mergeStateStatus BLOCKED by them.
- [gotcha] Bash-tool heredoc with an apostrophe in the body ("compute_plan's") => "unexpected EOF looking for matching quote". Write commit msgs / test blocks to a scratch file and `git commit -F file` / `cat file >> target`.
- [env] Local Windows: 4 test_director_render_integration drawtext tests fail with Fontconfig "Cannot load default config file" + ffmpeg 0xC0000005 — ENVIRONMENTAL, green on CI ubuntu.

## Relations
- part_of [[Reframe v1.2.0]]
- relates_to [[feedback_bc_re_dont_overcomplicate]]

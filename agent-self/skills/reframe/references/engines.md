# reframe engines

## Engine 2 — verthor (PRIMARY, verified 2026-06-11)
- Repo: `KazKozDev/auto-vertical-reframe` @ `33ac38d` → `D:\tools\reframe\verthor` (MIT).
- Venv: `~/.local/share/reframe/verthor` (WSL, ~8 GB, CUDA torch — `cuda=True`).
- Pipeline: PySceneDetect → YOLOv11-seg + ByteTrack → MediaPipe + handcrafted saliency → smoothed
  camera path → ffmpeg (libx264).
- Verified: `demo_source.mp4` (16:9) → `engine2_out.mp4` = **1080x1920 h264 + aac**, 24fps, 5.65 MB.
- Flags locked: `--saliency-model handcrafted` (never `deepgazemr` = torch.hub RCE), `--video-encoder libx264`.

## Engine 1 — claude-shorts (comparison, pending build)
- Repo: `AgriciDaniel/claude-shorts` @ `a369fad` → `D:\tools\reframe\claude-shorts` (MIT).
- Full pipeline: faster-whisper transcribe → Claude segment scoring → MediaPipe reframe
  (`compute_reframe.py`) → Remotion animated captions → ffmpeg export.
- Reframe-only vs Remotion-needed: see `D:\tools\reframe\ENGINE1_BUILD_RECIPE.md` (from the fan-out).
- Build = Wave-2 follow-up; gives the side-by-side comparison + burned-in captions.

## Choosing
- Default / fastest / cleanest subject-track: **engine-2 (verthor)**.
- Want animated karaoke captions or the long-video→clip scoring pipeline: **engine-1 (claude-shorts)**.

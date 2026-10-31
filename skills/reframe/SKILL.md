---
name: reframe
description: Reframe horizontal 16:9 video into vertical 9:16 (1080x1920) with automatic
  subject tracking - Shorts, Reels, TikTok. Use to convert or crop a landscape video
  to vertical, follow a moving subject, or turn long footage into a portrait clip.
  GPU via WSL2. NOT for a plain aspect change with no tracking (use video-resize-aspect).
license: 'MIT (skill). Engines: verthor + claude-shorts are MIT (vendored under D:\tools\reframe).'
permalink: dqverify-repo-20261013/skills/reframe/skill
---

# reframe — horizontal to vertical 9:16

Turns 16:9 footage into subject-tracked 1080x1920 vertical video. Runs in WSL2 Ubuntu (GPU: RTX 4050).

## Engine 2 — verthor (primary, verified)

Scene-aware reframe: PySceneDetect → YOLOv11-seg + ByteTrack → MediaPipe face/pose + saliency →
smoothed virtual-camera pan/zoom → ffmpeg encode. Emits 1080x1920 H.264 with audio intact.

**Run (from a FILE — never pipe the script in):**
```
wsl -- bash /mnt/c/Users/Prekzursil/source/agent-skills-toolchain/skills/reframe/scripts/reframe.sh IN.mp4 OUT.mp4 preset
```
- Run the script from a file, NOT `... | bash`: verthor/mediapipe read stdin, so a piped script gets
  consumed and corrupts after the verthor line. If you see a `\r` parse error, normalize once:
  `wsl -- bash -lc "sed -i 's/\r//g' <script>"`.
- Paths are WSL paths: Windows `D:\x.mp4` → `/mnt/d/x.mp4`.
- `<preset>`: `talking_head` (default) | `sports` | `pets` | `cars`.
- Or invoke verthor directly:
  `wsl -- bash -lc "source ~/.local/share/reframe/verthor/bin/activate && cd /mnt/d/tools/reframe/verthor && python -m verthor <IN> <OUT> --preset talking_head --saliency-model handcrafted --video-encoder libx264"`

**Safety / pinned choices (do not change):**
- `--saliency-model handcrafted` ALWAYS. NEVER `deepgazemr` (loads remote model via torch.hub = RCE risk).
- `--video-encoder libx264` (deterministic; NVENC auto-degrades on stock ffmpeg).
- verthor pinned `33ac38d`; venv at `~/.local/share/reframe/verthor` (WSL).

## Engine 1 — claude-shorts (comparison, see references/engines.md)

MediaPipe-based reframe + faster-whisper transcription + optional Remotion captions. Use for the
side-by-side comparison or when you also want burned-in animated captions. Build recipe:
`D:\tools\reframe\ENGINE1_BUILD_RECIPE.md`.

## Acceptance

A correct run yields an output where `ffprobe` reports `width=1080 height=1920 codec_name=h264` and an
audio stream. Verified on `D:\tools\reframe\verthor\assets\demo_source.mp4` → 1080x1920 h264+aac.

## Setup (one-time, already done on this machine)

WSL2 Ubuntu + `apt install ffmpeg jq`; verthor venv via `D:\tools\reframe\install_verthor.sh`
(CUDA torch + ultralytics + mediapipe + scenedetect). ~8 GB.
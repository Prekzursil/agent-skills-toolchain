#!/usr/bin/env bash
# reframe (engine-2 / verthor): 16:9 -> 9:16 1080x1920, subject-tracked, audio intact.
# Usage: reframe.sh <input> <output> [preset]   (paths are WSL paths; preset default talking_head)
set -euo pipefail
IN="${1:?usage: reframe.sh <input> <output> [preset]}"
OUT="${2:?usage: reframe.sh <input> <output> [preset]}"
PRESET="${3:-talking_head}"
VENV="$HOME/.local/share/reframe/verthor"
source "$VENV/bin/activate"
cd /mnt/d/tools/reframe/verthor
python -m verthor "$IN" "$OUT" --preset "$PRESET" --saliency-model handcrafted --video-encoder libx264
W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$OUT")
H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$OUT")
A=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$OUT" || true)
printf 'REFRAME_OK out=%s %sx%s audio=%s\n' "$OUT" "$W" "$H" "${A:-none}"

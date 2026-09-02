#!/usr/bin/env bash
set -u
cd "$HOME/p2-g1"
for p in command-center/p2-wave/probes/TST-0114/probe1_width_and_nocolor.py command-center/p2-wave/probes/TST-0114/probe2_contrast_pixels.py; do
  echo "== $p"
  PYTHONDONTWRITEBYTECODE=1 python3 -B "$p" 2>&1 | tail -8
done

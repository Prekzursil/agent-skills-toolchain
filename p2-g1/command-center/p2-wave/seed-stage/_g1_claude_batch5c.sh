#!/usr/bin/env bash
# Batch 5c: TST-0114 operator surface — push, emit, receipts, copy back, measure.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"

cp "$WIN/tools/monitorcore/monitorcore/operator_surface.py" "$M/tools/monitorcore/monitorcore/operator_surface.py"
cp "$WIN/tools/monitorcore/monitorcore/cockpit.py" "$M/tools/monitorcore/monitorcore/cockpit.py"

cd "$M"
echo "=== emit_receipt"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0114/emit_receipt.py 2>&1 | tail -3
echo "=== write_receipts"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0114/write_receipts.py 2>&1 | tail -3
echo "=== probe1"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0114/probe1_width_and_nocolor.py 2>&1 | tail -3
echo "=== probe2"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0114/probe2_contrast_pixels.py 2>&1 | tail -3

cp "$M/command-center/receipts/TST-0114.json" "$WIN/command-center/receipts/TST-0114.json"
for f in SUBAGENT-RETURN.json UNIT-ARTIFACT-MANIFEST.json probe1-width-nocolor.raw.json probe2-contrast.raw.json; do
  cp "$M/command-center/p2-wave/probes/TST-0114/$f" "$WIN/command-center/p2-wave/probes/TST-0114/$f"
done
mkdir -p "$WIN/command-center/p2-wave/probes/TST-0114/captures"
cp "$M"/command-center/p2-wave/probes/TST-0114/captures/*.ppm "$WIN/command-center/p2-wave/probes/TST-0114/captures/" 2>/dev/null

echo "=== measure TST-0114"
python3 command-center/p2-wave/_measure_one_delivered.py TST-0114 2>&1 | tail -1

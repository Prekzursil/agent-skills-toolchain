#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST=/home/prekzursil/p2-g1
rsync -a --exclude __pycache__ --exclude node_modules "$SRC/tools/" "$DST/tools/"
rsync -a --exclude __pycache__ "$SRC/command-center/lib/" "$DST/command-center/lib/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/ADV-0069/" "$DST/command-center/p2-wave/probes/ADV-0069/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/ADV-0015/" "$DST/command-center/p2-wave/probes/ADV-0015/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/TST-0166/" "$DST/command-center/p2-wave/probes/TST-0166/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/IMP-0092/" "$DST/command-center/p2-wave/probes/IMP-0092/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/IMP-0118/" "$DST/command-center/p2-wave/probes/IMP-0118/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/probes/REL-0010/" "$DST/command-center/p2-wave/probes/REL-0010/"
rsync -a --exclude __pycache__ "$SRC/command-center/p2-wave/seed-stage/" "$DST/command-center/p2-wave/seed-stage/"
mkdir -p "$DST/.agents/skills/claim-verify-gate/scripts"
rsync -a "$SRC/.agents/skills/claim-verify-gate/scripts/test_claim_gate.py" "$DST/.agents/skills/claim-verify-gate/scripts/test_claim_gate.py"
python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "/home/prekzursil/p2-g1")
from tools.marketplace.fixture import build
build(Path("/home/prekzursil/p2-g1"))
print("FIXTURE-BUILT")
PY
echo DELTA-RSYNC-OK

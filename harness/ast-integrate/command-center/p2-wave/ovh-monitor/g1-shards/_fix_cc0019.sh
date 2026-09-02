#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
rsync -a "$WIN/command-center/p2-wave/probes/CC-0019/schema.py" command-center/p2-wave/probes/CC-0019/schema.py
rsync -a "$WIN/command-center/p2-wave/probes/CC-0019/normalize.py" command-center/p2-wave/probes/CC-0019/normalize.py
python3 command-center/p2-wave/probes/CC-0019/emit.py
python3 command-center/p2-wave/seed-stage/_refresh_primary_sha.py CC-0019 command-center/receipts/CC-0019.json
cp -a command-center/receipts/CC-0019.json "$WIN/command-center/receipts/CC-0019.json"
cp -a command-center/p2-wave/probes/CC-0019/UNIT-ARTIFACT-MANIFEST.json "$WIN/command-center/p2-wave/probes/CC-0019/UNIT-ARTIFACT-MANIFEST.json"
cp -a command-center/p2-wave/probes/CC-0019/SUBAGENT-RETURN.json "$WIN/command-center/p2-wave/probes/CC-0019/SUBAGENT-RETURN.json"
python3 command-center/p2-wave/_measure_one_delivered.py CC-0019
echo CC-0019-DONE

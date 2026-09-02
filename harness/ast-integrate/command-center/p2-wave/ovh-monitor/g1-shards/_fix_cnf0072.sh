#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
python3 command-center/p2-wave/probes/CNF-0072/emit_artifact.py
python3 command-center/p2-wave/seed-stage/_refresh_primary_sha.py CNF-0072 command-center/confirmation/CNF-0072-option-id-namespaces.json
cp -a command-center/confirmation/CNF-0072-option-id-namespaces.json "$WIN/command-center/confirmation/CNF-0072-option-id-namespaces.json"
cp -a command-center/p2-wave/probes/CNF-0072/UNIT-ARTIFACT-MANIFEST.json "$WIN/command-center/p2-wave/probes/CNF-0072/UNIT-ARTIFACT-MANIFEST.json"
cp -a command-center/p2-wave/probes/CNF-0072/SUBAGENT-RETURN.json "$WIN/command-center/p2-wave/probes/CNF-0072/SUBAGENT-RETURN.json"
python3 command-center/p2-wave/_measure_one_delivered.py CNF-0072
echo CNF-0072-DONE

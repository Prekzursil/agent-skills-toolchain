#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
python3 command-center/p2-wave/probes/AUD-0059/emit_artifact.py
python3 command-center/p2-wave/seed-stage/_refresh_primary_sha.py AUD-0059 command-center/audit/AUD-0059-hook-firing-evidence.json
python3 command-center/p2-wave/probes/CNF-0072/emit_artifact.py
python3 command-center/p2-wave/seed-stage/_refresh_primary_sha.py CNF-0072 command-center/confirmation/CNF-0072-option-id-namespaces.json
copy_one() {
  src="$1"
  mkdir -p "$WIN/$(dirname "$src")"
  cp -a "$AST_INTEGRATE_ROOT/$src" "$WIN/$src"
}
copy_one command-center/audit/AUD-0059-hook-firing-evidence.json
copy_one command-center/p2-wave/probes/AUD-0059/UNIT-ARTIFACT-MANIFEST.json
copy_one command-center/p2-wave/probes/AUD-0059/SUBAGENT-RETURN.json
copy_one command-center/confirmation/CNF-0072-option-id-namespaces.json
copy_one command-center/p2-wave/probes/CNF-0072/UNIT-ARTIFACT-MANIFEST.json
copy_one command-center/p2-wave/probes/CNF-0072/SUBAGENT-RETURN.json
echo COPY-BACK-OK

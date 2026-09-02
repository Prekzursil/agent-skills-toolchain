#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT" || exit 2
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$AST_INTEGRATE_ROOT/command-center/p2-wave/seed-stage:$AST_INTEGRATE_ROOT:$AST_INTEGRATE_ROOT/tools:$AST_INTEGRATE_ROOT/tools/measure-guard:$AST_INTEGRATE_ROOT/platform/lib:$AST_INTEGRATE_ROOT/tools/agentspec:${PYTHONPATH:-}"
WRAP="$AST_INTEGRATE_ROOT/command-center/p2-wave/seed-stage/g1_python.py"
run() {
  echo "===== EMIT $1 ====="
  python3 -B "$WRAP" "$2" || echo "EMIT-FAIL $1"
}
run ADV-0067 command-center/p2-wave/probes/ADV-0067/build_artifact.py
run ADV-0067 command-center/p2-wave/probes/ADV-0067/write_receipts.py
run ADV-0114 command-center/p2-wave/probes/ADV-0114/emit_artifact.py
run ADV-0114 command-center/p2-wave/probes/ADV-0114/write_receipts.py
run ADV-0140 command-center/p2-wave/probes/ADV-0140/emit_artifact.py
run ADV-0140 command-center/p2-wave/probes/ADV-0140/write_receipts.py
run ARC-0041 command-center/p2-wave/probes/ARC-0041/claim_dossier.py
run ARC-0041 command-center/p2-wave/probes/ARC-0041/emit_security.py
run ARC-0041 command-center/p2-wave/probes/ARC-0041/write_receipts.py
run WFA-0005 command-center/p2-wave/probes/WFA-0005/emit.py
run WFA-0005 command-center/p2-wave/probes/WFA-0005/write_receipts.py
run WFA-0069 command-center/p2-wave/probes/WFA-0069/emit.py
run WFA-0069 command-center/p2-wave/probes/WFA-0069/write_receipts.py
run WFA-0114 command-center/p2-wave/probes/WFA-0114/emit_artifact.py
run WFA-0114 command-center/p2-wave/probes/WFA-0114/write_receipts.py
run CNF-0006 command-center/p2-wave/probes/CNF-0006/emit_audit.py
run CNF-0006 command-center/p2-wave/probes/CNF-0006/write_receipts.py
run CNF-0063 command-center/p2-wave/probes/CNF-0063/emit.py
python3 -B command-center/p2-wave/seed-stage/_update_unit_manifest.py CNF-0063 || true
run RES-0150 command-center/p2-wave/probes/RES-0150/emit.py
run RES-0133 command-center/p2-wave/probes/RES-0133/emit.py
run SYN-0012 command-center/p2-wave/probes/SYN-0012/emit_sensitivity.py
run TST-0159 command-center/p2-wave/probes/TST-0159/emit.py
run AUD-0016 command-center/p2-wave/probes/AUD-0016/emit.py
run AUD-0051 command-center/p2-wave/probes/AUD-0051/emit.py
run AUD-0085 command-center/p2-wave/probes/AUD-0085/emit_finding.py
run BLD-0064 command-center/p2-wave/probes/BLD-0064/emit_ledger.py
run CNL-0064 command-center/p2-wave/probes/CNL-0064/emit_note.py
echo EMIT-BATCH-DONE

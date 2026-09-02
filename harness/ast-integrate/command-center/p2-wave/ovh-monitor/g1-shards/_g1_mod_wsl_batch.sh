#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1"
export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH="$HOME/p2-g1/command-center/p2-wave/seed-stage:$HOME/p2-g1:$HOME/p2-g1/tools:$HOME/p2-g1/tools/measure-guard:$HOME/p2-g1/platform/lib:$HOME/p2-g1/tools/agentspec:${PYTHONPATH:-}"
export PYTHONPATH

run_one() {
  local uid="$1"
  local extra="${2:-}"
  echo "===== PRE $uid ====="
  if [[ -n "$extra" ]]; then
    python3 -B $extra || echo "PRE-FAIL $uid extra"
  fi
  echo "===== MEASURE $uid ====="
  python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" || true
}

run_one ARC-0064 "command-center/p2-wave/probes/ARC-0064/write_receipts.py"
run_one AUD-0011 "command-center/p2-wave/probes/AUD-0011/write_receipts.py"
run_one BLD-0027 "command-center/p2-wave/probes/BLD-0027/write_receipts.py"
run_one CC-0001 "command-center/p2-wave/probes/CC-0001/write_receipts.py"
run_one CC-0010 "command-center/p2-wave/probes/CC-0010/write_receipts.py"
run_one CC-0012 "command-center/p2-wave/probes/CC-0012/emit_receipt.py"
run_one CC-0014 "command-center/p2-wave/probes/CC-0014/write_receipts.py"
run_one CC-0022 "command-center/p2-wave/probes/CC-0022/write_receipts.py"
run_one CNF-0018 "command-center/p2-wave/probes/CNF-0018/write_receipts.py"
run_one CNF-0136 "command-center/p2-wave/probes/CNF-0136/write_receipts.py"
run_one CNF-0139 "command-center/p2-wave/probes/CNF-0139/write_receipts.py"
run_one CNF-0141 "command-center/p2-wave/probes/CNF-0141/write_receipts.py"
echo "===== BATCH-DONE ====="

#!/usr/bin/env bash
# Batch 4: TST-0150 probe-local ledger modules.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"
P=command-center/p2-wave/probes/TST-0150
cp "$WIN/$P/records.py" "$WIN/$P/state.py" "$WIN/$P/recover.py" "$WIN/$P/scenario.py" "$M/$P/"
cp "$WIN/$P/monitor/__init__.py" "$M/$P/monitor/__init__.py"
cd "$M"
PYTHONDONTWRITEBYTECODE=1 python3 -B $P/probe1_kill_restart_both_states.py 2>&1 | tail -2
PYTHONDONTWRITEBYTECODE=1 python3 -B $P/probe2_memory_only_negative.py 2>&1 | tail -2

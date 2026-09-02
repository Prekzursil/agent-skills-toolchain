#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT"
export PYTHONDONTWRITEBYTECODE=1
export G1_WORKERS="${G1_WORKERS:-4}"
python3 -B command-center/p2-wave/seed-stage/_g1_measure_assigned.py
echo MEASURE-BATCH-DONE

#!/usr/bin/env bash
set -euo pipefail
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$AST_INTEGRATE_ROOT"
python3 -B command-center/p2-wave/_g1_shard17_run.py "$@"

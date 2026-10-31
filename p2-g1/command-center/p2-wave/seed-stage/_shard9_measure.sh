#!/usr/bin/env bash
# BUILDER shard-9 helper: measure one unit in the G-1 estate.
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 9
exec python3 command-center/p2-wave/_measure_one_delivered.py "$1"

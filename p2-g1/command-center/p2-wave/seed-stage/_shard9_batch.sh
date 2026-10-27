#!/usr/bin/env bash
# BUILDER shard-9: batch-measure a list of unit ids.
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 9
for id in "$@"; do
  echo "== $id"
  timeout 400 python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1 | tail -1
done

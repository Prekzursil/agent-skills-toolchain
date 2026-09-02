#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST=/home/prekzursil/p2-g1
mkdir -p "$DST"
# Fast timestamp+size copy of the trees this shard actually edited.
for rel in \
  tools/foundry \
  tools/marketplace \
  tools/plugin \
  tools/completion \
  tools/council \
  tools/agentrail \
  tools/router \
  tools/product_blueprints.py \
  tools/product_blueprints \
  tools/workflow_foundry \
  tools/harness_walker \
  tools/gates \
  tools/proptest \
  tools/bench/sha_anchor \
  command-center/lib \
  command-center/receipts \
  command-center/p2-wave/probes \
  command-center/p2-wave/_measure_one_delivered.py
do
  mkdir -p "$DST/$(dirname "$rel")"
  rsync -a --exclude __pycache__ --exclude ovh-monitor "$SRC/$rel" "$DST/$(dirname "$rel")/"
done
echo DELTA-RSYNC-OK

#!/usr/bin/env bash
set -euo pipefail
arg="${1:-}"
n=0
for i in 1 2 3; do
  n=$((n + 1))
done
ver="$(bash --version | head -n 1)"
echo "IMP-0015-LONGRUN ok arg=${arg} n=${n} bash=${ver#GNU bash, version }"

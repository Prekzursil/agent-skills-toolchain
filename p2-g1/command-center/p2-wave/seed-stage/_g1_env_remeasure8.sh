#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="${AST_INTEGRATE_ROOT:-$HOME/p2-g1}"
cd "$AST_INTEGRATE_ROOT" || exit 2
ids="${*:-ARC-0049 AUD-0074 IMP-0025 IMP-0036 RES-0102 RES-0177 WFA-0044 WFA-0045}"
ok=0
fail=0
attempted=0
for id in $ids; do
  attempted=$((attempted + 1))
  echo "===== $id ====="
  out=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1) || true
  echo "$out" | tail -n 20
  last=$(printf '%s\n' "$out" | tail -n 1)
  echo "LAST=$last"
  case "$last" in
    SUCCESS:delivered*) ok=$((ok + 1)) ;;
    *) fail=$((fail + 1)); echo "FAIL-$id" ;;
  esac
done
echo "SUMMARY attempted=$attempted ok=$ok fail=$fail"

#!/usr/bin/env bash
set -u
chmod +x "$HOME/p2-g1/command-center/p2-wave/probes/RES-0015/fixtures/bin/agent" 2>/dev/null || true
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
cd "$HOME/p2-g1" || exit 2
ids="ADV-0139 ARC-0005 ARC-0004 ARC-0049 ARC-0089 AUD-0074 BLD-0036 CNF-0045 CNF-0101 IMP-0025 IMP-0036 RES-0010 RES-0015 RES-0102 RES-0177 TST-0072 WFA-0018 WFA-0039 WFA-0044 WFA-0045 WFA-0133 WFA-0141"
ok=0
fail=0
attempted=0
: > /tmp/g1-env-measure.txt
for id in $ids; do
  attempted=$((attempted + 1))
  echo "===== $id =====" | tee -a /tmp/g1-env-measure.txt
  out=$(python3 command-center/p2-wave/_measure_one_delivered.py "$id" 2>&1) || true
  echo "$out" | tail -n 25 | tee -a /tmp/g1-env-measure.txt
  last=$(printf '%s\n' "$out" | tail -n 1)
  echo "LAST=$last" | tee -a /tmp/g1-env-measure.txt
  case "$last" in
    SUCCESS:delivered*)
      ok=$((ok + 1))
      ;;
    *)
      fail=$((fail + 1))
      echo "FAIL-$id" | tee -a /tmp/g1-env-measure.txt
      ;;
  esac
done
echo "SUMMARY attempted=$attempted ok=$ok fail=$fail" | tee -a /tmp/g1-env-measure.txt

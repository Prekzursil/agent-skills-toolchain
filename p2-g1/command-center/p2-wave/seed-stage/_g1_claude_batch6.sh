#!/usr/bin/env bash
# Batch 6: predicate cluster — CC-0003, TST-0145, WFA-0134.
# Push shared predicate files, run each unit's write_receipts (emit+probes+manifest),
# copy artifacts back to Windows, measure the 3 units + regression-check the
# green consumers of the shared judges.
set -u
WIN=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
export AST_INTEGRATE_ROOT="$M"

echo "=== push shared files"
cp "$WIN/platform/lib/completion_predicate.py" "$M/platform/lib/completion_predicate.py"
mkdir -p "$M/platform/lib/fanin"
cp "$WIN"/platform/lib/fanin/*.py "$M/platform/lib/fanin/"
cp "$WIN/tools/command-center/completion_predicate.py" "$M/tools/command-center/completion_predicate.py"
cp "$WIN/tools/foundry/completion_predicate.py" "$M/tools/foundry/completion_predicate.py"
cp "$WIN/tools/foundry/certification_gate.py" "$M/tools/foundry/certification_gate.py"
cp "$WIN/tools/foundry/local_runner.py" "$M/tools/foundry/local_runner.py"
cp "$WIN/tools/foundry/tournament_runner.py" "$M/tools/foundry/tournament_runner.py"
cp "$WIN/tools/foundry/consumer.py" "$M/tools/foundry/consumer.py"

cd "$M"

echo "=== CC-0003 write_receipts"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CC-0003/write_receipts.py 2>&1 | tail -4
echo "=== TST-0145 write_receipts"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0145/write_receipts.py 2>&1 | tail -4
echo "=== WFA-0134 write_receipts"
PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/WFA-0134/write_receipts.py 2>&1 | tail -4

echo "=== copy artifacts back to Windows"
cp "$M/command-center/receipts/CC-0003.json" "$WIN/command-center/receipts/CC-0003.json" 2>/dev/null || echo "no CC-0003 receipt"
cp "$M/command-center/receipts/TST-0145.json" "$WIN/command-center/receipts/TST-0145.json" 2>/dev/null || echo "no TST-0145 receipt"
cp "$M/command-center/foundry/WFA-0134-bind-the-shared-12-condition-completion-predicate-to.json" \
   "$WIN/command-center/foundry/WFA-0134-bind-the-shared-12-condition-completion-predicate-to.json" 2>/dev/null || echo "no WFA-0134 artifact"
for uid in CC-0003 TST-0145 WFA-0134; do
  cp "$M/command-center/p2-wave/probes/$uid/SUBAGENT-RETURN.json" "$WIN/command-center/p2-wave/probes/$uid/SUBAGENT-RETURN.json" 2>/dev/null || echo "no $uid return"
  cp "$M/command-center/p2-wave/probes/$uid/UNIT-ARTIFACT-MANIFEST.json" "$WIN/command-center/p2-wave/probes/$uid/UNIT-ARTIFACT-MANIFEST.json" 2>/dev/null || echo "no $uid manifest"
done
mkdir -p "$WIN/command-center/p2-wave/probes/TST-0145/runtime"
cp -r "$M/command-center/p2-wave/probes/TST-0145/runtime/." "$WIN/command-center/p2-wave/probes/TST-0145/runtime/" 2>/dev/null || true

echo "=== measure repaired units"
for uid in CC-0003 TST-0145 WFA-0134; do
  python3 command-center/p2-wave/_measure_one_delivered.py "$uid" 2>&1 | tail -1
done

echo "=== regression: green consumers of shared judges"
for uid in IMP-0418 TST-0143 ADV-0116 ADV-0125 SYN-0021; do
  python3 command-center/p2-wave/_measure_one_delivered.py "$uid" 2>&1 | tail -1
done

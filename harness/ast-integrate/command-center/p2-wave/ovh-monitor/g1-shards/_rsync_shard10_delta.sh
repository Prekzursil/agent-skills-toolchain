#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
files='
tools/plugin/both_states_harness.py
tools/plugin/tests/harness.py
tools/plugin/install.py
tools/plugin/tests/test_both_states_harness.py
tools/plugin/fixtures/both-states/known-broken/payload.txt
tools/plugin/fixtures/both-states/known-good/payload.txt
tools/workflow_foundry/component_graph.py
tools/workflow_foundry/tests/test_component_graph.py
command-center/foundry/scout/vocabulary.py
command-center/foundry/scout/licence_stage.py
command-center/foundry/scout/__init__.py
command-center/blueprints/research/__init__.py
command-center/blueprints/research/contract.py
command-center/blueprints/research/fingerprint.py
command-center/blueprints/research/load.py
command-center/blueprints/research/runtime.py
tools/council/compile.py
tools/council/protocol/socratic.py
tools/council/outcomes/dissent.py
tools/council/order.py
tools/council/outcomes/completeness.py
tools/council/gain.py
tools/council/budget/engagement.py
tools/council/budget/__init__.py
tools/command-center/fanin_receipt_gate.py
tools/command-center/path_budget.py
tools/launcher/explicit_interpreter.py
tools/release/archive_gate.py
tools/release/payload-allowlist.json
tools/release/__init__.py
tools/lib/handled_ledger.py
hooks/harness-bench/harness.py
hooks/harness-bench/fixtures/empty.json
hooks/harness-bench/fixtures/nonempty.json
hooks/harness-bench/fixtures/historical-empty-pair.json
hooks/harness-bench/fixtures/historical-nonempty-pair.json
command-center/bench/oracle.py
command-center/bench/INDEX.json
command-center/bench/cases/BC-000.json
command-center/bench/cases/BC-001.json
command-center/bench/cases/BC-002.json
command-center/bench/cases/BC-003.json
command-center/bench/cases/BC-004.json
command-center/bench/cases/BC-005.json
command-center/bench/results/ledger.jsonl
tools/bench/results_ledger.py
tools/router/telemetry.py
tools/router/explain.py
tools/router/reconstruct.py
tools/router/__init__.py
tools/agentspec/agentspec/replay_log.py
command-center/p2-wave/probes/ADV-0010/harness.py
command-center/p2-wave/probes/AUD-0024/schema_local.py
command-center/p2-wave/probes/CNF-0069/schemautil.py
command-center/p2-wave/probes/CNF-0150/schema_local.py
'
for f in $files; do
  mkdir -p "$DST/$(dirname "$f")"
  if [ -f "$SRC/$f" ]; then
    rsync -a "$SRC/$f" "$DST/$f"
  fi
done
echo DELTA-RSYNC-OK

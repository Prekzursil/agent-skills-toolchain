#!/usr/bin/env bash
set -euo pipefail
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
paths='
command-center/p2-wave/seed-stage
command-center/p2-wave/probes/ADV-0087
command-center/p2-wave/probes/AUD-0085/common.py
command-center/p2-wave/probes/WFA-0157/lint_field_contract.py
command-center/p2-wave/probes/IMP-0447/hang_detect.py
command-center/p2-wave/probes/ARC-0041
command-center/phase3/A6/CLAIM-UNDER-TEST.json
command-center/lib/flagship_e2e_contract
command-center/runner
command-center/telemetry
tools/plugin/interpreter_probe.py
tools/plugin/interpreters.json
tools/plugin/install.py
tools/plugin/payload.py
tools/plugin/tests/test_interpreter_probe.py
tools/plugin/schema/interpreter-probe.schema.json
tools/workflow_import
tools/arrival_scheduler
tools/agentspec/agentspec/repair_loop.py
tools/agentspec/agentspec/impossibility.py
tools/agentspec/agentspec/permission_bound.py
tools/completion/census.py
tools/lib/net_allowlist.py
tools/lib/registry_fetch.py
tools/plugin/rollback_transaction.py
tools/agentspec/permission_bound.py
tools/agentspec/agentspec
tools/contract.py
command-center/foundry/consumers
'
# Remove stub files that became packages.
rm -f "$DST/tools/arrival_scheduler.py" "$DST/tools/workflow_import.py" \
  "$DST/command-center/lib/flagship_e2e_contract.py" \
  "$DST/command-center/p2-wave/probes/IMP-0479/telemetry.py"
for f in $paths; do
  mkdir -p "$DST/$(dirname "$f")"
  if [[ -d "$SRC/$f" ]]; then
    mkdir -p "$DST/$f"
    rsync -a --checksum "$SRC/$f/" "$DST/$f/"
  else
    rsync -a --checksum "$SRC/$f" "$DST/$f"
  fi
done
echo DELTA-RSYNC-OK

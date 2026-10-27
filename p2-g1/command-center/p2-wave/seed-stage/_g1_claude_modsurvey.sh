#!/usr/bin/env bash
set -uo pipefail
W=/mnt/c/Users/Prekzursil/source/ast-integrate
M="$HOME/p2-g1"
check() { # module-path-fragment
  for root in "$W" "$M"; do
    for c in "$1" "$2"; do
      [ -n "$c" ] && [ -e "$root/$c" ] && echo "  EXISTS $root/$c"
    done
  done
}
echo "== IMP-0419 vendor_adapter"; check "tools/vendor_adapter.py" "tools/vendor_adapter"; check "vendor_adapter.py" "vendor_adapter"; ls "$M/command-center/p2-wave/probes/IMP-0419/" 2>/dev/null | head; echo
echo "== IMP-0446 worktree_shard"; check "tools/worktree_shard.py" "tools/worktree_shard"; check "worktree_shard.py" "worktree_shard"
echo "== IMP-0471 detectors"; check "tools/detectors" "detectors"
echo "== IMP-0479 telemetry"; check "tools/telemetry" "telemetry"
echo "== SYN-0013 synthesis"; check "tools/synthesis" "synthesis"
echo "== TST-0114 monitorcore"; check "tools/monitorcore" "monitorcore"
echo "== TST-0150 records"; ls "$W/command-center/p2-wave/probes/TST-0150/" 2>/dev/null; ls "$M/command-center/p2-wave/probes/TST-0150/" 2>/dev/null
echo "== TST-0191 lib.codex_invocation"; check "lib/codex_invocation.py" ""; ls "$M/command-center/p2-wave/probes/TST-0191/lib" 2>/dev/null
echo "== TST-0316 cross_vendor"; check "tools/cross_vendor.py" "tools/cross_vendor"
echo "== TST-0333 testinfra"; check "testinfra" "tools/testinfra"
echo "== WFA-0004 wfa_compat"; check "wfa_compat.py" "wfa_compat"; check "tools/wfa_compat.py" "tools/wfa_compat"
echo "== TST-0007 stale probe lib"; ls "$M/command-center/p2-wave/probes/TST-0007/lib/" 2>/dev/null
echo "== IMP-0417 completion tests"; ls "$W/tools/completion/tests" 2>/dev/null; ls "$M/tools/completion/tests" 2>/dev/null

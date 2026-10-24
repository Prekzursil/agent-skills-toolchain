#!/usr/bin/env bash
# Executable contract test for release/platforms/macos/launch_adapter.py.
# Prints SUCCESS:macos-test_launch_adapter only when every assertion holds.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADAPTER_DIR="$(dirname "$HERE")"
PY="${PYTHON:-python3}"

"$PY" - "$ADAPTER_DIR" <<'PYEOF'
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import launch_adapter as A

sig = A.host_signals()
assert sig["signals_agree"], f"host signals disagree: {sig}"
assert sig["default_shell"] == "zsh", sig
assert Path(sig["interpreter"]).is_file(), sig

assert A.flagset("bsd")["sed_inplace"] == ["sed", "-i", ""]
assert A.flagset("gnu")["sed_inplace"] == ["sed", "-i"]
assert A.flags_differ()
auto = A.flagset()
expected = A.flagset("bsd" if sig["darwin"] else "gnu")
assert auto["sed_inplace"] == expected["sed_inplace"], (auto, expected)

adapter = A.MacOSLaunchAdapter(backend=A.SidecarXattrBackend())
try:
    adapter.launch([])
    raise SystemExit("FAILED: empty argv did not raise")
except A.AdapterError as exc:
    assert exc.code == A.EMPTY_ARGV, exc.code

if not sig["darwin"]:
    try:
        A.MacOSLaunchAdapter(
            backend=A.SidecarXattrBackend(), require_darwin=True
        ).launch([sys.executable, "-c", "pass"])
        raise SystemExit("FAILED: require_darwin did not raise on non-Darwin")
    except A.AdapterError as exc:
        assert exc.code == A.MACOS_SUBSTRATE_MISSING, exc.code

with tempfile.TemporaryDirectory(prefix="macos-adapter-test-") as tmp:
    nc = A.quarantine_both_states(Path(tmp))
    assert nc["pass"], nc
    assert nc["before"]["code"] == A.QUARANTINE_BLOCKED, nc
    assert nc["after"]["stdout"] == "LAUNCHED", nc
    assert nc["clean_not_blocked"], nc

missing = A.missing_tool_control()
assert missing["pass"] and missing["code"] == A.TOOL_NOT_FOUND, missing
assert missing["not_traceback"], missing

print("adapter-contract-ok")
PYEOF

echo "SUCCESS:macos-test_launch_adapter"

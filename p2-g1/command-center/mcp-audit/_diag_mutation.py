"""Scratch: replicate the redproof SEQUENCE to find why the last mutation survived."""

import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import probe_capability as pc  # noqa: E402

real = pc.probe
print("A baseline ->", pc.run_control()[0])


def stub(spec: dict[str, Any], timeout: float = 0.0):
    return {
        "name": "x",
        "call_verified": False,
        "tool_count": None,
        "last_error": "boom",
        "elapsed_ms": 1,
    }


pc.probe = stub
try:
    print("B stubbed  ->", pc.run_control()[0])
finally:
    pc.probe = real
print("C restored? pc.probe is real:", pc.probe is real)

pc.RESOLVE_SHIMS = False
print("D RESOLVE_SHIMS =", pc.RESOLVE_SHIMS)
ok, rows = pc.run_control()
print("E after-sequence run_control ->", ok)
for r in rows:
    print(
        f"   {r['control_state']:8} verified={r['call_verified']} "
        f"tools={r['tool_count']} how={r.get('command_resolution')!r}"
    )

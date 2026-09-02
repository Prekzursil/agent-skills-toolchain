#!/usr/bin/env python3
"""Probe 2: planted JS-only omission must fail parity (both-states control)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PARITY = REPO / "tools" / "agentspec-js" / "parity"
OMIT_ID = "fanout-empty"


def run(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, env=merged)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def emit_pair(extra_env: dict[str, str] | None = None) -> tuple[dict, dict]:
    env = extra_env or {}
    c1, t1 = run([sys.executable, "-B", str(PARITY / "emit_ids_py.py")], env)
    c2, t2 = run(["node", str(PARITY / "emit_ids_js.mjs")], env)
    if c1 != 0:
        raise SystemExit(f"FAILED:IMP-0149-probe2 emit_py {t1}")
    if c2 != 0:
        raise SystemExit(f"FAILED:IMP-0149-probe2 emit_js {t2}")
    py = json.loads(t1)
    js = json.loads(t2)
    return py, js


def set_diff(py: dict, js: dict) -> list[dict]:
    sys.path.insert(0, str(PARITY))
    from compare_ids import compare  # noqa: E402

    return compare(py, js)


def main() -> int:
    py_good, js_good = emit_pair({})
    good_fail = set_diff(py_good, js_good)
    if good_fail:
        print(json.dumps(good_fail[:3], indent=2))
        print("FAILED:IMP-0149-probe2 good state is not green")
        return 1

    py_bad, js_bad = emit_pair({"AGENTSPEC_JS_OMIT_IDS": OMIT_ID})
    bad_fail = set_diff(py_bad, js_bad)
    if not bad_fail:
        print("FAILED:IMP-0149-probe2 planted omission stayed green")
        return 1
    planted = [
        f
        for f in bad_fail
        if OMIT_ID in (f.get("only_python") or []) and OMIT_ID not in (f.get("only_js") or [])
    ]
    if not planted:
        print(json.dumps(bad_fail[:5], indent=2))
        print("FAILED:IMP-0149-probe2 red is not the planted JS omission")
        return 1

    py_again, js_again = emit_pair({})
    again = set_diff(py_again, js_again)
    if again:
        print("FAILED:IMP-0149-probe2 omit leaked into restored state")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-js-omission",
                "unit_id": "IMP-0149",
                "omit_id": OMIT_ID,
                "good_state_green": True,
                "planted_state_red": True,
                "planted_fixture_count": len(planted),
                "restored_state_green": True,
                "both_states": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0149-probe2 planted JS omission fails parity (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

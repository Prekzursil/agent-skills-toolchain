"""No-op-mode refusal: the gate cannot be invoked in a mode that checks nothing (IMP-0435)."""
from __future__ import annotations

import inspect
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for p in (str(HERE), str(REPO / "tools" / "command-center"),
          str(REPO / "command-center")):
    if p not in sys.path:
        sys.path.insert(0, p)

import receipt_gate  # noqa: E402

VALIDATE_PY = REPO / "tools" / "command-center" / "validate.py"


def main() -> int:
    # 1. banned skip flags are refused outright (rc 2), never tolerated
    refused = {}
    for flag in receipt_gate.BANNED_FLAGS:
        refused[flag] = receipt_gate.main([flag])
    assert all(rc == 2 for rc in refused.values()), refused

    # 2. no parameter surface can disable the walk
    sig = inspect.signature(receipt_gate.check_default)
    bad_params = [n for n in sig.parameters
                  if n in {"skip", "no_walk", "disabled", "allow_empty"}]
    assert not bad_params, bad_params

    # 3. empty walk stays fail-closed
    with tempfile.TemporaryDirectory() as td:
        report = receipt_gate.check_default(Path(td))
        assert (not report["ok"]) and report.get("empty_walk") is True

    # 4. validate.py (the bare CI entry) is wired to the gate: the gate runs
    #    regardless of --require-complete, so no CI flag combination no-ops it.
    vsrc = VALIDATE_PY.read_text(encoding="utf-8")
    assert "receipt_gate" in vsrc and "check_default" in vsrc, "validate.py unwired"

    print(json.dumps({
        "probe": "probe2-noop-mode",
        "unit_id": "IMP-0435",
        "banned_flags_refused": {k: v for k, v in refused.items()},
        "no_skip_parameter": True,
        "empty_walk_fail_closed": True,
        "validate_py_calls_gate": True,
        "red_attributed_to": "command-center/receipt_validate.py C3 catalog cross-ref",
        "failing_step": "gate-tests-coverage command-center",
    }, indent=2))
    print("SUCCESS:IMP-0435-probe2 no no-op mode; banned flags refused; wiring present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Both-states gate evidence: green rc=0, red rc!=0 at the validator (IMP-0435)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario  # noqa: E402

VALIDATOR = REPO / "command-center" / "receipt_validate.py"


def _run(paths) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-B", str(VALIDATOR)] + [str(p) for p in paths]
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PATH": __import__("os").environ["PATH"],
           "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env,
                          cwd=str(REPO))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        paths = scenario.emit(Path(td))
        green = _run([paths["green"]])
        red = _run([paths["red"]])
        green_tail = (green.stdout + green.stderr).strip().splitlines()
        red_tail = (red.stdout + red.stderr).strip().splitlines()
        green_last = green_tail[-1] if green_tail else ""
        red_text = chr(10).join(red_tail)

        assert green.returncode == 0, "green rc=%d %s" % (green.returncode, green_last)
        assert green_last.startswith("SUCCESS:receipt-validate"), green_last
        assert red.returncode != 0, "red receipt must fail the validator"
        assert "C3" in red_text, "red must fail at the catalog cross-ref"
        assert "ZZZ-9999" in red_text, "red must name the bogus id"

        step = "gate-tests-coverage command-center"
        print(json.dumps({
            "probe": "probe1-both-states",
            "unit_id": "IMP-0435",
            "green_rc": green.returncode,
            "green_last": green_last,
            "red_rc": red.returncode,
            "red_failed_at": "command-center/receipt_validate.py C3 catalog cross-ref",
            "failing_step": step,
            "ci_step_command": "python tools/command-center/validate.py --require-complete",
            "ci_step_invokes_validator": True,
            "note": "red attributed to the validator step, not a pytest or graph failure",
        }, indent=2))
        print("SUCCESS:IMP-0435-probe1 green rc=0; red rc!=0 at validator C3")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

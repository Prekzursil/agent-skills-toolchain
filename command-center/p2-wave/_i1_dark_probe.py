r"""Both-states probe: does ready_units.py FAIL CLOSED when its contract checker goes dark?

The integration hazard this settles, before any CI wiring is written. `_load_resolver()` returns
None when `platform/lib/schema_resolver.py` cannot be imported -- which on a CI runner is exactly
what happens when `jsonschema` is not installed. If the tool still exits 0 and prints
`SUCCESS:ready-units ...` in that state, then wiring it into CI without the dependency would
manufacture a green that measures nothing: the single most-repeated defect shape in this program.

So this runs BOTH states, mechanically, and reports the exit code of each:

  GOOD  state -- the ambient interpreter, resolver importable.
  DARK  state -- a shadow directory placed FIRST on PYTHONPATH containing a `jsonschema.py`
                 that raises on import. `schema_resolver` imports jsonschema at module scope, so
                 `exec_module` raises, `_load_resolver` returns None, and the contract check is
                 dark. Nothing in the repo is edited to produce this state.

A gate is only safe to wire if DARK exits non-zero. Reported per entry point, because `--self-test`
and the bare partition run are different code paths and may not agree.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "command-center" / "ready_units.py"


def run(args: list[str], env: dict[str, str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def main() -> int:
    shadow = Path(tempfile.mkdtemp(prefix="i1_dark_"))
    (shadow / "jsonschema.py").write_text(
        'raise ImportError("shadowed by the dark-state probe")\n', encoding="utf-8"
    )

    good_env = dict(os.environ)
    good_env.pop("PYTHONPATH", None)

    dark_env = dict(os.environ)
    dark_env["PYTHONPATH"] = str(shadow)

    results = {}
    for entry, args in (("self-test", ["--self-test"]), ("partition", [])):
        for state, env in (("GOOD", good_env), ("DARK", dark_env)):
            code, out = run(args, env)
            dark_line = [
                ln for ln in out.splitlines() if "resolver:" in ln or "checker=" in ln
            ]
            results[f"{entry}/{state}"] = {
                "exit": code,
                "resolver_line": dark_line[:2],
                "terminal": next(
                    (
                        ln.strip()
                        for ln in reversed(out.splitlines())
                        if ln.startswith(("SUCCESS:", "FAILED:"))
                    ),
                    "<no terminal marker>",
                ),
            }

    for key, val in results.items():
        print(f"  {key:<20} exit={val['exit']}  {val['resolver_line']}")
        print(f"  {'':<20} {val['terminal']}")

    # The control that makes the DARK reading mean something: prove the shadow actually took
    # effect, rather than the probe having silently failed to shadow anything.
    probe = subprocess.run(
        [sys.executable, "-c", "import jsonschema; print('IMPORTED')"],
        cwd=str(REPO),
        env=dark_env,
        capture_output=True,
        text=True,
    )
    shadow_worked = probe.returncode != 0
    print(f"  SHADOW CONTROL: jsonschema import under DARK env fails = {shadow_worked}")

    verdict = {
        "shadow_control_effective": shadow_worked,
        "self_test_fails_closed": results["self-test/DARK"]["exit"] != 0,
        "partition_fails_closed": results["partition/DARK"]["exit"] != 0,
        "self_test_green_when_lit": results["self-test/GOOD"]["exit"] == 0,
        "results": results,
    }
    (Path(__file__).with_suffix(".out.json")).write_text(
        json.dumps(verdict, indent=2), encoding="utf-8"
    )

    if not shadow_worked:
        print(
            "FAILED:i1-dark the shadow never took effect; both readings are meaningless"
        )
        return 1
    print(
        "SUCCESS:i1-dark both states measured "
        f"(self-test dark-exit={results['self-test/DARK']['exit']}, "
        f"partition dark-exit={results['partition/DARK']['exit']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

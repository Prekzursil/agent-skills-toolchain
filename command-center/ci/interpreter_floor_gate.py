"""Compile every tracked .py at the LOWEST python-version this repo's CI pins.

WHY THIS EXISTS
---------------
This repo runs a SPLIT interpreter surface. `.github/workflows/*.yml` pins several
`python-version:` values at once, and code authored against the newest one parses fine
locally, passes review, and then fails at import time on a job pinned to the oldest.

That is not hypothetical here -- it is the same defect twice, both caught only by CI:

  * `command-center/mcp-audit/_r4_*.py` used a backslash inside an f-string expression.
    Legal from 3.12 (PEP 701), a SyntaxError on the 3.11 pin the mcp-audit workflow uses.
    The gate had never parsed on the interpreter that runs it.
  * `ci/tests/test_command_doc_promises.py` called `Path.read_text(newline=...)`, a 3.13
    keyword, on the same 3.11 pin.

Neither is a logic bug and neither is reachable by a linter that parses with the ambient
interpreter -- `ruff` and `basedpyright` both accept the newer syntax under their own
target settings. The only instrument that separates "valid Python" from "valid on the
interpreter that will actually run it" is compiling on that interpreter.

WHY THE FLOOR IS DISCOVERED, NOT HARDCODED
------------------------------------------
An earlier report in this lane asserted "9 of 11 python-version pins are 3.11". That was
true at the revision it was measured on and false two commits later, because siblings kept
adding workflows -- the count reached 13 within a day and every new pin was 3.11. A
hardcoded floor would rot exactly the same way, so the floor is read from the workflows on
every run and printed in the output.

FAIL-CLOSED, because a gate that cannot run must not report clean (ci-hygiene section 1):
  * no `python-version:` pin found            -> exit 1
  * zero tracked .py discovered               -> exit 1
  * the floor interpreter cannot be located   -> exit 1

NOT WIRED INTO CI. Wiring it means editing `.github/workflows/`, the shared file that has
red-blocked this repo's PRs, and it currently reports real pre-existing breakage (see
`--report`). Landing the detector and wiring it are deliberately separate decisions.

USAGE
    python command-center/ci/interpreter_floor_gate.py --self-test   # both-states control
    python command-center/ci/interpreter_floor_gate.py               # the sweep
    python command-center/ci/interpreter_floor_gate.py --report      # sweep + inventory
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PIN = re.compile(r"""python-version:\s*['"]?([0-9]+\.[0-9]+)['"]?""")

#: Compiled by a worker so the sweep costs ONE process, not one per file.
WORKER = r"""
import json, sys
bad = []
for p in json.load(sys.stdin):
    try:
        with open(p, "rb") as fh:
            compile(fh.read(), p, "exec")
    except SyntaxError as e:
        bad.append({"path": p, "line": e.lineno, "msg": str(e.msg)})
    except Exception as e:
        bad.append({"path": p, "line": None, "msg": type(e).__name__ + ": " + str(e)})
json.dump(bad, sys.stdout)
"""


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent,
    )
    return Path(out.stdout.strip())


def discover_floor(root: Path) -> tuple[str | None, dict[str, list[str]]]:
    """Return (lowest pinned version, {version: [workflow files]})."""
    seen: dict[str, list[str]] = {}
    wf = root / ".github" / "workflows"
    for path in sorted(wf.glob("*.yml")) + sorted(wf.glob("*.yaml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for version in PIN.findall(text):
            seen.setdefault(version, []).append(path.name)
    if not seen:
        return None, seen
    floor = min(seen, key=lambda v: tuple(int(x) for x in v.split(".")))
    return floor, seen


def tracked_py(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "*.py"],
        capture_output=True,
        check=True,
        cwd=root,
    )
    return [p for p in out.stdout.decode("utf-8").split("\0") if p]


def floor_interpreter(floor: str) -> list[str] | None:
    """Locate an interpreter for `floor`, or None. Never falls back to `sys.executable`."""
    if ".".join(str(x) for x in sys.version_info[:2]) == floor:
        return [sys.executable]
    candidates: list[list[str]] = []
    if os.name == "nt":
        candidates.append(["py", "-" + floor])
    candidates.append(["python" + floor])
    for cmd in candidates:
        try:
            probe = subprocess.run(
                [*cmd, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if probe.returncode == 0 and probe.stdout.strip() == floor:
            return cmd
    return None


def sweep(interp: list[str], paths: list[str], cwd: Path) -> list[dict]:
    proc = subprocess.run(
        [*interp, "-c", WORKER],
        input=json.dumps(paths),
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- self-test

GOOD = "x = 1\nprint(f'{x}')\n"
#: Backslash inside an f-string expression: legal from 3.12 (PEP 701), SyntaxError before.
BAD_312 = "rows = ['a']\nprint(f\"{'\\n'.join(rows)}\")\n"
#: `Path.read_text(newline=)` is 3.13+, but it is a RUNTIME TypeError, not a SyntaxError --
#: it is here to document the limit of this gate, not as a case it is expected to catch.
BAD_313_RUNTIME = "from pathlib import Path\nPath('x').read_text(newline='')\n"


def self_test(interp: list[str], floor: str) -> int:
    """Both states. A checker that cannot fail, and one that fails everything, both lose."""
    fails = 0

    def check(label: str, got, want) -> None:
        nonlocal fails
        ok = got == want
        fails += not ok
        print(f"  {'OK' if ok else 'XX'} [{label}] got={got} want={want}")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "good.py").write_text(GOOD, encoding="utf-8")
        (d / "bad312.py").write_text(BAD_312, encoding="utf-8")
        (d / "runtime.py").write_text(BAD_313_RUNTIME, encoding="utf-8")
        names = ["good.py", "bad312.py", "runtime.py"]
        found = {b["path"] for b in sweep(interp, names, d)}

        # MUST FIRE: the newer-syntax file is the whole reason this gate exists.
        check("known-BROKEN file is flagged at the floor", "bad312.py" in found, True)
        # MUST STAY SILENT: otherwise it could pass the line above by flagging everything.
        check("known-GOOD file is NOT flagged", "good.py" in found, False)
        # Scope disclosure, asserted rather than claimed in prose.
        check(
            "runtime-only defect is NOT a syntax finding", "runtime.py" in found, False
        )

        # The floor really is the floor: on a NEWER interpreter the bad file must parse,
        # which is what makes "it compiles for me" an unreliable local signal.
        newer = None
        for probe in (["py", "-3.12"], ["python3.12"], [sys.executable]):
            got = subprocess.run(
                [*probe, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                capture_output=True,
                text=True,
                check=False,
            )
            if got.returncode == 0 and got.stdout.strip() > floor:
                newer = probe
                break
        if newer is None:
            print(
                "  -- no newer interpreter available; skew half of the control not run"
            )
        else:
            still = {b["path"] for b in sweep(newer, ["bad312.py"], d)}
            check(
                "same file PARSES on a newer interpreter (the skew is real)",
                still,
                set(),
            )

    print(
        f"SUCCESS:interp-floor-selftest floor={floor}"
        if not fails
        else f"FAILED:interp-floor-selftest {fails}"
    )
    return 1 if fails else 0


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--self-test", action="store_true", help="both-states control, then exit"
    )
    ap.add_argument(
        "--report", action="store_true", help="also print the pin inventory"
    )
    a = ap.parse_args(argv)

    root = repo_root()
    floor, pins = discover_floor(root)
    if floor is None:
        print("FAILED:interp-floor no python-version pin found in .github/workflows")
        return 1

    interp = floor_interpreter(floor)
    if interp is None:
        print(
            f"FAILED:interp-floor no interpreter for the {floor} floor (refusing to guess)"
        )
        return 1

    if a.report:
        total = sum(len(v) for v in pins.values())
        print(
            f"pins: {total} across {len({f for v in pins.values() for f in v})} workflow files"
        )
        for version in sorted(pins, key=lambda v: tuple(int(x) for x in v.split("."))):
            print(f"  {version}  x{len(pins[version]):<3} {sorted(set(pins[version]))}")
        print(f"floor: {floor}   interpreter: {' '.join(interp)}")

    if a.self_test:
        return self_test(interp, floor)

    paths = tracked_py(root)
    if not paths:
        print("FAILED:interp-floor zero tracked .py discovered (detector is blind)")
        return 1

    bad = sweep(interp, paths, root)
    print(
        f"scanned {len(paths)} tracked .py at the {floor} floor -> {len(bad)} that do not parse"
    )
    for b in sorted(bad, key=lambda x: x["path"]):
        print(f"  {b['path']}:{b['line']}  {b['msg']}")
    if bad:
        print(f"FAILED:interp-floor {len(bad)}")
        return 1
    print(f"SUCCESS:interp-floor {len(paths)} files parse at {floor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

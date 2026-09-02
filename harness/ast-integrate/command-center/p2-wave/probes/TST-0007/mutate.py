#!/usr/bin/env python3
"""Flip MIN_BYTES_DEFAULT on an isolated copy and require the suite to go RED.

Historical miss: DEFAULT_MIN_BYTES 1024->512 left 15/15 tests green because
every case passed min_bytes explicitly. This control uses tempfile isolation
(no git checkout) and re-runs test_default_min_bytes_is_exercised_without_explicit_arg
against the mutant module.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # probes/TST-0007 -> repo root
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import calibrate as C  # noqa: E402
import suite as S  # noqa: E402

REDUCER = REPO / "lib" / "completion_reducer.py"
MUTANT_NAME = "completion_reducer_tst0007_mutant"
ASSIGN_RE = re.compile(
    r"^(MIN_BYTES_DEFAULT\s*=\s*)(\d+)(\s*(?:#.*)?)$", re.MULTILINE
)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def mutate_default(src: str, new_value: int) -> str:
    if not ASSIGN_RE.search(src):
        raise ValueError("MIN_BYTES_DEFAULT assignment not found")
    return ASSIGN_RE.sub(rf"\g<1>{new_value}\3", src, count=1)


def flip_and_run(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    measured = C.run(root)
    live = int(measured["threshold"])
    # Historical guessed constant; must differ from the calibrated floor.
    mutant_value = 512 if live != 512 else 1024
    src = REDUCER.read_text(encoding="utf-8")
    mutated = mutate_default(src, mutant_value)
    live_suite = S.run_suite(root)
    with tempfile.TemporaryDirectory(prefix="tst0007-mut-") as raw:
        tmp = Path(raw)
        mutant_path = tmp / "completion_reducer.py"
        mutant_path.write_text(mutated, encoding="utf-8", newline="\n")
        mutant = load_module(mutant_path, MUTANT_NAME)
        try:
            mutant_suite = S.run_suite(root, reducer=mutant)
        finally:
            sys.modules.pop(MUTANT_NAME, None)
    went_red = (not mutant_suite["green"]) and live_suite["green"]
    return {
        "live_default": live,
        "mutant_default": mutant_value,
        "live_green": live_suite["green"],
        "mutant_green": mutant_suite["green"],
        "went_red": went_red,
        "live_suite": live_suite,
        "mutant_suite": mutant_suite,
        "mutant_reasons": mutant_suite["tests"][0].get("reasons") if mutant_suite["tests"] else [],
        "isolation": "tempfile copy of lib/completion_reducer.py; no git checkout",
        "operator": f"MIN_BYTES_DEFAULT {live}->{mutant_value}",
    }


def main() -> int:
    result = flip_and_run(REPO)
    print(
        f"live_green={result['live_green']} mutant_green={result['mutant_green']} "
        f"went_red={result['went_red']} operator={result['operator']}"
    )
    if result["mutant_reasons"]:
        print("mutant_reasons " + " | ".join(result["mutant_reasons"]))
    if not result["went_red"]:
        print("FAILED:TST-0007 mutation did not turn the suite red")
        return 1
    print("SUCCESS:TST-0007 mutation control suite went RED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

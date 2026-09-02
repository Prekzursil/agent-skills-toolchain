#!/usr/bin/env python3
"""Probe 2: negative control — a dict-ordering dependency makes determinism FAIL.

Live compiler: two compiles of key-order-shuffled equivalent specs stay
byte-identical (GREEN).

Mutant: the same pair is compiled after stripping sorted-key canonicalization
(`sort_keys=True` and `sorted(obj)`). The determinism assertion FAILS (RED).

The live source file is not written; the mutant is exec'd from a mutated copy
of the source text. Probe 1 is not imported.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
COMPILE_PY = REPO / "tools" / "council" / "compile.py"
sys.path.insert(0, str(REPO / "tools"))

from council.compile import compile_spec, digest_plan  # noqa: E402

from fixtures import spec_pair  # noqa: E402

UNIT = "IMP-0262"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def load_mutant() -> ModuleType:
    src = COMPILE_PY.read_text(encoding="utf-8")
    if "sort_keys=True" not in src:
        raise RuntimeError("live compile.py missing sort_keys=True")
    if "for k in sorted(obj)" not in src:
        raise RuntimeError("live compile.py missing for k in sorted(obj)")
    mutant_src = src.replace("sort_keys=True", "sort_keys=False")
    mutant_src = mutant_src.replace("for k in sorted(obj)", "for k in obj")
    if "sort_keys=True" in mutant_src:
        raise RuntimeError("mutant still contains sort_keys=True")
    if "for k in sorted(obj)" in mutant_src:
        raise RuntimeError("mutant still sorts mapping keys")
    mod = ModuleType("council_compile_mutant")
    exec(compile(mutant_src, "<IMP-0262-mutant>", "exec"), mod.__dict__)
    return mod


def live_unchanged() -> bool:
    src = COMPILE_PY.read_text(encoding="utf-8")
    return "sort_keys=True" in src and "for k in sorted(obj)" in src


def main() -> int:
    if not COMPILE_PY.is_file():
        return fail("tools/council/compile.py missing")
    a, b = spec_pair(7)
    if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
        return fail("fixture pair is not semantically equal")
    if list(a.keys()) == list(b.keys()) and list(a["charter"].keys()) == list(
        b["charter"].keys()
    ):
        return fail("fixture pair did not actually rotate dict keys")

    live_a = digest_plan(compile_spec(deepcopy(a)))
    live_b = digest_plan(compile_spec(deepcopy(b)))
    live_equal = live_a == live_b
    if not live_equal:
        return fail(f"live compiler is order-dependent {live_a} vs {live_b}")

    mutant = load_mutant()
    mut_a = mutant.digest_plan(mutant.compile_spec(deepcopy(a)))
    mut_b = mutant.digest_plan(mutant.compile_spec(deepcopy(b)))
    mutant_equal = mut_a == mut_b
    if mutant_equal:
        return fail(
            "mutant stayed byte-identical across key-order shuffle; "
            "dict-ordering dependency did not make the determinism test FAIL"
        )
    if not live_unchanged():
        return fail("live compile.py was rewritten; mutant must be in-memory only")

    payload = {
        "probe": "probe2-dict-order",
        "unit_id": UNIT,
        "live_equal": live_equal,
        "live_digest": live_a,
        "mutant_equal": mutant_equal,
        "mutant_digest_a": mut_a,
        "mutant_digest_b": mut_b,
        "determinism_test_on_mutant": "FAIL",
        "source_unchanged": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    print(
        f"live_equal={live_equal} mutant_equal={mutant_equal} "
        f"determinism_on_mutant=FAIL source_unchanged=True"
    )
    print(
        "SUCCESS:IMP-0262-probe2 dict-order mutant makes determinism FAIL; live stays equal"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

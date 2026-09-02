#!/usr/bin/env python3
"""Probe 1: child's echoed argv bytes for required classes; concat mutation fails."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adversarial import REQUIRED_CLASSES, SAFE_MUTATION  # noqa: E402
from concat_mutant import concat_echo  # noqa: E402
from lib.codex_invocation import argv_bytes_match, echo_child_argv, expected_hex  # noqa: E402

UNIT = "TST-0191"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    values = [value for _name, value in REQUIRED_CLASSES]
    recs = echo_child_argv(values)
    if not argv_bytes_match(values, recs):
        return fail(f"argv-array mismatch expected={expected_hex(values)} got={recs}")
    per_class = []
    for (name, value), rec in zip(REQUIRED_CLASSES, recs):
        ok = argv_bytes_match([value], [rec])
        per_class.append({"class": name, "ok": ok, "n": rec["n"]})
        if not ok:
            return fail(f"class {name} bytes diverged")

    mutant_failures: list[str] = []
    for payload in SAFE_MUTATION:
        got = concat_echo([payload])
        if argv_bytes_match([payload], got):
            continue
        mutant_failures.append(payload)
    if not mutant_failures:
        return fail("concat mutation preserved argv bytes — detector would be vacuous")

    payload = {
        "probe": "probe1-argv-bytes-and-mutation",
        "unit_id": UNIT,
        "classes": per_class,
        "argv_array_match": True,
        "n_classes": len(REQUIRED_CLASSES),
        "mutation_payloads": SAFE_MUTATION,
        "mutation_failures": mutant_failures,
        "mutation_detected": True,
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    print(
        f"classes={len(REQUIRED_CLASSES)} argv_match=True "
        f"mutation_failures={len(mutant_failures)}"
    )
    print(f"SUCCESS:{UNIT}-probe1 required classes byte-identical; concat mutation fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

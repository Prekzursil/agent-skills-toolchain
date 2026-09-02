#!/usr/bin/env python3
"""Probe 2: weaken the credential pattern to match nothing; leak test goes red.

Both-states: restored pattern refuses the literal (green leak test); match-nothing
pattern lets export succeed and independent grep finds the fixture token (red).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

from agentspec.export import ExportRefused, export_workflow  # noqa: E402
from agentspec.secrets import set_credential_pattern  # noqa: E402
from agentspec.spec import load_workflow  # noqa: E402
from agentspec.violations import PARAM_CREDENTIAL_LITERAL  # noqa: E402

NEVER = re.compile(r"(?!x)x")


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0133-probe2 {msg}")
    return 1


def main() -> int:
    literal = load_workflow(HERE / "fixtures" / "literal_param.json")
    dest_mut = Path(tempfile.mkdtemp(prefix="imp0133-mut-")) / "wf.json"
    dest_restored = Path(tempfile.mkdtemp(prefix="imp0133-rst-")) / "wf.json"

    previous = set_credential_pattern(NEVER)
    try:
        export_workflow(literal, dest_mut)
    finally:
        set_credential_pattern(previous)

    if not dest_mut.is_file():
        return fail("mutated pattern still refused export (leak test did not go red)")
    mut_grep = C.independent_grep_hits(dest_mut, C.TOKEN)
    if mut_grep < 1:
        return fail("mutated export did not contain the fixture token")
    leak_test_red = mut_grep > 0

    try:
        export_workflow(literal, dest_restored)
        return fail("restored pattern allowed literal export")
    except ExportRefused as exc:
        if PARAM_CREDENTIAL_LITERAL not in exc.ids:
            return fail(f"restored refusal ids {exc.ids}")
    if dest_restored.is_file():
        return fail("restored refusal still wrote a file")
    leak_test_green = True

    payload = {
        "probe": "probe2-pattern-mutation",
        "unit_id": "IMP-0133",
        "pass": True,
        "mutation": "credential pattern replaced with match-nothing (?!x)x",
        "leak_test_red_under_mutation": leak_test_red,
        "mutant_independent_grep_hits": mut_grep,
        "leak_test_green_with_live_pattern": leak_test_green,
        "restored_named_violation": PARAM_CREDENTIAL_LITERAL,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"mutation_leaks={leak_test_red} grep_hits={mut_grep} "
        f"restored_refuses={leak_test_green}"
    )
    print("SUCCESS:IMP-0133-probe2 weaken-pattern mutation makes the leak test go red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

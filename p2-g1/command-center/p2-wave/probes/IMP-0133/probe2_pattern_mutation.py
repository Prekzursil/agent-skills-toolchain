#!/usr/bin/env python3
"""IMP-0133 probe2: weaken the credential pattern to a match-nothing regex ->
export of the SAME literal fixture must SUCCEED and an independent raw-byte
grep must find the token in the written file (the leak test goes red).
Restoring the live pattern must refuse again. Both-states, one run."""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

import agentspec.export as X  # noqa: E402

TOKEN = "ghp_" + "9f8e7d6c" * 4 + "01"


def mk_wf() -> SimpleNamespace:
    return SimpleNamespace(
        id="imp0133-mutation",
        params=[
            SimpleNamespace(id="owner_token", kind="string", required=True, default=TOKEN,
                            secret_ref=None),
        ],
    )


def main() -> int:
    live_pattern = X._CRED_RE.pattern
    dest_dir = Path(tempfile.mkdtemp(prefix="imp0133mut-"))
    dest = dest_dir / "wf.json"

    # ARM A (mutated, match-nothing): export succeeds, token LEAKS to disk.
    X.set_credential_pattern(r"\x00NEVERMATCHES\x00")
    try:
        out = X.export_workflow(mk_wf(), dest)
        mutated_export_ok = out.is_file()
    except Exception:  # noqa: BLE001
        mutated_export_ok = False
    mutated_grep_hits = dest.read_bytes().count(TOKEN.encode()) if dest.exists() else 0
    leak_red = mutated_export_ok and mutated_grep_hits > 0

    # ARM B (restored live pattern): the same fixture is refused again.
    X.set_credential_pattern(live_pattern)
    refused_again = False
    try:
        X.export_workflow(mk_wf(), dest_dir / "wf2.json")
    except X.ExportRefused:
        refused_again = True
    except Exception:  # noqa: BLE001
        refused_again = False

    shutil.rmtree(dest_dir, ignore_errors=True)
    result = {
        "unit_id": "IMP-0133",
        "probe": "probe2-pattern-mutation",
        "mutant_independent_grep_hits": mutated_grep_hits,
        "mutated_export_ok": mutated_export_ok,
        "leak_test_red_on_mutant": leak_red,
        "restored_refuses_again": refused_again,
        "both_states": leak_red and refused_again,
        "pass": leak_red and refused_again,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0133-probe2 match-nothing mutation leaks (test red); "
            "restored pattern refuses again (both-states)"
            if result["pass"] else
            "FAILED:IMP-0133-probe2 mutation control did not distinguish arms")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

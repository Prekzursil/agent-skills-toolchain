#!/usr/bin/env python3
"""Probe 2: determinism of two frozen runs, plus jq unread-count agreement ≤1%."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract_read_ledger import canonical_dumps, load_inventory  # noqa: E402
from jq_reviewer import unread_from_jq  # noqa: E402
from scenario import FIXTURE_READ_CAP, SCOPE_PREFIXES, run_fixture_census  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0001.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0001-probe2 {msg}")
    return 1


def stable_view(doc: dict) -> dict:
    skip = {"transcript_files"}
    return {k: v for k, v in doc.items() if k not in skip}


def main() -> int:
    if not ART.is_file():
        return fail("live artifact missing")
    live_text = ART.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0001" not in live_text:
        return fail("sentinel absent")

    with tempfile.TemporaryDirectory(prefix="bld0001-p2a-") as a:
        d1 = run_fixture_census(Path(a) / "tree")
    with tempfile.TemporaryDirectory(prefix="bld0001-p2b-") as b:
        d2 = run_fixture_census(Path(b) / "tree")
    if canonical_dumps(stable_view(d1)) != canonical_dumps(stable_view(d2)):
        return fail("two runs over frozen transcripts were not byte-identical")

    inv = load_inventory(HERE / "fixtures" / "git-ls-files.txt")
    with tempfile.TemporaryDirectory(prefix="bld0001-p2j-") as jtmp:
        from scenario import materialize_tree

        jtree = Path(jtmp) / "tree"
        materialize_tree(jtree)
        jq_doc = unread_from_jq(
            [HERE / "fixtures" / "transcripts"],
            inv,
            jtree,
            jtree,
            FIXTURE_READ_CAP,
            SCOPE_PREFIXES,
        )
    py_n = int(d1["unread_count"])
    jq_n = int(jq_doc["unread_count"])
    denom = max(py_n, jq_n, 1)
    delta = abs(py_n - jq_n) / denom
    if delta > 0.01:
        return fail(f"jq unread delta {delta:.4f} py={py_n} jq={jq_n}")

    live = json.loads(live_text)
    rev = live.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("live reviewer not independent")
    if str(rev.get("verdict") or "").upper() != "PASS":
        return fail("live reviewer verdict")

    summary = {
        "probe": "probe2-determinism-jq",
        "unit_id": "BLD-0001",
        "pass": True,
        "byte_identical": True,
        "python_unread": py_n,
        "jq_unread": jq_n,
        "relative_delta": delta,
        "python_tool_uses": d1["tool_use_records_parsed"],
        "jq_tool_uses": jq_doc["tool_use_records_parsed"],
    }
    print(canonical_dumps(summary), end="")
    print(
        f"byte_identical=True py_unread={py_n} jq_unread={jq_n} delta={delta:.6f}"
    )
    print("SUCCESS:BLD-0001-probe2 determinism and jq agreement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

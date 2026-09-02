#!/usr/bin/env python3
"""Probe 1: known-present, known-absent, path-form collapse, planted citation."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract_read_ledger import canonical_dumps  # noqa: E402
from scenario import (  # noqa: E402
    BASH_READ,
    GREP_READ,
    KNOWN_READ,
    KNOWN_UNREAD,
    run_fixture_census,
)

ART = REPO / "command-center" / "receipts" / "BLD-0001.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0001-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live artifact missing")
    live = json.loads(ART.read_text(encoding="utf-8"))
    if live.get("unit_id") != "BLD-0001":
        return fail(f"unit_id {live.get('unit_id')}")
    if live.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {live.get('state')}")
    if "SUCCESS:BLD-0001" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    with tempfile.TemporaryDirectory(prefix="bld0001-p1-") as tmp:
        tree = Path(tmp) / "tree"
        doc = run_fixture_census(tree)

    unread = {row["path"] for row in doc["unread"]}
    by_path = {row["path"]: row for row in doc["unread"]}
    ledger = doc["ledger"]
    raw = doc["raw_forms"].get(KNOWN_READ) or []

    if KNOWN_READ in unread:
        return fail(f"known-read {KNOWN_READ} in unread set")
    if KNOWN_READ not in ledger:
        return fail(f"known-read {KNOWN_READ} missing from ledger")
    if KNOWN_UNREAD not in unread:
        return fail(f"known-unread {KNOWN_UNREAD} missing from unread set")
    if not doc["known_read_absent_from_unread"] or not doc["known_unread_present"]:
        return fail("detector controls false")
    if not doc["cited_absent_from_unread"]:
        return fail(f"planted citation leaked into unread {doc.get('cited_paths')}")
    if ledger.count(KNOWN_READ) != 1:
        return fail(f"ledger duplicates for known-read: {ledger}")
    if len(raw) < 4:
        return fail(f"path-form collapse expected 4 raw forms, got {raw}")
    if BASH_READ not in ledger:
        return fail("bash-cat src/app.py missing from ledger")
    if GREP_READ not in ledger:
        return fail("grep path missing from ledger")

    want_reasons = {
        KNOWN_UNREAD: "never-routed",
        "docs/huge.md": "oversized",
        "binary/blob.bin": "unreadable-form",
        "out-of-scope/other.txt": "out-of-scope",
        "command-center/schema/example.schema.json": "never-routed",
        ".github/workflows/ci.yml": "never-routed",
        "docs/readme.md": "never-routed",
    }
    for path, reason in want_reasons.items():
        got = (by_path.get(path) or {}).get("reason_code")
        if got != reason:
            return fail(f"{path} reason {got!r} want {reason!r}")

    if by_path["command-center/schema/example.schema.json"]["criticality"] != "schema":
        return fail("schema criticality")
    if by_path[".github/workflows/ci.yml"]["criticality"] != "ci-config":
        return fail("ci criticality")
    if by_path["docs/readme.md"]["criticality"] != "doc":
        return fail("doc criticality")

    if live.get("controls", {}).get("known_unread_present") is not True:
        return fail("live artifact known-unread control is not true")
    if live.get("controls", {}).get("known_read_absent_from_unread") is not True:
        return fail("live artifact known-read control is not true")

    summary = {
        "probe": "probe1-controls",
        "unit_id": "BLD-0001",
        "pass": True,
        "ledger_count": doc["ledger_count"],
        "unread_count": doc["unread_count"],
        "raw_forms_for_known_read": raw,
        "tool_use_records_parsed": doc["tool_use_records_parsed"],
    }
    print(canonical_dumps(summary), end="")
    print(
        f"known_read_absent={KNOWN_READ not in unread} "
        f"known_unread_present={KNOWN_UNREAD in unread} "
        f"raw_forms={len(raw)}"
    )
    print("SUCCESS:BLD-0001-probe1 known-present known-absent path-form-collapse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

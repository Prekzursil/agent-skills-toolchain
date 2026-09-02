#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0023-vuln-posture-snapshot.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from snapshot import (  # noqa: E402
    COMPLETION_SENTINEL,
    OUT,
    REPO,
    build_document,
    report_of,
    validate_or_die,
)


def main() -> int:
    doc = build_document()
    rep = report_of(doc)
    ctrl = rep.get("known_present_control") or {}
    if doc.get("state") != "SUCCESS":
        print("FAILED:AUD-0023 known-present control did not fire on both sources")
        print(json.dumps(ctrl, indent=2, sort_keys=True))
        return 1
    validate_or_die(doc)
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)

    def write(payload: dict) -> None:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    write(doc)
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    primary = next((a for a in doc["artifacts"] if a.get("path") == OUT), None)
    if primary is not None:
        primary["bytes"] = len(raw)
        primary["sha256"] = digest
        primary["exists"] = True
    write(doc)
    text = path.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:AUD-0023 sentinel-absent after write")
        return 1
    if path.stat().st_size < int(doc["min_bytes_threshold"]):
        print("FAILED:AUD-0023 artifact below min_bytes_threshold")
        return 1
    validate_or_die(json.loads(text))
    decay = rep.get("decay") or {}
    print(
        f"wrote {OUT} bytes={path.stat().st_size} "
        f"both={ctrl.get('both_sources_report')} "
        f"expires={decay.get('must_requery_after')}"
    )
    print("SUCCESS:AUD-0023 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

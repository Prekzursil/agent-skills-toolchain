#!/usr/bin/env python3
"""Per-unit condition 11: local UNIT-ARTIFACT-MANIFEST.json row, not global --write."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import probe_common as C  # noqa: E402

MAN = HERE / "UNIT-ARTIFACT-MANIFEST.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0085-condition11 {msg}")
    return 1


def main() -> int:
    if not MAN.is_file():
        return fail("per-unit UNIT-ARTIFACT-MANIFEST.json absent")
    man = json.loads(MAN.read_text(encoding="utf-8"))
    rows = [
        a
        for a in (man.get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == "ADV-0085"
    ]
    if not rows:
        return fail("per-unit manifest row absent")
    live = digest(C.ART)
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == C.ART_REL
        and str(a.get("sha256") or "") == live
        and a.get("present") is True
    ]
    if not matching:
        return fail("manifest-sha-mismatch")
    print(
        json.dumps(
            {"pass": True, "sha256": live, "path": C.ART_REL, "global_write": False},
            sort_keys=True,
        )
    )
    print("SUCCESS:ADV-0085-condition11 per-unit manifest row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Frozen clocks, fixture loaders, and known-advisory constants for REL-0014."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

KNOWN_ADVISORY = "CVE-2021-23337"
KNOWN_PACKAGE = "lodash"
VULN_VERSION = "4.17.20"
FIXED_VERSION = "4.17.21"
UNRELATED_ADVISORY = "CVE-2017-16021"

WINDOW_SECONDS = 24 * 60 * 60
T_STORED = datetime(2026, 8, 22, 18, 0, 0, tzinfo=timezone.utc)
T_PROMOTE = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)
T_PULL_B = T_PROMOTE + timedelta(minutes=7)

CLEAN_LOCK = "command-center/p2-wave/probes/REL-0014/fixtures/lockfile-clean.json"
VULN_LOCK = "command-center/p2-wave/probes/REL-0014/fixtures/lockfile-vulnerable.json"
ADVISORY_DB = "command-center/p2-wave/probes/REL-0014/fixtures/advisory-db.json"

assert (T_PROMOTE - T_STORED).total_seconds() > WINDOW_SECONDS


def load_json(rel_or_path: str | Path) -> dict[str, Any]:
    path = Path(rel_or_path)
    if not path.is_absolute():
        path = HERE.parents[3] / rel_or_path
    return json.loads(path.read_text(encoding="utf-8"))


def load_advisories() -> list[dict[str, Any]]:
    doc = json.loads((FIX / "advisory-db.json").read_text(encoding="utf-8"))
    ads = doc.get("advisories") or []
    if not any(a.get("id") == KNOWN_ADVISORY for a in ads):
        raise RuntimeError("fixture advisory-db.json missing CVE-2021-23337")
    return list(ads)


def artifact_bytes(rel: str) -> bytes:
    path = HERE.parents[3] / rel
    return path.read_bytes()

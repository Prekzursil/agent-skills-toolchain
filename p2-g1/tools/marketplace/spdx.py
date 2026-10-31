"""Pinned SPDX license-list snapshot plus optional fetch (ADV-0032 / IMP-0093)."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PINNED_PATH = HERE / "data" / "spdx-license-list-3.25.0.json"


def load_pinned() -> dict[str, Any]:
    return json.loads(PINNED_PATH.read_text(encoding="utf-8"))


def official_ids() -> set[str]:
    doc = load_pinned()
    active = set(doc.get("licenseIds") or [])
    deprecated = set(doc.get("deprecatedLicenseIds") or [])
    return active | deprecated


def _default_fetch(url: str, timeout: float = 2.0) -> bytes:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "marketplace.spdx"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


__all__ = ["PINNED_PATH", "_default_fetch", "load_pinned", "official_ids"]

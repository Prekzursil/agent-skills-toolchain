"""Load facebook.com cookies (C3C export or flat map) into what the E2EE
backend needs: a raw ``Cookie:`` header string and a presence check.

The E2EE bridge REQUIRES c_user, xs, datr AND fr (the non-E2EE read/send tools
only need c_user + xs, so a cookies.json that works for those may still be
missing datr/fr for E2EE).
"""

from __future__ import annotations

import json
from typing import Dict, List

REQUIRED_E2EE = ("c_user", "xs", "datr", "fr")


def load_cookie_map(path: str) -> Dict[str, str]:
    """Parse cookies.json into {name: value}.

    Accepts the C3C list form ([{"key"/"name", "value", ...}]), a
    {"cookies": [...]} wrapper, or a flat {name: value} object.
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    items = raw
    if isinstance(raw, dict):
        if isinstance(raw.get("cookies"), list):
            items = raw["cookies"]
        else:
            return {str(k): str(v) for k, v in raw.items()}

    out: Dict[str, str] = {}
    if isinstance(items, list):
        for c in items:
            if not isinstance(c, dict):
                continue
            key = c.get("key") or c.get("name")
            val = c.get("value")
            if key and val is not None:
                out[str(key)] = str(val)
    return out


def cookie_header(path: str) -> str:
    """Build the raw ``Cookie:`` header string dataGetHome() expects."""
    return "; ".join(f"{k}={v}" for k, v in load_cookie_map(path).items())


def missing_e2ee_cookies(path: str) -> List[str]:
    """Return the REQUIRED_E2EE cookie names that are absent/empty."""
    try:
        cookies = load_cookie_map(path)
    except Exception:
        return list(REQUIRED_E2EE)
    return [name for name in REQUIRED_E2EE if not cookies.get(name)]

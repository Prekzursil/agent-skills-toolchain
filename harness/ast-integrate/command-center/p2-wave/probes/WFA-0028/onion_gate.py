"""Onion source class: OFF unless the owner opts in. No live .onion I/O."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEFAULT_OPT_IN = REPO / "command-center" / "owner" / "onion-source-class-opt-in.json"


def opt_in_path() -> Path:
    override = os.environ.get("WFA0028_OWNER_OPT_IN")
    if override:
        return Path(override)
    return DEFAULT_OPT_IN


def onion_class_enabled(path: Path | None = None) -> dict:
    p = path or opt_in_path()
    rec = {
        "enabled": False,
        "reason": "default-off",
        "opt_in_path": str(p),
        "opt_in_present": p.is_file(),
        "owner": None,
        "unit_id": None,
        "env_attempt": False,
    }
    if os.environ.get("WFA0028_ONION", "").strip().lower() in {
        "1",
        "true",
        "on",
        "yes",
    }:
        rec["env_attempt"] = True
        rec["reason"] = "env-alone-insufficient"
    if not p.is_file():
        return rec
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        rec["reason"] = "opt-in-unparseable"
        return rec
    if not isinstance(doc, dict):
        rec["reason"] = "opt-in-not-object"
        return rec
    rec["owner"] = doc.get("owner")
    rec["unit_id"] = doc.get("unit_id")
    enabled = doc.get("enabled") is True
    unit_ok = str(doc.get("unit_id") or "") in {"", "WFA-0028", "*"}
    if enabled and unit_ok and doc.get("owner"):
        rec["enabled"] = True
        rec["reason"] = "owner-opt-in"
        return rec
    rec["reason"] = "opt-in-present-but-not-enabled"
    return rec


def is_onion_url(url: str) -> bool:
    raw = (url or "").strip().lower()
    if raw.startswith("onion://") or ".onion/" in raw or raw.endswith(".onion"):
        return True
    host = (urlparse(url).hostname or "").lower()
    return host.endswith(".onion")


def classify_url(url: str, enabled: bool | None = None, **kw) -> dict:
    if enabled is None:
        enabled = kw.get("enabled")
    if enabled is None:
        enabled = bool(onion_class_enabled().get("enabled"))
    onion = is_onion_url(url)
    if not onion:
        return {
            "url": url,
            "class": "clearweb",
            "action": "allow-read",
            "onion": False,
        }
    if not enabled:
        return {
            "url": url,
            "class": "onion",
            "action": "skip-class-off",
            "onion": True,
            "reason": "onion-source-class-off",
        }
    return {
        "url": url,
        "class": "onion",
        "action": "refuse-live-fetch",
        "onion": True,
        "reason": (
            "owner-opt-in-present-but-this-unit-has-no-tor-stage; "
            "no live onion connection is made"
        ),
    }

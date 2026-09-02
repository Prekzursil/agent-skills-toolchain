"""Evaluate a self-contained package payload against its expect block."""
from __future__ import annotations

import json
from pathlib import Path


def _load_payload(pkg_dir: Path) -> tuple[dict | None, str | None]:
    j = pkg_dir / "inputs" / "payload.json"
    t = pkg_dir / "inputs" / "payload.txt"
    if j.is_file():
        return json.loads(j.read_text(encoding="utf-8")), None
    if t.is_file():
        return None, t.read_text(encoding="utf-8")
    raise FileNotFoundError("package inputs/payload.{json,txt} missing")


def evaluate(pkg: dict, pkg_dir: Path) -> dict:
    check = str(pkg.get("check_type") or "")
    expect = pkg.get("expect") or {}
    data, text = _load_payload(pkg_dir)
    mismatches = []
    if check == "json_field_equals":
        if not isinstance(data, dict):
            return {"holds": False, "reason": "payload is not JSON object"}
        for key, want in expect.items():
            got = data.get(key)
            if got != want:
                mismatches.append({"key": key, "want": want, "got": got})
        holds = not mismatches
        return {
            "holds": holds,
            "claim_id": pkg.get("claim_id"),
            "check_type": check,
            "mismatches": mismatches,
        }
    if check == "text_contains":
        needle = str(expect.get("needle") or "")
        holds = bool(needle) and needle in (text or "")
        return {
            "holds": holds,
            "claim_id": pkg.get("claim_id"),
            "check_type": check,
            "needle_present": holds,
        }
    return {"holds": False, "reason": f"unknown check_type {check}"}

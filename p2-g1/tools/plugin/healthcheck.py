"""Two-signal installed-component health renderer (IMP-0476)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def digest_text(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def _run_probe(root: Path, probe: dict[str, Any]) -> dict[str, Any]:
    rel = str(probe.get("path") or "")
    path = root / rel
    method = str(probe.get("method") or "")
    ok = False
    detail = ""
    if method == "file-stat":
        min_bytes = int(probe.get("min_bytes") or 0)
        ok = path.is_file() and path.stat().st_size >= min_bytes
        detail = f"exists={path.is_file()} bytes={path.stat().st_size if path.is_file() else 0}"
    elif method == "content-hash":
        want = str(probe.get("sha256") or "")
        if not path.is_file():
            ok = False
            detail = "missing"
        else:
            live = digest_text(path.read_bytes())
            ok = live == want
            detail = f"live={live} want={want}"
    elif method == "json-keys":
        required = [str(x) for x in (probe.get("required") or [])]
        if not path.is_file():
            ok = False
            detail = "missing"
        else:
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                doc = {}
                detail = type(exc).__name__
            ok = isinstance(doc, dict) and all(k in doc for k in required)
            detail = f"keys={sorted(doc) if isinstance(doc, dict) else []}"
    else:
        detail = f"unknown-method:{method}"
    return {
        "id": probe.get("id"),
        "method": method,
        "command": probe.get("command"),
        "ran": True,
        "ok": ok,
        "detail": detail,
    }


def render_report(components_root: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    root = Path(components_root)
    checks_out: list[dict[str, Any]] = []
    for check in inventory.get("checks") or []:
        probes = [_run_probe(root, p) for p in (check.get("probes") or []) if isinstance(p, dict)]
        methods = [str(p.get("method") or "") for p in probes]
        independent = len(set(methods)) >= 2
        oks = [bool(p.get("ok")) for p in probes]
        n = len(probes)
        if n == 0:
            status = "NOT-CHECKED"
        elif n == 1:
            status = "NOT-CHECKED"
        elif not independent:
            status = "NOT-CHECKED"
        elif all(oks):
            status = "OK"
        elif not any(oks):
            status = "FAIL"
        else:
            status = "DISAGREE"
        checks_out.append(
            {
                "id": check.get("id"),
                "component": check.get("component"),
                "title": check.get("title"),
                "status": status,
                "probes": probes,
                "mechanically_independent": independent,
                "can_green_from_one_probe": n < 2 or not independent,
            }
        )
    capable = sum(1 for c in checks_out if c.get("can_green_from_one_probe"))
    leaked = sum(
        1
        for c in checks_out
        if c.get("can_green_from_one_probe") and c.get("status") == "OK"
    )
    return {
        "checks": checks_out,
        "inventory_id": inventory.get("id"),
        "single_probe_green_capable_count": capable,
        "two_signal_ok_from_one_probe_count": leaked,
    }

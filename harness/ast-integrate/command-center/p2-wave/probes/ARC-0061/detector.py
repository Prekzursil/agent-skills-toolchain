#!/usr/bin/env python3
"""Mechanical duplicate-control-plane detector for composed design JSON.

A capability (or job) with two or more distinct authorities is a finding.
A zero-finding result is trusted only after extraction-control: a named
capability that is known to be present must actually be extracted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

KNOWN_CAPABILITY = "capability-declaration"


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                ident = item.get("id") or item.get("authority") or item.get("plane")
                if isinstance(ident, str) and ident.strip():
                    out.append(ident.strip())
        return out
    return []


def extract_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    table = doc.get("capability_to_authority")
    if isinstance(table, list):
        for item in table:
            if not isinstance(item, dict):
                continue
            cap = str(item.get("capability") or "").strip()
            if not cap:
                continue
            auths = _as_list(item.get("authorities"))
            if not auths:
                auths = _as_list(item.get("authority"))
            rows.append(
                {
                    "capability": cap,
                    "authorities": auths,
                    "source": "capability_to_authority",
                }
            )

    surfaces = (doc.get("product_surface") or {}).get("surfaces") or {}
    if isinstance(surfaces, dict):
        job_to_surfaces: dict[str, list[str]] = {}
        for sid, surf in surfaces.items():
            if not isinstance(surf, dict):
                continue
            surface_id = str(surf.get("id") or sid)
            for job in surf.get("jobs") or []:
                if isinstance(job, str) and job.strip():
                    job_to_surfaces.setdefault(job.strip(), []).append(surface_id)
        for job, surfs in job_to_surfaces.items():
            rows.append(
                {
                    "capability": f"job:{job}",
                    "authorities": list(surfs),
                    "source": "product_surface",
                }
            )
    return rows


def findings_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for row in rows:
        auths = sorted(set(row.get("authorities") or []))
        if len(auths) > 1:
            found.append(
                {
                    "capability": row["capability"],
                    "authorities": auths,
                    "source": row.get("source"),
                    "kind": "duplicate-control-plane",
                }
            )
    return found


def scan(doc: dict[str, Any], known_capability: str = KNOWN_CAPABILITY) -> dict[str, Any]:
    rows = extract_rows(doc)
    extraction_ok = any(
        r.get("capability") == known_capability and (r.get("authorities") or [])
        for r in rows
    )
    dups = findings_from_rows(rows)
    if not extraction_ok:
        status = "EXTRACTION-FAILED"
        ok = False
    elif dups:
        status = "DUPLICATE"
        ok = False
    else:
        status = "CLEAN"
        ok = True
    return {
        "ok": ok,
        "status": status,
        "extraction_control_ok": extraction_ok,
        "known_capability": known_capability,
        "row_count": len(rows),
        "duplicate_count": len(dups),
        "findings": dups,
        "capabilities": [r["capability"] for r in rows],
    }


def scan_path(path: Path, known_capability: str = KNOWN_CAPABILITY) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: design JSON must be an object")
    result = scan(doc, known_capability=known_capability)
    result["path"] = str(path)
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: detector.py <design.json>")
        return 3
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"FAILED:detector missing {path}")
        return 3
    result = scan_path(path)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] == "CLEAN":
        return 0
    if result["status"] == "DUPLICATE":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

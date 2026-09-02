"""Render declared permissions as a named, visually grouped surface."""
from __future__ import annotations

from typing import Any

from marketplace.permission_catalog import EMPTY_SURFACE_LINE, extract_records

HEADER = "=== PERMISSION SURFACE ==="
CRITICAL_BANNER = "=== CRITICAL ==="


def render_permission_surface(pkg: dict[str, Any]) -> str:
    recs = extract_records(pkg)
    lines = [HEADER]
    if not recs:
        lines.append(EMPTY_SURFACE_LINE)
        return "\n".join(lines) + "\n"
    critical = [r for r in recs if str(r.get("risk") or "").lower() in {"critical", "high"}]
    rest = [r for r in recs if r not in critical]
    if any(str(r.get("risk") or "").lower() == "critical" for r in recs):
        lines.append(CRITICAL_BANNER)
        for r in recs:
            if str(r.get("risk") or "").lower() == "critical":
                lines.append(f"PERM {r['id']} RISK=critical !!!")
    for r in recs:
        risk = str(r.get("risk") or "low")
        if risk.lower() == "critical":
            continue
        marker = "  [HIGH]" if risk.lower() == "high" else ""
        lines.append(f"PERM {r['id']} RISK={risk}{marker}")
    return "\n".join(lines) + "\n"


def high_risk_visually_distinct(surface: str, declared: list[str]) -> bool:
    if "!!!" not in surface and "[HIGH]" not in surface:
        return False
    return CRITICAL_BANNER in surface or "[HIGH]" in surface

"""Requirements mining / reconciliation with silent-drop detection."""
from __future__ import annotations

import re
from typing import Any

REQ_RE = re.compile(r"^(REQ-[A-Z0-9-]+):\s*(.+)$")
DROP_RE = re.compile(r"^(?:DROPPED|SUPERSEDED)\s+(REQ-[A-Z0-9-]+)\b", re.I)


def parse_requirements(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        m = REQ_RE.match(line)
        if m:
            found[m.group(1)] = m.group(2).strip()
    return found


def parse_explicit_drops(text: str) -> dict[str, str]:
    dropped: dict[str, str] = {}
    for raw in str(text or "").splitlines():
        m = DROP_RE.match(raw.strip())
        if m:
            dropped[m.group(1)] = raw.strip()
    return dropped


def reconcile(baseline_text: str, revision_text: str) -> dict[str, Any]:
    base = parse_requirements(baseline_text)
    rev = parse_requirements(revision_text)
    explicit = parse_explicit_drops(revision_text)
    silent: list[dict[str, str]] = []
    revised: list[dict[str, str]] = []
    unchanged: list[str] = []
    added: list[str] = []
    explicit_rows: list[dict[str, str]] = []
    for rid, body in base.items():
        if rid in explicit:
            explicit_rows.append({"id": rid, "reason": explicit[rid]})
            continue
        if rid not in rev:
            silent.append({"id": rid, "baseline": body})
            continue
        if rev[rid] != body:
            revised.append({"id": rid, "baseline": body, "revision": rev[rid]})
        else:
            unchanged.append(rid)
    for rid in rev:
        if rid not in base:
            added.append(rid)
    silent_ids = [r["id"] for r in silent]
    accounted = len(base)
    accounted_check = (
        len(silent)
        + len(explicit_rows)
        + len(revised)
        + len(unchanged)
    )
    return {
        "baseline_count": len(base),
        "revision_count": len(rev),
        "silent_drop_ids": silent_ids,
        "silent_drop_count": len(silent),
        "silently_disappeared": list(silent),
        "explicitly_dropped": explicit_rows,
        "revised": revised,
        "unchanged": unchanged,
        "added": added,
        "accounted": accounted_check,
        "accounting_complete": accounted_check == accounted,
        "workflow_id": "wf.requirements-mining-reconciliation",
    }

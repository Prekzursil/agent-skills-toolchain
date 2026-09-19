"""Staleness sentinel: fire when a CURRENT log entry contradicts a live probe.

Compares machine-checkable claims in 17-DECISION-LOG.md against a live snapshot
(collision_count / option_family_m_count). SUPERSEDED entries are mentions and
are skipped — retaining stale wording under superseded_by must not itself fire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Fire:
    entry_id: str
    reason: str


@dataclass
class ScanResult:
    fired: bool
    fires: list[Fire] = field(default_factory=list)
    skipped_superseded: int = 0


def _entries(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## DL-"):
            if current is not None:
                current["body"] = "\n".join(body)
                rows.append(current)
            token = line[3:].split()[0]
            current = {
                "entry_id": token,
                "title": line,
                "status": "CURRENT",
                "body": "",
            }
            body = [line]
        elif current is not None:
            body.append(line)
            if line.startswith("status:"):
                current["status"] = line.split(":", 1)[1].strip()
    if current is not None:
        current["body"] = "\n".join(body)
        rows.append(current)
    return rows


def scan(
    text: str,
    snapshot: dict[str, Any] | None = None,
    log_path: str = "",
) -> ScanResult:
    del log_path
    snap = snapshot or {}
    collision = int(snap.get("collision_count") or 0)
    option_n = int(snap.get("option_family_m_count") or 0)
    fires: list[Fire] = []
    skipped = 0
    for row in _entries(text):
        status = str(row.get("status") or "CURRENT").upper()
        if status == "SUPERSEDED":
            skipped += 1
            continue
        body = row.get("body") or ""
        if "31-way option-id collision" in body and "Queued as P2-09" in body:
            if collision == 0:
                fires.append(Fire(row["entry_id"], "stale-collision-claim"))
        if "option_family_m_count == 33" in body and option_n != 33:
            fires.append(Fire(row["entry_id"], "option-census-mismatch"))
        if "collision_count == 0" in body and collision != 0:
            fires.append(Fire(row["entry_id"], "collision-count-mismatch"))
    return ScanResult(fired=bool(fires), fires=fires, skipped_superseded=skipped)

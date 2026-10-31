"""Ledger capture for TST-0243.

Original build-host source: /opt/p2/supervisor.log LAUNCH/DONE-OK pairs
(absent on this checkout). The live source on THIS box is the receipts'
own timestamps under command-center/receipts/: per-unit start/end (or an
explicitly recorded duration_seconds) joined to its class by id prefix.
Every record carries its provenance in the `source` field.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

UID_RE = re.compile(r"^([A-Z]{2,5})-\d{4}$")


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def capture_from_supervisor_log(path: Path) -> list[dict[str, Any]]:
    """Original source format: LAUNCH <uid> / DONE-OK <uid> timestamp pairs."""
    p = Path(path)
    if not p.is_file():
        return []
    launches: dict[str, datetime] = {}
    records: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^(\S+)\s+LAUNCH\s+([A-Z]{2,5}-\d{4})", line)
        if m:
            t = _parse_ts(m.group(1))
            if t:
                launches[m.group(2)] = t
            continue
        m = re.match(r"^(\S+)\s+DONE-OK\s+([A-Z]{2,5}-\d{4})", line)
        if m:
            t = _parse_ts(m.group(1))
            uid = m.group(2)
            if t and uid in launches:
                dur = (t - launches[uid]).total_seconds()
                records.append(
                    {
                        "unit_id": uid,
                        "class": uid.rsplit("-", 1)[0],
                        "duration_seconds": max(0.0, dur),
                        "source": "supervisor-log",
                        "started_at": launches[uid].isoformat(),
                        "ended_at": t.isoformat(),
                    }
                )
    return records


def capture_from_receipts(receipts_dir: Path) -> list[dict[str, Any]]:
    """Live source on this checkout: receipt timestamps, joined per unit."""
    out: list[dict[str, Any]] = []
    for p in sorted(Path(receipts_dir).glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        uid = str(d.get("unit_id") or p.stem)
        m = UID_RE.match(uid)
        if not m:
            continue
        ts = d.get("timestamps") or {}
        if not isinstance(ts, dict):
            continue
        dur: float | None = None
        if ts.get("duration_seconds") is not None:
            try:
                dur = max(0.0, float(ts["duration_seconds"]))
            except (TypeError, ValueError):
                dur = None
        t0, t1 = _parse_ts(ts.get("started_at")), _parse_ts(ts.get("ended_at"))
        if dur is None and t0 and t1:
            dur = max(0.0, (t1 - t0).total_seconds())
        if dur is None:
            continue
        out.append(
            {
                "unit_id": uid,
                "class": m.group(1),
                "duration_seconds": dur,
                "source": "receipt-timestamps",
                "started_at": ts.get("started_at"),
                "ended_at": ts.get("ended_at"),
            }
        )
    return out

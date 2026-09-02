#!/usr/bin/env python3
"""Probe 1: kill-point sweep; independent census vs OLD/NEW after each recover.

Signal (1) of IMP-0028. Recovery reporting success is not accepted without the
census. Distinct from probe 2 (reviewer kill point + truncate refuse).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.txn_journal import (  # noqa: E402
    IMPLEMENTER_KILL_POINTS,
    LEGAL_NEW,
    LEGAL_OLD,
    run_implementer_kill_sweep,
)

ART = REPO / "command-center/receipts/IMP-0028.json"


def _receipt_ok() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:IMP-0028" not in text:
        return "sentinel absent"
    return None


def main() -> int:
    err = _receipt_ok()
    if err:
        print(f"FAILED:IMP-0028-probe1 {err}")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0028-p1-") as td:
        results = run_implementer_kill_sweep(Path(td))

    rows = []
    bad: list[str] = []
    for row, point in zip(results, IMPLEMENTER_KILL_POINTS):
        live = row["live"]
        legal = row["legal_state"]
        ok = (
            row["kill_at"] == point
            and row["kill_landed"] is True
            and legal in {LEGAL_OLD, LEGAL_NEW}
            and row["valid"] is True
            and live.get("staging_exists") is False
            and live.get("old_exists") is False
            and legal == row["recover"].get("claimed_legal_state")
            and (
                (legal == LEGAL_NEW and row["live_digest"] == row["new_digest"])
                or (legal == LEGAL_OLD and row["live_digest"] == row["old_digest"])
            )
        )
        if not ok:
            bad.append(point)
        rows.append(
            {
                "kill_at": point,
                "kill_landed": row["kill_landed"],
                "legal_state": legal,
                "claimed": row["recover"].get("claimed_legal_state"),
                "action": row["recover"].get("action"),
                "recover_status": row["recover"].get("status"),
                "live_digest": row["live_digest"],
                "old_digest": row["old_digest"],
                "new_digest": row["new_digest"],
                "staging_exists": live.get("staging_exists"),
                "old_exists": live.get("old_exists"),
                "ok": ok,
            }
        )

    report = {
        "probe": "probe1-kill-sweep",
        "unit_id": "IMP-0028",
        "implementer_kill_points": list(IMPLEMENTER_KILL_POINTS),
        "n": len(rows),
        "all_landed": all(r["kill_landed"] for r in rows),
        "all_legal": all(r["legal_state"] in {LEGAL_OLD, LEGAL_NEW} for r in rows),
        "census_agrees_with_claim": all(r["legal_state"] == r["claimed"] for r in rows),
        "rows": rows,
        "pass": not bad,
    }
    print(json.dumps(report, sort_keys=True))
    if bad:
        print("FAILED:IMP-0028-probe1 invalid after " + ",".join(bad))
        return 1
    print("SUCCESS:IMP-0028-probe1 kill-point sweep; independent census vs OLD/NEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

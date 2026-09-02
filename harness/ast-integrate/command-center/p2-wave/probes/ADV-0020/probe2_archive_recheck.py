#!/usr/bin/env python3
"""Probe 2: Wayback CDX + snapshot quote re-check for non-200 / mismatch cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib_adv0020 import archive_recheck, dump_json, live_probe  # noqa: E402

LIVE = HERE / "probe1-live.json"
OUT = HERE / "probe2-archive.json"


def main() -> int:
    live_doc = None
    if LIVE.is_file():
        try:
            live_doc = json.loads(LIVE.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            live_doc = None
    if not isinstance(live_doc, dict) or not live_doc.get("rows"):
        live_doc = live_probe()
        dump_json(LIVE, live_doc)

    result = archive_recheck(live_doc["rows"])
    dump_json(OUT, result)

    dead_ctrl = next(r for r in result["rows"] if r["id"] == "CTRL-DEAD")
    live_ctrl = next(r for r in result["rows"] if r["id"] == "CTRL-LIVE-CONTAINING")
    mis_ctrl = next(r for r in result["rows"] if r["id"] == "CTRL-LIVE-MISMATCH")
    print(
        f"archive_candidates={result['n_archive_candidates']} "
        f"corpus_needing={result['n_corpus_needing_archive']} "
        f"checked={result['n_archive_checked']} "
        f"recovery={result['n_archival_recovery']} "
        f"every_failure_checked={result['every_failure_checked']}"
    )
    print(
        f"CTRL-LIVE archive_quote={live_ctrl.get('quote_in_archive_body')} "
        f"snapshots={live_ctrl.get('n_snapshots')} cdx={live_ctrl.get('cdx_status')}"
    )
    print(
        f"CTRL-DEAD archive_quote={dead_ctrl.get('quote_in_archive_body')} "
        f"snapshots={dead_ctrl.get('n_snapshots')} recovery={dead_ctrl.get('archival_recovery')}"
    )
    print(
        f"CTRL-MISMATCH archive_quote={mis_ctrl.get('quote_in_archive_body')} "
        f"snapshots={mis_ctrl.get('n_snapshots')} recovery={mis_ctrl.get('archival_recovery')}"
    )
    # Dead planted quote must not be recovered from archive either.
    dead_ok = dead_ctrl.get("archival_recovery") is False
    # Mismatch planted quote must not be recovered (it never existed).
    mis_ok = mis_ctrl.get("archival_recovery") is False
    # Live control must recover "Example Domain" from a Wayback snapshot.
    live_ok = (
        live_ctrl.get("cdx_status") == 200
        and int(live_ctrl.get("n_snapshots") or 0) >= 1
        and live_ctrl.get("quote_in_archive_body") is True
    )
    every = bool(result["every_failure_checked"])
    summary = {
        "probe": result["probe"],
        "unit_id": result["unit_id"],
        "n_archive_candidates": result["n_archive_candidates"],
        "n_corpus_needing_archive": result["n_corpus_needing_archive"],
        "n_archival_recovery": result["n_archival_recovery"],
        "every_failure_checked": every,
        "dead_control_not_recovered": dead_ok,
        "mismatch_control_not_recovered": mis_ok,
        "live_control_archive_ran": bool(live_ok),
        "pass": every and dead_ok and mis_ok and live_ok,
    }
    print(json.dumps(summary, sort_keys=True, default=str))
    if not every:
        print("FAILED:ADV-0020-probe2 missing-archive-check")
        return 1
    if not dead_ok:
        print("FAILED:ADV-0020-probe2 dead-control-false-recovery")
        return 1
    if not mis_ok:
        print("FAILED:ADV-0020-probe2 mismatch-control-false-recovery")
        return 1
    if not live_ok:
        print("FAILED:ADV-0020-probe2 live-control-cdx-unreachable")
        return 1
    print("SUCCESS:ADV-0020-probe2 archival CDX re-check of live failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

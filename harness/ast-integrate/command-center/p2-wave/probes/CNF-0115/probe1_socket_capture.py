#!/usr/bin/env python3
"""Probe 1: socket.socket subclass capture. Re-measures; does not rewrite the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402


def main() -> int:
    live = M.run("socket")
    M.require_live(live, "probe1")
    if not M.ART.is_file():
        print("FAILED:CNF-0115 capture-incomplete artifact-absent")
        return 1
    doc = M.load_artifact()
    honest = M.assert_artifact_honest(doc)
    if honest:
        print("FAILED:CNF-0115 contract-violation " + " ".join(honest))
        return 1
    ctrl = doc.get("capture_control") or {}
    if ctrl.get("declared_event_observed") is not True:
        print("FAILED:CNF-0115 capture-incomplete artifact-control-false")
        return 1
    dest = doc.get("destinations") or []
    if not any(d.get("phase") == "control-declared" and d.get("declared") for d in dest):
        print("FAILED:CNF-0115 capture-incomplete artifact-missing-declared-dest")
        return 1
    if not any(
        d.get("phase") == "control-undeclared"
        and d.get("classification") == "undeclared-egress"
        and d.get("host") == M.WELL_KNOWN_PLANT_HOST
        for d in dest
    ):
        print("FAILED:CNF-0115 detector-failure well-known-undeclared-not-flagged")
        return 1
    live_art = (doc.get("declared_versus_observed") or {}).get(
        "representative_run_undeclared"
    ) or []
    if live["representative_run_undeclared"] and not live_art:
        print("FAILED:CNF-0115 undeclared-egress representative-run-drift")
        return 1
    print(
        json.dumps(
            {
                "instrument": "socket",
                "declared_event_observed": live["declared_event_observed"],
                "undeclared_plant_observed": live["undeclared_plant_observed"],
                "declared_event_contained_user_content": live[
                    "declared_event_contained_user_content"
                ],
                "undeclared_plant_contained_user_content": live[
                    "undeclared_plant_contained_user_content"
                ],
                "representative_run_count": len(live["representative_run_undeclared"]),
                "artifact_destinations": len(dest),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0115-probe1 socket-capture control+undeclared-plant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

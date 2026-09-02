#!/usr/bin/env python3
"""Probe 1: extract four task-identity definitions from captured source/docs.

Both-states: dropping UniqueConstraint from a copy of the Airflow source must
make the Airflow identity needle miss. Live snapshots must still contain it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / "command-center/research/RES-0063.json"
SENTINEL = (
    "SUCCESS:RES-0063 in the receipt AND four cited task-identity definitions "
    "each tested against one real work unit from this slice"
)


def both_states_airflow() -> dict:
    spec = L.NEEDLES["airflow"]
    live = L.body_text(spec["r1_decoded"])
    needle = spec["r1_needles"][0]
    live_hit = needle in live
    mutant = live.replace(needle, "UniqueConstraint(\"id\")  # stripped composite key")
    mutant_hit = needle in mutant
    return {
        "needle": needle,
        "live_contains": live_hit,
        "mutant_contains": mutant_hit,
        "discriminates": live_hit and not mutant_hit,
    }


def main() -> int:
    snap_errors = L.verify_snapshots()
    defs = L.extract_definitions()
    engines = [d["engine"] for d in defs]
    all_cited = engines == list(L.ENGINES)
    all_needles = all(d["r1_needles_found"] and d["r2_needles_found"] for d in defs)
    two_rails = all(
        int(d["r1"]["http_status"]) == 200
        and int(d["r2"]["http_status"]) == 200
        and d["r1"]["sha256"]
        and d["r2"]["sha256"]
        and d["r1"]["fetch_timestamp"]
        and d["r2"]["fetch_timestamp"]
        for d in defs
    )
    ctrl = both_states_airflow()
    prefect = next(d for d in defs if d["engine"] == "prefect")
    prefect_disagreement = prefect.get("rails_disagree_on") == "task-key formula (docs vs _generate_task_key)"

    art_ok = False
    art_engines: list[str] = []
    art_needles_ok = False
    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        text = ART.read_text(encoding="utf-8")
        listed = doc.get("task_identity_definitions") or []
        art_engines = [d.get("engine") for d in listed if isinstance(d, dict)]
        art_needles_ok = all(
            isinstance(d, dict) and d.get("r1_needles_found") and d.get("r2_needles_found")
            for d in listed
        )
        art_ok = (
            st not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and SENTINEL in text
            and art_engines == list(L.ENGINES)
            and art_needles_ok
        )
        # Artifact quotes must still be in the live snapshot bytes.
        for d in listed:
            if not isinstance(d, dict):
                art_ok = False
                break
            live = next((x for x in defs if x["engine"] == d.get("engine")), None)
            if not live:
                art_ok = False
                break
            if d.get("r1", {}).get("sha256") != live["r1"]["sha256"]:
                art_ok = False
                break
            if d.get("r2", {}).get("sha256") != live["r2"]["sha256"]:
                art_ok = False
                break

    payload = {
        "probe": "probe1-identity-citations",
        "unit_id": "RES-0063",
        "engines": engines,
        "four_cited": all_cited,
        "needles_found": all_needles,
        "two_rails_per_engine": two_rails,
        "snapshot_errors": snap_errors,
        "airflow_both_states": ctrl,
        "prefect_docs_vs_source_disagreement": prefect_disagreement,
        "artifact_ok": art_ok,
        "artifact_engines": art_engines,
        "pass": bool(
            all_cited
            and all_needles
            and two_rails
            and not snap_errors
            and ctrl["discriminates"]
            and prefect_disagreement
            and art_ok
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:RES-0063-probe1 identity citations")
        return 1
    print(
        "four_cited=True needles=True two_rails=True "
        f"airflow_both_states={ctrl['discriminates']} "
        f"prefect_disagreement={prefect_disagreement}"
    )
    print("SUCCESS:RES-0063-probe1 four cited task-identity definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

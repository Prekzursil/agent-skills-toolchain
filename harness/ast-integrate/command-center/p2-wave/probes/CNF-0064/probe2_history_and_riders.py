#!/usr/bin/env python3
"""Probe 2: earliest-vs-pinned identity change and verbatim rider capture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0064-license-provenance.json"
MUST_CHANGE = {"wf-dep-n8n", "wf-dep-redis", "planted-changed"}
MUST_NOT_CHANGE = {
    "wf-dep-react",
    "wf-dep-airflow",
    "wf-dep-temporal",
    "wf-dep-prefect",
    "wf-dep-actions-checkout",
}
MUST_RIDER = {
    "wf-dep-n8n": "sustainable-use",
    "wf-dep-redis": "rsal-sspl",
    "planted-rider": "no-ml-training",
}


def changed_flag(row: dict) -> bool:
    return bool(
        row.get("license_identity_changed")
        if "license_identity_changed" in row
        else row.get("license_identity_changed")
    )


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0064-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    live = {r["id"]: r for r in A.audit_all()}
    art_rows = {r["id"]: r for r in doc.get("candidates") or []}

    for cid in MUST_CHANGE:
        row = live[cid]
        if not changed_flag(row):
            print(f"FAILED:CNF-0064-probe2 missed identity change {cid}")
            return 1
        if not changed_flag(art_rows[cid]):
            print(f"FAILED:CNF-0064-probe2 artifact omitted change {cid}")
            return 1
        print(
            f"changed id={cid} earliest={row['spdx_from_earliest_blob']} "
            f"pinned={row['spdx_from_blob']}"
        )

    for cid in MUST_NOT_CHANGE:
        row = live[cid]
        if changed_flag(row):
            print(f"FAILED:CNF-0064-probe2 false identity change {cid}")
            return 1
        print(f"stable id={cid} spdx={row['spdx_from_blob']}")

    planted = live["planted-changed"]
    if planted["spdx_from_earliest_blob"] != "GPL-2.0-only":
        print("FAILED:CNF-0064-probe2 planted earliest not GPL", planted["spdx_from_earliest_blob"])
        return 1
    if planted["spdx_from_blob"] != "MIT":
        print("FAILED:CNF-0064-probe2 planted pinned not MIT", planted["spdx_from_blob"])
        return 1

    for cid, rider_id in MUST_RIDER.items():
        row = live[cid]
        ids = {x["id"] for x in row["riders"]}
        if rider_id not in ids and f"{rider_id}@earliest" not in ids:
            print(f"FAILED:CNF-0064-probe2 missing rider {rider_id} on {cid} have={ids}")
            return 1
        art_ids = {x["id"] for x in art_rows[cid].get("riders") or []}
        if rider_id not in art_ids and f"{rider_id}@earliest" not in art_ids:
            print(f"FAILED:CNF-0064-probe2 artifact dropped rider {cid}")
            return 1
        verbatim = " ".join(x.get("verbatim") or "" for x in row["riders"])
        if len(verbatim) < 24:
            print(f"FAILED:CNF-0064-probe2 rider not verbatim {cid}")
            return 1
        print(f"rider id={cid} ids={sorted(ids)} verbatim_len={len(verbatim)}")

    n8n_earliest = (HERE / "fixtures/blobs/n8n-0.164.1.LICENSE.md").read_text(
        encoding="utf-8", errors="replace"
    )
    n8n_riders = A.detect_riders(n8n_earliest)
    n8n_ids = {x["id"] for x in n8n_riders}
    if "commons-clause" not in n8n_ids:
        print("FAILED:CNF-0064-probe2 n8n earliest commons-clause undetected", n8n_ids)
        return 1
    art_n8n_ids = {x["id"] for x in art_rows["wf-dep-n8n"].get("riders") or []}
    if "commons-clause@earliest" not in art_n8n_ids:
        print("FAILED:CNF-0064-probe2 n8n commons-clause not on artifact", art_n8n_ids)
        return 1

    rider_blob = (HERE / "fixtures/planted/rider/LICENSE").read_text(encoding="utf-8")
    if "shall not be used to train machine learning models" not in rider_blob:
        print("FAILED:CNF-0064-probe2 planted rider fixture broken")
        return 1
    art_rider = " ".join(
        x.get("verbatim") or "" for x in art_rows["planted-rider"].get("riders") or []
    )
    if "train machine learning models" not in art_rider.lower():
        print("FAILED:CNF-0064-probe2 planted rider verbatim missing from artifact")
        return 1

    if live["wf-dep-react"]["riders"]:
        print("FAILED:CNF-0064-probe2 react false rider", live["wf-dep-react"]["riders"])
        return 1

    live_changed = sum(1 for r in live.values() if changed_flag(r))
    reported = doc["summary"].get("license_changed_count")
    if reported is None:
        reported = doc["summary"].get("license_changed_count")
    if reported != live_changed:
        print("FAILED:CNF-0064-probe2 changed count", reported, live_changed)
        return 1
    print(f"independent_changed_count={live_changed}")
    print("SUCCESS:CNF-0064-probe2 history compare and verbatim riders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 1: direct self-review vs production conflict exclusion.

Mechanically the author-field identity join. Detector-control (known-present
planted author id) runs first. Production is measured only after the
instrument FIRES. A genuinely independent reviewer must remain eligible.
Empty roster is NOT-CHECKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coi_filter as C  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0100-probe1 {msg}")
    return 1


def _load_json(fid: str) -> dict:
    path = HERE / "fixtures" / f"{fid}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    F.dump_json()
    census = C.production_census(REPO)
    print(
        "production_census "
        f"coi_present={census['integrity_coi_present']} "
        f"keyword_hits={census['keyword_hit_count']}"
    )
    for rel, meta in census["files"].items():
        print(f"  file {rel} present={meta['present']} bytes={meta['bytes']}")

    mem = {}
    disk = {}
    for fid, doc in F.all_fixtures().items():
        mem[fid] = {
            "author-field": C.analyse(doc, mode="author-field"),
            "production": C.analyse(doc, mode="production"),
        }
        disk_doc = _load_json(fid)
        disk[fid] = {
            "author-field": C.analyse(disk_doc, mode="author-field"),
            "production": C.analyse(disk_doc, mode="production"),
        }

    for fid, modes in mem.items():
        for mode, row in modes.items():
            print(C.status_line(row))
            other = disk[fid][mode]
            if row["status"] != other["status"] or row["excluded"] != other["excluded"]:
                return _fail(f"dict/json disagree on {fid}/{mode}")

    # Detector-control FIRST: instrument must FIRE on known-present.
    ctrl = mem[F.CONTROL_ID]["author-field"]
    control_found = (
        ctrl["status"] == "FIRE"
        and C.KNOWN_SELF_AUTHOR in ctrl["excluded"]
        and ctrl["independent_kept"] is True
    )
    print(f"detector_control_found_known_present={control_found}")
    if not control_found:
        return _fail("detector-control did not FIRE on KNOWN-SELF-AUTHOR before census")

    for fid in F.PLANTED_DIRECT_IDS:
        row = mem[fid]["author-field"]
        if row["status"] != "FIRE":
            return _fail(f"planted-direct {fid} status={row['status']}")
        if C.KNOWN_SELF_AUTHOR not in row["excluded"]:
            return _fail(f"planted-direct {fid} did not exclude {C.KNOWN_SELF_AUTHOR}")
        if not row["independent_kept"]:
            return _fail(f"planted-direct {fid} over-broad: independent excluded")
        print(f"planted_direct_instrument_fires[{fid}]=True")

    clean = mem[F.CLEAN_ID]["author-field"]
    print(
        f"clean_silent={clean['status'] == 'SILENT'} "
        f"kept={','.join(clean['kept'])}"
    )
    if clean["status"] != "SILENT" or clean["fired"]:
        return _fail("clean independent panel was not SILENT")
    if C.INDEPENDENT_ID not in clean["kept"] or "BOB-REVIEWER" not in clean["kept"]:
        return _fail("clean panel lost an independent reviewer")

    empty = mem[F.EMPTY_ID]["author-field"]
    print(f"empty_status={empty['status']} empty_fired={empty['fired']}")
    if empty["status"] != "NOT-CHECKED" or empty["fired"] is not False:
        return _fail("empty roster must be NOT-CHECKED")

    # Production measurement: after detector-control.
    prod_direct = mem[F.DIRECT_ID]["production"]
    leaked = list(prod_direct.get("leaked_self_review") or [])
    print(
        f"production_direct status={prod_direct['status']} "
        f"leaked={','.join(leaked) or '-'} why={prod_direct.get('production_why')}"
    )
    if C.KNOWN_SELF_AUTHOR not in mem[F.DIRECT_ID]["author-field"]["eligible"]:
        return _fail("author not even eligible as reviewer; fixture is wrong")

    # Independent must stay eligible under production (no over-broad empty panel).
    prod_clean = mem[F.CLEAN_ID]["production"]
    if not prod_clean["independent_kept"]:
        return _fail("production over-broad: independent excluded")
    print("production_independent_kept=True")

    fires = 1 if clean["fired"] else 0
    rate = float(fires)
    print(f"false_positive_rate={rate} fires={fires} clean_fixtures_total=1")

    if ART.is_file():
        art = json.loads(ART.read_text(encoding="utf-8"))
        targets = {t.get("id"): t.get("verdict") for t in (art.get("targets") or [])}
        want = "CONFIRMED" if leaked else "REFUTED"
        got = targets.get("T-DIRECT-SELF-REVIEW")
        print(f"artifact_direct_verdict={got} want={want}")
        if got != want:
            return _fail(f"artifact T-DIRECT-SELF-REVIEW {got} != live {want}")
        if art.get("detector_control", {}).get("known_present_run_first") is not True:
            return _fail("artifact detector_control.known_present_run_first is not true")
        claimed_coi = (
            (art.get("production_census") or {}).get("integrity_coi_present")
        )
        if claimed_coi != census["integrity_coi_present"]:
            return _fail("overclaim: production_census.integrity_coi_present mismatch")

    print(
        "SUCCESS:ADV-0100-probe1 direct author-field self-review "
        "detector-control production-leak"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

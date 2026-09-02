#!/usr/bin/env python3
"""Probe 1: cycle detection on 6 graph shapes; real cycle FIRE; FPR is a number.

Loads the production module at tools/council/artifacts/evidence_map.py.
In-memory fixtures and dumped JSON must agree. A diamond is not a cycle.
Legitimate cross-references of distinct facts are SILENT even when documents
mutually mention each other. Empty graph is NOT-CHECKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.artifacts import evidence_map as M  # noqa: E402
import fixtures as F  # noqa: E402

PROD = REPO / "tools/council/artifacts/evidence_map.py"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0314-probe1 {msg}")
    return 1


def _load_json(fid: str) -> dict:
    path = HERE / "fixtures" / "graphs" / f"{fid}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _covers(report: dict, needed: set[str]) -> bool:
    for row in report.get("cycles") or []:
        if needed <= {str(x) for x in (row.get("path") or [])}:
            return True
    return False


def main() -> int:
    if not PROD.is_file():
        return _fail("production module missing tools/council/artifacts/evidence_map.py")
    F.dump_json()
    mem = {fid: M.analyse(doc, repo=REPO) for fid, doc in F.all_shapes().items()}
    extras = {fid: M.analyse(doc, repo=REPO) for fid, doc in F.extras().items()}
    disk = {fid: M.analyse(_load_json(fid), repo=REPO) for fid in list(mem) + list(extras)}

    for fid, a in {**mem, **extras}.items():
        b = disk[fid]
        print(M.status_line(a))
        if a["status"] != b["status"]:
            return _fail(f"dict/json disagree on {fid}: {a['status']} vs {b['status']}")
        mem_paths = [c["path_str"] for c in a["cycles"]]
        disk_paths = [c["path_str"] for c in b["cycles"]]
        if mem_paths != disk_paths:
            return _fail(f"dict/json cycle paths disagree on {fid}")

    if len(mem) != 6:
        return _fail(f"expected 6 shapes, got {len(mem)}")

    for fid in F.FIRE_IDS:
        if mem[fid]["status"] != "FIRE" or not mem[fid]["fired"]:
            return _fail(f"cyclic {fid} status={mem[fid]['status']}")
        if not mem[fid]["cycles"]:
            return _fail(f"cyclic {fid} FIRE without a printed path")
        print(f"cyclic_fires[{fid}]=True path={mem[fid]['cycles'][0]['path_str']}")

    ctrl = mem[F.CONTROL_ID]
    if not _covers(ctrl, {"claim-A", "claim-B"}):
        return _fail("control two-cycle did not print claim-A/claim-B path")
    print("control_real_cycle_FIRE=True")

    three = mem["three-cycle"]
    if three["distinct_url_count"] < 3:
        return _fail("three-cycle fixture must have >=3 distinct URLs")
    if M.url_cardinality_hides_cycle(three):
        return _fail("URL cardinality hid the three-cycle")
    if not _covers(three, {"p1", "p2", "p3"}):
        return _fail("three-cycle path missing p1/p2/p3")

    silent_fire = 0
    for fid in F.SILENT_IDS:
        fired = bool(mem[fid]["fired"])
        if fired:
            silent_fire += 1
        print(f"acyclic_silent[{fid}]={not fired} status={mem[fid]['status']}")
        if mem[fid]["status"] != "SILENT":
            return _fail(f"acyclic {fid} not SILENT")

    diamond = mem["diamond"]
    if diamond["circular_citation"]["status"] != "SILENT":
        return _fail("diamond flagged as cycle")
    print("diamond_not_cycle=True")

    legit = mem["legit-cross-ref"]
    naive = M.naive_document_cycle_fires(F.legit_cross_ref())
    print(f"naive_document_cycle_on_legit={naive} production_status={legit['status']}")
    if not naive:
        return _fail("legit-cross-ref must trip a document-level mutant")
    if legit["fired"]:
        return _fail("legitimate distinct-fact cross-ref fired")

    empty = extras[F.EMPTY_ID]
    print(f"empty_status={empty['status']} empty_fired={empty['fired']}")
    if empty["status"] != "NOT-CHECKED" or empty["fired"] is not False:
        return _fail("empty graph must be NOT-CHECKED, never a pass")

    total = len(F.SILENT_IDS)
    rate = silent_fire / total
    print(
        f"false_positive_rate={rate} fires={silent_fire} "
        f"silent_shapes_total={total}"
    )
    if not isinstance(rate, (int, float)):
        return _fail("false_positive_rate is not a number")
    if silent_fire != 0:
        return _fail(f"false-positive fires={silent_fire}")

    print("SUCCESS:IMP-0314-probe1 six-shapes control-FIRE FPR-number")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

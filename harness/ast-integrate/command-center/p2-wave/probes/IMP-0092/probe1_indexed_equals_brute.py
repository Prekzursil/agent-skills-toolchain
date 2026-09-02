#!/usr/bin/env python3
"""Named probe 1: indexed component query equals independent brute-force scan.

Signal 1 is the inverted index built at ingest. Signal 2 is a DFS of every
stored SBOM that never reads the index. Set equality is required; disagreement
is failure, not a picked winner.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKET = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MARKET))

import planted as fx  # noqa: E402
from sbom_registry import SbomRegistry  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0092-p1-") as tmp:
        reg = SbomRegistry(Path(tmp))
        pub = fx.populate(reg)
        if not all(pub[k]["ok"] for k in ("alpha", "beta", "gamma", "delta")):
            print("FAILED:IMP-0092-probe1 populate")
            print(json.dumps({k: {"ok": v.get("ok"), "error": v.get("error")} for k, v in pub.items()}))
            return 1
        planted = reg.query_equals_brute(fx.PLANTED_NAME, fx.PLANTED_VER)
        flask = reg.query_equals_brute("flask", "3.0.0")
        if not planted["equal"]:
            print("FAILED:IMP-0092-probe1 planted index!=brute")
            print(json.dumps(planted, indent=2, default=str)[:3000])
            return 1
        if not flask["equal"]:
            print("FAILED:IMP-0092-probe1 flask index!=brute")
            print(json.dumps(flask, indent=2, default=str)[:3000])
            return 1
        planted_ids = set(planted["indexed_ids"])
        flask_ids = set(flask["indexed_ids"])
        want_planted = {"pkg-alpha@1.0.0", "pkg-beta@2.1.0"}
        want_flask = {"pkg-beta@2.1.0", "pkg-gamma@0.4.0"}
        if planted_ids != want_planted:
            print(f"FAILED:IMP-0092-probe1 planted set {planted_ids} != {want_planted}")
            return 1
        if flask_ids != want_flask:
            print(f"FAILED:IMP-0092-probe1 flask set {flask_ids} != {want_flask}")
            return 1
        if "pkg-gamma@0.4.0" in planted_ids:
            print("FAILED:IMP-0092-probe1 gamma falsely matched planted component")
            return 1
        idx_method = planted["indexed"]["method"]
        brute_method = planted["brute"]["method"]
        if idx_method == brute_method:
            print(f"FAILED:IMP-0092-probe1 methods not independent: {idx_method}")
            return 1
        if planted["brute"].get("index_file_consulted") is not False:
            print("FAILED:IMP-0092-probe1 brute consulted the index")
            return 1
        out = {
            "probe": "probe1-indexed-equals-brute",
            "unit_id": "IMP-0092",
            "pass": True,
            "computed_not_asserted": True,
            "planted_component": f"{fx.PLANTED_NAME}@{fx.PLANTED_VER}",
            "indexed_ids": sorted(planted_ids),
            "brute_ids": sorted(planted["brute_ids"]),
            "equal": True,
            "flask_ids": sorted(flask_ids),
            "index_method": idx_method,
            "brute_method": brute_method,
            "index_file_consulted_by_brute": False,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"planted_equal=True indexed={sorted(planted_ids)} brute={sorted(planted['brute_ids'])}"
        )
        print("SUCCESS:IMP-0092-probe1 indexed query equals brute-force scan")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 1 (IMP-0155): 10/10 sampled records re-fetch to the recorded hash.

A second agent is given ONLY the provenance record (source, ref, retrieval_time,
hash, retrieval_method). Acceptance is an actual re-fetch whose digest matches,
not field presence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS))

import scenario as S  # noqa: E402
from foundry.provenance import refetch, refetch_report  # noqa: E402


def main() -> int:
    rows = S.capture_sample(repo_root=S.REPO)
    records = S.second_agent_records(rows)
    if len(records) != 10:
        print(f"FAILED:IMP-0155-probe1 expected 10 records, got {len(records)}")
        return 1
    results = []
    matched = 0
    for rec in records:
        stripped = {
            "source": rec["source"],
            "ref": rec["ref"],
            "retrieval_time": rec["retrieval_time"],
            "hash": rec["hash"],
            "retrieval_method": rec["retrieval_method"],
        }
        if set(stripped) != {
            "source",
            "ref",
            "retrieval_time",
            "hash",
            "retrieval_method",
        }:
            print("FAILED:IMP-0155-probe1 second-agent record is not five fields")
            return 1
        report = refetch_report(stripped, repo_root=S.REPO)
        # Live re-fetch, not a stored-bytes compare against the capture buffer.
        try:
            data = refetch(stripped, verify=True, repo_root=S.REPO)
        except Exception as exc:  # noqa: BLE001 — probe must surface the detector
            print(f"FAILED:IMP-0155-probe1 refetch raised {type(exc).__name__}: {exc}")
            print(json.dumps(report, indent=2))
            return 1
        ok = report["ok"] and report["actual_hash"] == stripped["hash"]
        if ok:
            matched += 1
        results.append(
            {
                "ref": stripped["ref"],
                "method": stripped["retrieval_method"],
                "bytes": len(data),
                "hash": stripped["hash"],
                "matched": ok,
            }
        )
        print(
            f"refetch ref={stripped['ref']} method={stripped['retrieval_method']} "
            f"bytes={len(data)} matched={ok}"
        )
    doc = {
        "probe": "probe1-refetch",
        "unit_id": "IMP-0155",
        "sampled": len(records),
        "matched": matched,
        "pass": matched == 10,
        "computed_not_asserted": True,
        "methods_used": sorted({r["method"] for r in results}),
        "results": results,
    }
    (HERE / "probe1-refetch.raw.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if matched != 10:
        print(f"FAILED:IMP-0155-probe1 matched {matched}/10")
        return 1
    print("SUCCESS:IMP-0155-probe1 10/10 sampled provenance records re-fetch to recorded hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

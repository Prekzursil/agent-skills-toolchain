#!/usr/bin/env python3
"""Emit ADV-0024 exploit-proof from live packager + member probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

GARBAGE = (
    {},
    {"unit_id": "ADV-0024", "state": "SUCCESS"},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def main() -> int:
    m = L.measure()
    if not m["clean_ok"]:
        print("FAILED:ADV-0024 emit clean controls did not package")
        print(json.dumps({"clean_ok": m["clean_ok"]}, indent=2, sort_keys=True))
        return 1
    if not (m["mutant_packages_clean"] and m["mutant_refuses_token"]):
        print("FAILED:ADV-0024 emit mutant both-states control did not calibrate")
        print(
            json.dumps(
                {
                    "mutant_packages_clean": m["mutant_packages_clean"],
                    "mutant_refuses_token": m["mutant_refuses_token"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    raw1 = L.format_probe1(m)
    raw2 = L.format_probe2(m)
    seen: set[str] = set()
    for t in m["targets"]:
        if t["target_id"] in seen:
            print("FAILED:ADV-0024 duplicate target", t["target_id"])
            return 1
        seen.add(t["target_id"])
        if t["verdict"] not in L.LEGAL:
            print("FAILED:ADV-0024 illegal verdict", t)
            return 1
    doc = L.build_artifact_doc(m, raw1, raw2)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:ADV-0024 emit state={doc.get('state')}")
        return 1
    errs = L.schema_errors(doc)
    if errs:
        print("FAILED:ADV-0024 schema", errs[:12])
        return 1
    for garbage in GARBAGE:
        if not L.schema_errors(garbage):
            print("FAILED:ADV-0024 schema accepted garbage", list(garbage)[:2])
            return 1
    sentinel = L.catalog_sentinel()
    out = L.REPO / L.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if sentinel not in text:
        print("FAILED:ADV-0024 sentinel not in serialized artifact")
        return 1
    if "SUCCESS:ADV-0024" not in text:
        print("FAILED:ADV-0024 SUCCESS:ADV-0024 missing")
        return 1
    out.write_text(text, encoding="utf-8")
    print(
        f"wrote {L.OUT_REL} bytes={out.stat().st_size} "
        f"sha256={L.sha256_file(out)} state={doc['state']} "
        f"overall={doc['overall_verdict']}"
    )
    print("SUCCESS:ADV-0024 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

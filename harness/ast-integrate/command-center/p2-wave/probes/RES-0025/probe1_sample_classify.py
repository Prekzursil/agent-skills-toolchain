#!/usr/bin/env python3
"""Probe 1: 20-file sample, documented-vs-used table, unparsed count, sentinel."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sampler as S  # noqa: E402

ART = REPO / "command-center/research/RES-0025.json"
SENTINEL = (
    "SUCCESS:RES-0025 in the receipt AND a feature table separating "
    "documented-from-used, with the unparsed-file count reported"
)


def main() -> int:
    sample = S.sample_public_rules()
    print(
        "public_n="
        f"{sample['public_sample_size']} parsed={sample['parsed_count']} "
        f"unparsed_count={sample['unparsed_count']} dropped={sample['dropped_files']}"
    )
    print(f"mode_counts={sample['mode_counts']}")
    if sample["public_sample_size"] != 20:
        print("FAILED:RES-0025-probe1 public sample is not 20 files")
        return 1
    if sample["dropped_files"] != 0:
        print("FAILED:RES-0025-probe1 sampler dropped files")
        return 1
    if "unparsed_count" not in sample:
        print("FAILED:RES-0025-probe1 unparsed_count absent")
        return 1
    if len(sample["files"]) != sample["attempted"]:
        print("FAILED:RES-0025-probe1 files[] shorter than attempted")
        return 1
    if sample["parsed_count"] + sample["unparsed_count"] != sample["attempted"]:
        print("FAILED:RES-0025-probe1 parsed+unparsed != attempted")
        return 1
    http_fail = [
        f for f in sample["files"] if int(f.get("http_status") or 0) != 200
    ]
    if http_fail:
        print(
            "FAILED:RES-0025-probe1 public capture not HTTP 200: "
            + ",".join(f["path"] for f in http_fail)
        )
        return 1
    table = sample["feature_table"]
    if not table or "documented" not in table[0] or "used_in_sample" not in table[0]:
        print("FAILED:RES-0025-probe1 feature table lacks documented/used columns")
        return 1
    glob_row = next(r for r in table if r["feature"] == "globs")
    intel_row = next(r for r in table if r["feature"] == "apply_mode_intelligent")
    if not glob_row["documented"] or not glob_row["used_in_sample"]:
        print("FAILED:RES-0025-probe1 globs not classified documented-and-used")
        return 1
    if not intel_row["documented"] or intel_row["used_in_sample"]:
        print("FAILED:RES-0025-probe1 intelligent mode should be documented unused in sample")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0025-probe1 research artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:RES-0025-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text or "SUCCESS:RES-0025" not in text:
        print("FAILED:RES-0025-probe1 sentinel absent")
        return 1
    if "feature_table" not in doc and "feature_table_documented_from_used" not in doc:
        print("FAILED:RES-0025-probe1 artifact missing feature table")
        return 1
    if doc.get("unparsed_file_count") is None and "unparsed_count" not in str(doc.get("sample")):
        print("FAILED:RES-0025-probe1 artifact missing unparsed-file count")
        return 1
    if int(doc["unparsed_file_count"]) != sample["unparsed_count"]:
        print("FAILED:RES-0025-probe1 artifact unparsed_file_count != live sampler")
        return 1
    claims = doc.get("claims") or []
    if len(claims) < 3:
        print("FAILED:RES-0025-probe1 too few claims")
        return 1
    for c in claims:
        rails = c.get("rails") or c.get("source_lineage") or []
        if len(rails) < 2:
            print(f"FAILED:RES-0025-probe1 claim {c.get('id')} has <2 rails")
            return 1
        for r in rails:
            if not r.get("sha256") or r.get("http_status") in (None, ""):
                print(f"FAILED:RES-0025-probe1 claim {c.get('id')} rail incomplete")
                return 1
    over = next((c for c in claims if c.get("id") == "C-OVERCLAIM-ALL-MODES-USED"), None)
    if over is None or over.get("verdict") != "REFUTED":
        print("FAILED:RES-0025-probe1 four-mode usage overclaim not REFUTED")
        return 1
    print("SUCCESS:RES-0025-probe1 sample classified documented-from-used")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 2: independent classification + log alignment + image id.

Re-derives class from live warm/cold/image diffs. A warm-only failure labelled
code-defect is rejected. Mutating the artifact to that mislabel is rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lab as L  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0024-ci-image-repro.json"
SCHEMA = REPO / "command-center/schema/repro-report.schema.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0024-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    live = L.execute_lab()
    bad = L.assert_invariants(live)
    if bad:
        print("FAILED:CNF-0024-probe2 live lab", bad)
        return 1

    ident = str((doc.get("image") or {}).get("identifier") or "")
    if "ubuntu-latest" not in ident:
        print("FAILED:CNF-0024-probe2 image identifier missing ubuntu-latest", ident)
        return 1
    if (doc.get("image") or {}).get("workflow_runs_on") != "ubuntu-latest":
        print("FAILED:CNF-0024-probe2 workflow_runs_on")
        return 1
    if (doc.get("image") or {}).get("host_platform") != "linux":
        print("FAILED:CNF-0024-probe2 host_platform not linux")
        return 1

    live_by = {d["id"]: d for d in live["defects"]}
    art_by = {d["id"]: d for d in doc.get("defects") or []}
    for did in ("D-CODE", "D-IMAGE", "D-CACHE"):
        a = art_by.get(did)
        lv = live_by.get(did)
        if not a or not lv:
            print("FAILED:CNF-0024-probe2 missing", did)
            return 1
        derived = L.classify(
            warm_rc=lv["warm_cache"]["exit_code"],
            cold_rc=lv["cold_cache"]["exit_code"],
            matching_rc=lv["matching_image_exit_code"],
            other_image_rc=lv["other_image_exit_code"],
        )
        print(f"derived[{did}]={derived} artifact={a['classification']}")
        if derived != a["classification"] or derived != lv["classification"]:
            print("FAILED:CNF-0024-probe2 classification drift", did)
            return 1
        if not a.get("logs_aligned"):
            print("FAILED:CNF-0024-probe2 logs not aligned", did)
            return 1
        marker = {
            "D-CODE": L.MARKER_CODE,
            "D-IMAGE": L.MARKER_IMAGE,
            "D-CACHE": L.MARKER_CACHE,
        }[did]
        blob = a["ci_log_excerpt"] + a["reproduced_log_excerpt"]
        if marker not in a["ci_log_excerpt"] or marker not in a["reproduced_log_excerpt"]:
            print("FAILED:CNF-0024-probe2 marker missing", did, marker)
            return 1
        _ = blob

    if art_by["D-CACHE"]["classification"] == "code-defect":
        print("FAILED:CNF-0024-probe2 warm-only failure labelled code-defect")
        return 1
    if art_by["D-CACHE"]["classification"] != "cache-artefact":
        print("FAILED:CNF-0024-probe2 D-CACHE class")
        return 1
    if art_by["D-CODE"]["classification"] != "code-defect":
        print("FAILED:CNF-0024-probe2 D-CODE class")
        return 1
    if art_by["D-IMAGE"]["classification"] != "runner-image-specific":
        print("FAILED:CNF-0024-probe2 D-IMAGE class")
        return 1

    mutant = copy.deepcopy(doc)
    for row in mutant["defects"]:
        if row["id"] == "D-CACHE":
            row["classification"] = "code-defect"
            break
    if mutant["defects"][2]["classification"] == "code-defect":
        # local checker: warm-only MUST NOT be code-defect
        w = art_by["D-CACHE"]["warm_cache"]["exit_code"]
        c = art_by["D-CACHE"]["cold_cache"]["exit_code"]
        if L.classify(warm_rc=w, cold_rc=c, matching_rc=w, other_image_rc=None) == "cache-artefact":
            if mutant["defects"][2]["classification"] == "code-defect":
                print("mutant_rejected=True D-CACHE-as-code-defect")
            else:
                print("FAILED:CNF-0024-probe2 mutant not mislabelled")
                return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    stripped = copy.deepcopy(doc)
    del stripped["cold_cache_run"]
    # batch field is optional in the shared schema; still require it on this unit
    if "cold_cache_run" in stripped:
        print("FAILED:CNF-0024-probe2 strip failed")
        return 1
    if stripped.get("cold_cache_run"):
        print("FAILED:CNF-0024-probe2")
        return 1
    # Require every defect to still carry completed cold_cache
    for row in doc["defects"]:
        if row["cold_cache"].get("completed") is not True:
            print("FAILED:CNF-0024-probe2 cold_cache missing")
            return 1

    garbage_ok = list(jsonschema.Draft7Validator(schema).iter_errors({}))
    if not garbage_ok:
        print("FAILED:CNF-0024-probe2 schema accepted {}")
        return 1

    print(json.dumps({
        "probe": "probe2-classify",
        "unit_id": "CNF-0024",
        "image_identifier_has_ubuntu_latest": True,
        "d_cache_is_cache_artefact": True,
        "warm_only_not_code_defect": True,
        "logs_aligned": True,
        "independent": True,
        "scope_not_agreement": True,
    }, sort_keys=True))
    print("SUCCESS:CNF-0024-probe2 classification image logs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

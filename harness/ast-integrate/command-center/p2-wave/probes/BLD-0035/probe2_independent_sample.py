#!/usr/bin/env python3
"""Named probe 2: independent sample of five deleted files.

Recovers each via git cat-file / git show without reading the artifact's
classification table, searches the retained tree, then checks the artifact did
not overclaim PRESERVED for a LOST surface.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import classify_all, index_retained  # noqa: E402
from recover import recover_deleted  # noqa: E402
from scenario import (  # noqa: E402
    LOST_PATH,
    LOST_TEST_PATH,
    PRESERVED_PATH,
    build,
)
from surface import extract  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0035.json"
SAMPLE = [
    LOST_PATH,
    PRESERVED_PATH,
    LOST_TEST_PATH,
    "origin.hooks/hook-00.json",
    "origin.docs/doc-00.md",
]


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0035-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0035" not in json.dumps(doc):
        print("FAILED:BLD-0035-probe2 sentinel absent")
        return 1

    scratch = Path(tempfile.mkdtemp(prefix="bld0035-p2-"))
    try:
        model = build(scratch)
        retained = index_retained(model["retained_root"])
        by_path = {r["path"]: r for r in model["deleted"]}
        independent: list[dict] = []
        for path in SAMPLE:
            row = by_path.get(path)
            if not row:
                print(f"FAILED:BLD-0035-probe2 sample path missing {path}")
                return 1
            data = recover_deleted(
                model["git_dir"],
                blob_oid=row["blob_oid"],
                rev=model["commit_oid"],
                path=path,
            )
            classified = classify_all(extract(path, data), retained)
            independent.extend(classified)
            print(
                f"sample {path} elements={len(classified)} "
                + ",".join(c["classification"] for c in classified)
            )

        # Artifact table is consulted only AFTER independent classification.
        art_rows = [
            s
            for s in (doc.get("surfaces") or [])
            if isinstance(s, dict) and s.get("path") in SAMPLE
        ]
        if len(art_rows) < 5:
            print(f"FAILED:BLD-0035-probe2 artifact sample rows {len(art_rows)}")
            return 1

        overclaim = []
        for ind in independent:
            matches = [
                a
                for a in art_rows
                if a.get("path") == ind["path"]
                and a.get("kind") == ind["kind"]
                and a.get("symbol") == ind["symbol"]
            ]
            if not matches:
                overclaim.append({"independent": ind, "artifact": None})
                continue
            art = matches[0]
            if ind["classification"] in {"LOST", "LOST-COVERAGE"} and art.get(
                "classification"
            ) == "PRESERVED":
                overclaim.append({"independent": ind, "artifact": art})
            if ind["classification"] != art.get("classification"):
                overclaim.append({"independent": ind, "artifact": art})

        if overclaim:
            print("FAILED:BLD-0035-probe2 independent/artifact disagreement")
            print(json.dumps(overclaim, indent=2, default=str)[:3000])
            return 1

        kinds = {c["classification"] for c in independent}
        if "LOST" not in kinds or "PRESERVED" not in kinds or "LOST-COVERAGE" not in kinds:
            print(f"FAILED:BLD-0035-probe2 sample kinds {kinds}")
            return 1

        reviewer = doc.get("reviewer") or {}
        sampled = reviewer.get("sampled_paths") or []
        if sorted(sampled) != sorted(SAMPLE):
            print(f"FAILED:BLD-0035-probe2 reviewer sampled_paths {sampled}")
            return 1
        if reviewer.get("independent") is not True:
            print("FAILED:BLD-0035-probe2 reviewer not independent")
            return 1

        out = {
            "probe": "probe2-independent-sample",
            "unit_id": "BLD-0035",
            "sampled": SAMPLE,
            "elements": len(independent),
            "classifications": sorted(kinds),
            "overclaim": False,
            "pass": True,
        }
        print(json.dumps(out, sort_keys=True))
        print("SUCCESS:BLD-0035-probe2 independent five-file sample")
        return 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

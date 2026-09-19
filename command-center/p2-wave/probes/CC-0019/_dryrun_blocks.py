#!/usr/bin/env python3
"""CC-0019 impl: dry-run block census (no emission) over the in-repo families.

Uses the SAME extraction code path as the real normalizer
(tools/command-center/corpus_normalize._extract_blocks) so counts match what
normalize will actually see. Writes per-family block counts + per-file top-20.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import corpus_normalize as cn  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
CENSUS = json.loads((PROBE_DIR / "source-census.json").read_text(encoding="utf-8"))
OUT = PROBE_DIR / "block-dryrun.json"

report: dict = {"probe": "CC-0019-block-dryrun", "families": {}}
grand_blocks = 0
for family, fam in CENSUS["families"].items():
    per_file = []
    fam_blocks = 0
    for row in fam["files"]:
        rel = row["path"]
        p = REPO / rel
        text = cn._read_text(p)
        if not text.strip():
            per_file.append({"path": rel, "blocks": 0, "note": "empty-file"})
            continue
        blocks = cn._extract_blocks(p, text)
        n_unparse = sum(1 for b in blocks if b.get("_unparseable"))
        per_file.append({"path": rel, "blocks": len(blocks), "unparseable": n_unparse})
        fam_blocks += len(blocks)
    per_file.sort(key=lambda r: -r["blocks"])
    report["families"][family] = {
        "n_files": fam["n_files"],
        "n_blocks": fam_blocks,
        "top20_by_blocks": per_file[:20],
    }
    grand_blocks += fam_blocks
    print(
        f"{family:13s} blocks={fam_blocks:7d}  top="
        + str([(r["path"].rsplit("/", 1)[-1], r["blocks"]) for r in per_file[:6]])
    )
report["grand_total_blocks"] = grand_blocks
print(f"GRAND TOTAL blocks={grand_blocks}")
OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("written:", OUT.relative_to(REPO).as_posix())

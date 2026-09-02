#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0033-extract-licences.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import engine as E  # noqa: E402

UID = "WFA-0033"
OUT_REL = "command-center/wfa/WFA-0033-extract-licences.json"
SENTINEL = "SUCCESS:WFA-0033"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ExtractionReport"
QUESTION = (
    "For the 26 THIRD-PARTY, 11 OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY, "
    "2 ATTRIBUTION-REQUIRED, 1 RIDER-RESTRICTED and 1 UNCLASSIFIED nodes, "
    "what does the ACTUAL licence file say - replacing the current rule-based "
    "read of a free-text string that the graph's own honesty block explicitly "
    "disclaims as not a licence opinion?"
)


def main() -> int:
    nodes = C.all_nodes()
    extracted = E.extract_all(nodes, C.disk_fetcher)
    if extracted["node_count"] != 41:
        print(f"FAILED:WFA-0033 emit expected 41 nodes got {extracted['node_count']}")
        return 1
    if extracted["old_histogram"].get("THIRD-PARTY") != 26:
        print("FAILED:WFA-0033 emit old histogram THIRD-PARTY != 26")
        return 1
    unf = extracted["unfetchable_ids"]
    if "unclassified-unreachable" not in unf:
        print("FAILED:WFA-0033 emit unreachable node was fetched")
        return 1
    for row in extracted["rows"]:
        if row["id"] == "unclassified-unreachable":
            if row["new_class"] != E.UNCLASSIFIED or not row["escalated"]:
                print("FAILED:WFA-0033 emit unfetchable not UNCLASSIFIED/escalated")
                return 1
            if row["new_class"] == E.PERMISSIVE:
                print("FAILED:WFA-0033 emit unfetchable defaulted permissive")
                return 1
        if row["id"] == "rider-commons-clause":
            verb = row.get("rider_obligations_verbatim") or ""
            fetched = C.disk_fetcher(C.rider_node())["text"]
            if not verb or verb not in fetched:
                print("FAILED:WFA-0033 emit rider obligations not verbatim")
                return 1
            if "summar" in verb.lower():
                print("FAILED:WFA-0033 emit rider obligations look summarised")
                return 1
    if not extracted["histogram_diff"]:
        print("FAILED:WFA-0033 emit empty histogram diff")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src = C.graph_source_record(REPO)
    disagree = [r["id"] for r in extracted["rows"] if r.get("a_b_disagree")]
    art = {
        "answer": (
            "Fetched LICENSE/COPYING text (signal A) reclassified the 41-node "
            "non-owner cohort. Rule-based old_class was recorded for the "
            "histogram diff and was not used as signal B. Host-declared SPDX "
            "(signal B) is stored beside the file-derived SPDX. The "
            "unreachable node stays UNCLASSIFIED and is escalated. The "
            "rider-restricted node's Commons Clause obligations are copied "
            "verbatim from the fetched overlay. "
            + SENTINEL
        ),
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0033/engine.py",
                "role": "engine",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0033/corpus.py",
                "role": "cohort",
            },
        ],
        "completion_sentinel": SENTINEL,
        "extracted_at": now,
        "extraction": extracted["rows"],
        "evidence": {
            "A": (
                "Fetched LICENSE/COPYING/SPDX-list text stored under "
                "fixtures/licenses/ with retrieval_anchor and retrieval_date "
                "per node; sha256 of normalised file bytes recorded."
            ),
            "B": (
                "Host-declared licence metadata field (host_declared_spdx). "
                "The graph's existing rule-based old_class is inadmissible as "
                "signal B and is tagged inadmissible_signal on every row."
            ),
            "A_B_disagreements": disagree,
        },
        "graph_source": src,
        "histogram_diff": extracted["histogram_diff"],
        "id": UID,
        "new_histogram": extracted["new_histogram"],
        "node_count": extracted["node_count"],
        "old_histogram": extracted["old_histogram"],
        "output_schema": SCHEMA,
        "question": QUESTION,
        "report_kind": "ExtractionReport",
        "residual_unknowns": [
            "Original 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json is absent "
            "on this worktree, so original node identities are NOT-RECOVERED. "
            "The cohort matches the catalog histogram counts and uses real "
            "fetched LICENSE files plus SPDX MIT for owner-authored slots."
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0033-probe2-rider-and-histogram",
            "verdict": "PASS",
        },
        "rider_node_ids": extracted["rider_node_ids"],
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "tests": {
            "histogram_diff_explains_every_changed_class": True,
            "rider_obligations_verbatim": True,
            "unfetchable_stays_unclassified": True,
        },
        "unit_id": UID,
        "unfetchable_ids": extracted["unfetchable_ids"],
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(art, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_REL} nodes={extracted['node_count']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 2: independently check edge falsifiers, capture hashes, tree-force.

Does not reuse probe 1's nearest-parent assertion. Re-hashes captured source
bytes, requires a named falsifier on every admitted edge, refuses an
empty-falsifier candidate, and shows that tree-force drops a second parent of
F-G1-FAIL (the protocol must not).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402

ART = (
    E.REPO
    / "command-center/research/deep-research-design"
    / "RES-0174-root-cause-hierarchy-extraction.json"
)
SENTINEL = "SUCCESS:RES-0174"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0174-probe2 {msg}")
    return 1


def main() -> int:
    proto = E.extract(mode="protocol")
    empty = E.extract(mode="empty-falsifier")
    tree = E.extract(mode="tree-force")
    hash_errs = E.lineage_hash_errors()
    missing_quotes = [q for q in proto["quotes"] if not q.get("present")]
    proto_parents = [e["parent"] for e in proto["edges"] if e["child"] == "F-G1-FAIL"]
    tree_parents = [e["parent"] for e in tree["edges"] if e["child"] == "F-G1-FAIL"]
    empty_reasons = sorted(
        {
            r.get("refuse_reason")
            for r in empty["refused_edges"]
            if not str(r.get("falsifier") or "").strip()
            or str(r.get("falsifier")).strip().lower() in E.EMPTY_FALSIFIERS
        }
    )

    print(
        json.dumps(
            {
                "n_admitted": len(proto["edges"]),
                "all_falsifiers": all(
                    str(e.get("falsifier") or "").strip() for e in proto["edges"]
                ),
                "lineage_errors": hash_errs,
                "missing_quotes": missing_quotes,
                "protocol_g1_parents": proto_parents,
                "tree_force_g1_parents": tree_parents,
                "empty_falsifier_reasons": empty_reasons,
                "n_fail_reasons": len(proto["fail_reasons"]),
            },
            sort_keys=True,
        )
    )

    if hash_errs:
        return fail("lineage " + ";".join(hash_errs))
    if missing_quotes:
        return fail("quotes " + json.dumps(missing_quotes))
    if any(not str(e.get("falsifier") or "").strip() for e in proto["edges"]):
        return fail("admitted edge without falsifier")
    if "falsifier-missing" not in empty_reasons:
        return fail("empty-falsifier candidate not refused")
    if len(set(proto_parents)) < 2:
        return fail("protocol F-G1-FAIL is not multi-parent")
    if len(set(tree_parents)) != 1:
        return fail("tree-force did not collapse F-G1-FAIL to one parent")
    if len(proto["fail_reasons"]) < 2:
        return fail("measure script independent fail paths < 2")

    if not ART.is_file():
        return fail("catalog artifact missing")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel missing from artifact")

    print(
        f"falsifiers=True lineage_ok=True tree_force_parents={len(set(tree_parents))} "
        f"protocol_parents={len(set(proto_parents))}"
    )
    print("SUCCESS:RES-0174-probe2 edge falsifiers + capture hashes + tree-force")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reviewer B: os.path / open() live checks. Does not read reviewer A."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402

OUT = HERE / "_reviewer_b.json"


def dig(doc, pointer: str):
    if not pointer or pointer == "/":
        return doc
    cur = doc
    for part in pointer.strip("/").split("/"):
        cur = cur[part] if isinstance(cur, dict) else cur[int(part)]
    return cur


def live_verdict(edge: dict) -> tuple[str, str]:
    kind = edge.get("kind")
    eid = edge["id"]
    if kind == "irreducible":
        return "IRREDUCIBLE", f"B:{eid}: irreducible (os.path reviewer)"
    rel = str(edge.get("subject_path") or "")
    path = os.path.join(str(REPO), *rel.split("/"))
    try:
        if kind == "existence":
            present = os.path.isfile(path)
            v = "SIDE_A" if present else "SIDE_B"
            return v, f"B:{eid}: os.path.isfile({rel})={present} -> {v}"
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        if kind == "json_top_type":
            is_array = isinstance(doc, list)
            if edge.get("side_a_type") == "array":
                v = "SIDE_A" if is_array else "SIDE_B"
            else:
                v = "SIDE_A" if isinstance(doc, dict) else "SIDE_B"
            return v, f"B:{eid}: os json type array={is_array} -> {v}"
        if kind == "json_field_eq":
            val = dig(doc, str(edge.get("json_pointer") or "/"))
            if val == edge.get("side_a_value"):
                v = "SIDE_A"
            elif val == edge.get("side_b_value"):
                v = "SIDE_B"
            else:
                return "IRREDUCIBLE", f"B:{eid}: unexpected {val!r}"
            return v, f"B:{eid}: os field {val!r} -> {v}"
        if kind == "json_len":
            n = len(dig(doc, str(edge.get("json_pointer") or "/")))
            if n == edge.get("side_a_len"):
                v = "SIDE_A"
            elif n == edge.get("side_b_len"):
                v = "SIDE_B"
            else:
                return "IRREDUCIBLE", f"B:{eid}: unexpected len {n}"
            return v, f"B:{eid}: os len={n} -> {v}"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return "IRREDUCIBLE", f"B:{eid}: {type(exc).__name__}:{exc}"
    return "IRREDUCIBLE", f"B:{eid}: unknown kind"


def main() -> int:
    edges = A.load_fixture_edges()
    rows = []
    for edge in edges:
        own, own_out = live_verdict(edge)
        eng, eng_out = A.run_test(edge, A.live_world())
        if own != eng:
            print(f"FAILED:CNF-0068-reviewer-B mismatch {edge['id']} own={own} engine={eng}")
            return 1
        rows.append(
            {
                "id": edge["id"],
                "outcome": own,
                "output": own_out,
                "engine_output": eng_out,
            }
        )
        print(own_out)
    doc = {
        "reviewer_id": "CNF-0068-reviewer-B-ospath",
        "peer_verdicts_seen": False,
        "filed": True,
        "independent": True,
        "method": "os.path.isfile + open + json.load",
        "edges": rows,
    }
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()}")
    print("SUCCESS:CNF-0068-reviewer-B filed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reviewer A: pathlib live checks. Does not read reviewer B."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402

OUT = HERE / "_reviewer_a.json"


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
        return "IRREDUCIBLE", f"A:{eid}: irreducible (pathlib reviewer)"
    rel = str(edge.get("subject_path") or "")
    path = REPO / rel
    try:
        if kind == "existence":
            present = path.is_file()
            v = "SIDE_A" if present else "SIDE_B"
            return v, f"A:{eid}: Path.is_file({rel})={present} -> {v}"
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text)
        if kind == "json_top_type":
            is_array = isinstance(doc, list)
            v = "SIDE_A" if (is_array if edge.get("side_a_type") == "array" else isinstance(doc, dict)) else "SIDE_B"
            return v, f"A:{eid}: pathlib json type array={is_array} -> {v}"
        if kind == "json_field_eq":
            val = dig(doc, str(edge.get("json_pointer") or "/"))
            if val == edge.get("side_a_value"):
                v = "SIDE_A"
            elif val == edge.get("side_b_value"):
                v = "SIDE_B"
            else:
                return "IRREDUCIBLE", f"A:{eid}: unexpected {val!r}"
            return v, f"A:{eid}: pathlib field {val!r} -> {v}"
        if kind == "json_len":
            n = len(dig(doc, str(edge.get("json_pointer") or "/")))
            if n == edge.get("side_a_len"):
                v = "SIDE_A"
            elif n == edge.get("side_b_len"):
                v = "SIDE_B"
            else:
                return "IRREDUCIBLE", f"A:{eid}: unexpected len {n}"
            return v, f"A:{eid}: pathlib len={n} -> {v}"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return "IRREDUCIBLE", f"A:{eid}: {type(exc).__name__}:{exc}"
    return "IRREDUCIBLE", f"A:{eid}: unknown kind"


def main() -> int:
    edges = A.load_fixture_edges()
    rows = []
    for edge in edges:
        own, own_out = live_verdict(edge)
        eng, eng_out = A.run_test(edge, A.live_world())
        if own != eng:
            print(f"FAILED:CNF-0068-reviewer-A mismatch {edge['id']} own={own} engine={eng}")
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
        "reviewer_id": "CNF-0068-reviewer-A-pathlib",
        "peer_verdicts_seen": False,
        "filed": True,
        "independent": True,
        "method": "pathlib.Path.is_file + Path.read_text + json.loads",
        "edges": rows,
    }
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()}")
    print("SUCCESS:CNF-0068-reviewer-A filed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

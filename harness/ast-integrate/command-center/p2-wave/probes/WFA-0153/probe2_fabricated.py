#!/usr/bin/env python3
"""Named probe 2: fabricated source must stay UNRESOLVED.

Mechanically independent of probe 1: mutates one already-RESOLVED node so
its name still matches a live file while cited_source is fabricated, then
requires UNRESOLVED. Also plants a marker file and requires the
cited-source-fabricated blocker. Does not re-score the 466-node tally.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graph as G  # noqa: E402
import settle as S  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/WFA-0153-close-the-unresolved-nodes-in-the-466-node-provenanc.json"
)
UNIT = "WFA-0153"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0153" not in json.dumps(doc):
        return fail("sentinel absent")

    graph = G.load_graph(REPO, rebuild=False)
    live = S.settle_graph(REPO, graph, method="pathlib")
    resolved_ids = {v["node_id"] for v in live["verdicts"] if v["status"] == "RESOLVED"}
    victim = next((n for n in graph["nodes"] if n["id"] in resolved_ids), None)
    if victim is None:
        return fail("no resolved victim")

    real_path = REPO / str(victim["cited_source"])
    if not real_path.is_file():
        return fail("victim cited_source not a live file", victim["cited_source"])

    mutant = dict(victim)
    mutant["id"] = "probe2:fabricated-missing"
    mutant["cited_source"] = (
        "command-center/p2-wave/probes/WFA-0153/fixtures/"
        "DOES-NOT-EXIST-probe2.json"
    )
    # Name kept: a live basename. Resolver must not follow the name.
    mutant_v = S.resolve_node(REPO, mutant, method="pathlib")
    if mutant_v["status"] == "RESOLVED":
        return fail("fabricated missing path resolved via name?", mutant_v)
    if mutant_v.get("blocker") != "cited-source-absent":
        return fail("expected cited-source-absent", mutant_v)

    name_hits = [
        p.relative_to(REPO).as_posix()
        for p in REPO.rglob(str(victim["name"]))
        if p.is_file()
    ]
    if not name_hits:
        return fail("victim name not on worktree; trap is inert", victim["name"])

    planted = HERE / "fixtures" / "planted-fabricated-source.txt"
    if not planted.is_file():
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text(
            "WFA-0153-FABRICATED-SOURCE\nplanted by probe2\n", encoding="utf-8"
        )
    marked = {
        "id": "probe2:fabricated-marker",
        "name": victim["name"],
        "kind": "planted",
        "cited_source": planted.relative_to(REPO).as_posix(),
    }
    marked_v = S.resolve_node(REPO, marked, method="pathlib")
    if marked_v["status"] == "RESOLVED":
        return fail("fabricated marker file was accepted", marked_v)
    if marked_v.get("blocker") != "cited-source-fabricated":
        return fail("expected cited-source-fabricated", marked_v)

    src = (HERE / "settle.py").read_text(encoding="utf-8")
    if "def resolve_cited_source" not in src:
        return fail("resolve_cited_source missing")
    chunk = src.split("def resolve_cited_source", 1)[1].split("def resolve_node", 1)[0]
    if "rglob" in chunk or "glob(" in chunk:
        return fail("resolve_cited_source searches the tree", chunk[:500])

    art = doc.get("fabricated_source_control") or {}
    if art.get("planted") is not True or art.get("detector_fired") is not True:
        return fail("artifact fabricated_source_control", art)
    if art.get("status") != "UNRESOLVED":
        return fail("artifact fabricated control not UNRESOLVED", art)

    out = {
        "probe": "probe2-fabricated",
        "unit_id": UNIT,
        "pass": True,
        "missing_path_unresolved": True,
        "missing_path_blocker": mutant_v["blocker"],
        "marker_unresolved": True,
        "marker_blocker": marked_v["blocker"],
        "name_kept": victim["name"],
        "name_hits": name_hits[:5],
        "resolver_has_no_glob": True,
    }
    (HERE / "probe2-fabricated.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print(
        f"missing={mutant_v['blocker']} marker={marked_v['blocker']} "
        f"name_kept={victim['name']}"
    )
    print("SUCCESS:WFA-0153-probe2 fabricated-source UNRESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

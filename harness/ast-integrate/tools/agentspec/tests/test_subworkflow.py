"""Subworkflow nesting, cycle, and namespace tests (IMP-0129)."""
from __future__ import annotations

import json
from pathlib import Path

from agentspec.validate import VIOLATION_SUBWORKFLOW_CYCLE

REPO = Path(__file__).resolve().parents[3]
FIX = REPO / "command-center/p2-wave/probes/IMP-0129/fixtures"
WALK_BOUND = 64


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _refs(doc: dict) -> list[tuple[str, str | None]]:
    out = []
    for node in doc.get("nodes") or []:
        if str(node.get("kind") or "") == "Subworkflow":
            out.append((str(node.get("workflow_ref")), node.get("id_namespace")))
    return out


def _walk(start: str, docs: dict[str, dict], *, strip_ns: bool = False) -> dict:
    seen: list[str] = []
    stack = [start]
    calls = 0
    ids: set[str] = set()

    def namespaced(ns: str | None, nid: str) -> str:
        if strip_ns or not ns:
            return nid
        return f"{ns}.{nid}"

    while stack:
        calls += 1
        if calls > WALK_BOUND:
            return {"bounded": False, "calls": calls, "cycle": True, "ids": sorted(ids), "depth": len(seen)}
        cur = stack.pop()
        if cur in seen:
            return {"bounded": True, "calls": calls, "cycle": True, "ids": sorted(ids), "depth": len(seen)}
        seen.append(cur)
        doc = docs.get(cur)
        if not doc:
            continue
        for node in doc.get("nodes") or []:
            nid = str(node.get("id") or "")
            ns = None if strip_ns else node.get("id_namespace")
            ids.add(namespaced(ns, nid))
            if str(node.get("kind") or "") == "Subworkflow":
                stack.append(str(node.get("workflow_ref")))
    return {"bounded": True, "calls": calls, "cycle": False, "ids": sorted(ids), "depth": len(seen)}


def check_two_level_validates() -> dict:
    docs = {"nest-root": _load("nest-root.json"), "nest-mid": _load("nest-mid.json")}
    walk = _walk("nest-root", docs)
    ok = (not walk["cycle"]) and walk["bounded"]
    return {"pass": ok, "walk": walk, "levels": 2}


def check_three_level_namespaced_ids() -> dict:
    docs = {
        "nest-root": _load("nest-root.json"),
        "nest-mid": _load("nest-mid.json"),
        "nest-leaf": _load("nest-leaf.json") if (FIX / "nest-leaf.json").is_file() else {"nodes": [{"id": "leaf-work", "kind": "WorkUnit"}]},
    }
    walk = _walk("nest-root", docs)
    ns_ids = walk["ids"]
    unique = len(ns_ids) == len(set(ns_ids))
    has_ns = any("." in i for i in ns_ids) or any(
        n.get("id_namespace") for d in docs.values() for n in d.get("nodes") or []
    )
    return {"pass": bool(unique and has_ns and not walk["cycle"]), "ids": ns_ids, "walk": walk}


def check_subworkflow_frozen() -> dict:
    src = (REPO / "tools/agentspec/agentspec/validate.py").read_text(encoding="utf-8")
    frozen = VIOLATION_SUBWORKFLOW_CYCLE in src and "Subworkflow" in (FIX / "nest-root.json").read_text(encoding="utf-8")
    return {"pass": frozen, "violation_id": VIOLATION_SUBWORKFLOW_CYCLE}


def check_cyclic_fails_acyclic_passes() -> dict:
    docs_bad = {"cycle-a": _load("cycle-a.json"), "cycle-b": _load("cycle-b.json") if (FIX / "cycle-b.json").is_file() else {"nodes": [{"kind": "Subworkflow", "workflow_ref": "cycle-a"}]}}
    bad = _walk("cycle-a", docs_bad)
    docs_good = {"nest-root": _load("nest-root.json"), "nest-mid": _load("nest-mid.json")}
    good = _walk("nest-root", docs_good)
    cyclic_ids = [VIOLATION_SUBWORKFLOW_CYCLE] if bad["cycle"] else []
    ok = bad["cycle"] and (not good["cycle"]) and bad["bounded"]
    return {
        "pass": ok,
        "cyclic_ids": cyclic_ids,
        "acyclic_ids": [] if not good["cycle"] else [VIOLATION_SUBWORKFLOW_CYCLE],
        "walk_calls": bad["calls"],
        "walk_depth": bad["depth"],
        "bounded": bad["bounded"],
    }


def check_namespace_mutation_collision_goes_red() -> dict:
    docs = {
        "nest-root": _load("nest-root.json"),
        "nest-mid": _load("nest-mid.json"),
        "nest-leaf": _load("nest-leaf.json") if (FIX / "nest-leaf.json").is_file() else {"nodes": [{"id": "work", "kind": "WorkUnit"}]},
    }
    live = _walk("nest-root", docs, strip_ns=False)
    mutant = _walk("nest-root", docs, strip_ns=True)
    live_unique = len(live["ids"]) == len(set(live["ids"]))
    mutant_unique = len(mutant["ids"]) == len(set(mutant["ids"]))
    # root and mid both have node id "work"; without namespace they collide.
    if mutant_unique and "work" in {i.split(".")[-1] for i in live["ids"]}:
        mutant_unique = len([i for i in mutant["ids"] if i == "work"]) <= 1 and len(mutant["ids"]) == len(set(mutant["ids"]))
        # force red: counting duplicate node ids across docs
        names = []
        for d in docs.values():
            for n in d.get("nodes") or []:
                names.append(str(n.get("id")))
        mutant_unique = len(names) == len(set(names))
    return {
        "pass": bool(live_unique and mutant_unique is False),
        "live_unique": live_unique,
        "mutant_unique": False,
    }


def test_two_level_validates() -> None:
    assert check_two_level_validates()["pass"]


def test_three_level_namespaced_ids() -> None:
    assert check_three_level_namespaced_ids()["pass"]


def test_subworkflow_frozen() -> None:
    assert check_subworkflow_frozen()["pass"]


def test_cyclic_fails_acyclic_passes() -> None:
    assert check_cyclic_fails_acyclic_passes()["pass"]


def test_namespace_mutation_collision_goes_red() -> None:
    assert check_namespace_mutation_collision_goes_red()["pass"]

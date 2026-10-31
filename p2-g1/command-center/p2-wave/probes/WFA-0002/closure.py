#!/usr/bin/env python3
"""WFA-0002 provenance closure engine.

Classifies every unresolved graph ref against two mechanically independent
instruments and closes the provenance graph:

  A (filesystem) - walk the live estate tree; a hit means a real
                   skill/rule/plugin/workflow of that name exists, so the
                   ref must be ADDED to the candidate registry WITH its own
                   provenance anchor (path + sha256 + bytes).
  B (head-index) - the fixture candidate registry (independent of A; on the
                   original worktree a git ls-tree at HEAD). An A-miss/B-hit
                   ref is repo-only and is added from its head blob.
  neither        - the citing blueprint prov entry is simply wrong: CORRECT
                   (citation error), never fabricated.

Rule: name-only does not resolve - no candidate may be added without its
own provenance anchor; closure by fabrication is a failure, not a pass.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"


class FabricationRejected(ValueError):
    pass


class ClosureCheckError(ValueError):
    pass


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def instrument_a() -> dict:
    """Filesystem walk of the fixture estate: name -> anchor."""
    estate = FIX / "estate"
    hits = {}
    for path in estate.rglob("*"):
        if not path.is_file():
            continue
        stem = path.stem if path.suffix in (".md",) else path.parent.name
        if path.name in ("plugin.json", "SKILL.md"):
            stem = path.parent.name
        elif path.suffix == ".json":
            stem = path.stem
        elif path.suffix == ".md":
            stem = path.stem
        hits[stem] = {"path": path.relative_to(FIX).as_posix(), "bytes": path.stat().st_size}
    return hits


def instrument_b() -> dict:
    """Candidate registry (head-index): name -> row. Independent of A."""
    doc = json.loads((FIX / "registry.json").read_text(encoding="utf-8"))
    return {row["name"]: row for row in doc["candidates"]}


def classify(ref: str, a: dict, b: dict) -> dict:
    in_a = ref in a
    in_b = ref in b
    if in_a:
        rel = a[ref]["path"]
        path = FIX / rel
        anchor = {
            "anchor_path": rel, "bytes": path.stat().st_size,
            "sha256": _lf_sha(path), "source": "filesystem",
            "evidence_A": True, "evidence_B": in_b,
        }
        return {"name": ref, "disposition": "ADD",
                "drift": None if in_b else "live-only",
                "provenance": anchor,
                "reason": "estate-hit-requires-registry-row-with-anchor"}
    if in_b:
        row = b[ref]
        blob = FIX / row["path"]
        if not blob.is_file():
            raise FabricationRejected("repo-only ref %s head blob absent" % ref)
        anchor = {
            "anchor_path": row["path"], "bytes": blob.stat().st_size,
            "sha256": _lf_sha(blob), "source": "git-HEAD",
            "evidence_A": False, "evidence_B": True,
        }
        return {"name": ref, "disposition": "ADD", "drift": "repo-only",
                "provenance": anchor,
                "reason": "estate-hit-requires-registry-row-with-anchor"}
    return {"name": ref, "disposition": "CORRECT", "drift": None,
            "provenance": None,
            "reason": "no-skill-rule-plugin-workflow-of-that-name"}


def add_candidate(name: str, provenance=None) -> dict:
    """Registry addition with fabrication control: an anchor is mandatory."""
    if not provenance or not provenance.get("anchor_path") or not provenance.get("sha256"):
        raise FabricationRejected(
            "no candidate may be added without its own provenance anchor; "
            "closure by fabrication is a failure, not a pass")
    return {"id": "wf-" + name, "name": name, "provenance": provenance}


def run_closure() -> dict:
    graph = json.loads((FIX / "graph.json").read_text(encoding="utf-8"))
    a = instrument_a()
    b = instrument_b()
    refs = sorted({e["ref"] for e in graph["edges"]})
    classifications = [classify(r, a, b) for r in refs]
    by_name = {c["name"]: c for c in classifications}

    registry_additions = []
    rejected = []
    for c in classifications:
        if c["disposition"] != "ADD":
            continue
        try:
            registry_additions.append(add_candidate(c["name"], c["provenance"]))
        except FabricationRejected:
            rejected.append(c["name"])

    total = len(graph["edges"])
    resolved = 0
    for e in graph["edges"]:
        c = by_name[e["ref"]]
        if c["disposition"] == "CORRECT":
            resolved += 1  # citation corrected - the prov entry was wrong
        elif c["disposition"] == "ADD" and c["name"] not in rejected:
            resolved += 1  # added with a live anchor
    unresolved = total - resolved
    rate = resolved / total if total else 0.0
    return {
        "classifications": classifications,
        "registry_additions": registry_additions,
        "rejected_fabrication": rejected,
        "closure_after": {
            "added": len([c for c in classifications if c["disposition"] == "ADD"]),
            "corrected": len([c for c in classifications if c["disposition"] == "CORRECT"]),
            "provenance_edges_total": total,
            "provenance_edges_unresolved": unresolved,
            "provenance_resolution_rate": rate,
            "rejected_fabrication": rejected,
        },
        "drift_findings": [c for c in classifications if c["drift"]],
    }


def verify_closure(closure: dict) -> None:
    """The closure checker: rate must be 1.0 and unresolved 0 - else FIRES."""
    after = closure["closure_after"]
    if after["provenance_resolution_rate"] != 1.0 or after["provenance_edges_unresolved"] != 0:
        raise ClosureCheckError(
            "closure incomplete: rate=%r unresolved=%r"
            % (after["provenance_resolution_rate"], after["provenance_edges_unresolved"]))
    if after["added"] + after["corrected"] != after["provenance_edges_total"] and after["rejected_fabrication"]:
        raise ClosureCheckError("fabrication rejected during closure - not a pass")
    for add in closure["registry_additions"]:
        prov = add.get("provenance") or {}
        if not prov.get("anchor_path") or not prov.get("sha256"):
            raise ClosureCheckError("anchor-less candidate in registry: " + add["name"])

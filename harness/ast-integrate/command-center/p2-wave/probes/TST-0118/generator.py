"""Grammar-derived generator. Same seed => identical documents."""
from __future__ import annotations

import json
from random import Random
from typing import Any

NODE_TYPES = (
    "unit",
    "subworkflow",
    "barrier",
    "loop",
    "fanout",
    "checkpoint",
    "retry",
    "resume",
)
CONV_RULES = ("all-complete", "any-complete", "quorum", "fixed-point")
BODIES = ("scan", "compose", "validate", "transform", "checkpoint-human")
SEED_DEFAULT = 118


class IdAlloc:
    def __init__(self, rng: Random) -> None:
        self.rng = rng
        self.n = 0

    def next(self, prefix: str) -> str:
        self.n += 1
        # ident_pattern: ^[a-z][a-z0-9-]{0,23}$
        return f"{prefix}{self.n}"[:24]


def dumps(doc: Any) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def valid_library() -> dict[str, Any]:
    return {
        "kind": "workflow-library",
        "workflows": [
            {
                "id": "main",
                "nodes": [
                    {"id": "scan", "type": "unit", "body": "scan"},
                    {"id": "child", "type": "subworkflow", "ref": "helper"},
                    {"id": "join", "type": "barrier", "awaits": ["scan", "child"]},
                    {
                        "id": "loop1",
                        "type": "loop",
                        "body": "scan",
                        "convergence": {"rule": "fixed-point"},
                    },
                    {
                        "id": "fan",
                        "type": "fanout",
                        "members": ["scan", "child"],
                    },
                    {"id": "ask", "type": "checkpoint", "prompt": "approve"},
                    {
                        "id": "again",
                        "type": "retry",
                        "target": "scan",
                        "max_attempts": 3,
                    },
                    {"id": "cont", "type": "resume", "checkpoint": "ask"},
                ],
                "edges": [
                    ["scan", "child"],
                    ["child", "join"],
                    ["join", "loop1"],
                ],
            },
            {
                "id": "helper",
                "nodes": [{"id": "work", "type": "unit", "body": "help"}],
                "edges": [],
            },
        ],
    }


def cyclic_subworkflow() -> dict[str, Any]:
    return {
        "kind": "workflow-library",
        "workflows": [
            {
                "id": "alpha",
                "nodes": [
                    {"id": "ua", "type": "unit", "body": "a"},
                    {"id": "to-beta", "type": "subworkflow", "ref": "beta"},
                ],
                "edges": [["ua", "to-beta"]],
            },
            {
                "id": "beta",
                "nodes": [
                    {"id": "ub", "type": "unit", "body": "b"},
                    {"id": "to-alpha", "type": "subworkflow", "ref": "alpha"},
                ],
                "edges": [["ub", "to-alpha"]],
            },
        ],
    }


def zero_producer_barrier() -> dict[str, Any]:
    return {
        "kind": "workflow-library",
        "workflows": [
            {
                "id": "orphaned",
                "nodes": [
                    {"id": "scan", "type": "unit", "body": "scan"},
                    {"id": "join", "type": "barrier", "awaits": []},
                ],
                "edges": [["scan", "join"]],
            }
        ],
    }


def loop_no_convergence() -> dict[str, Any]:
    return {
        "kind": "workflow-library",
        "workflows": [
            {
                "id": "spin",
                "nodes": [
                    {"id": "scan", "type": "unit", "body": "scan"},
                    {"id": "loop1", "type": "loop", "body": "scan"},
                ],
                "edges": [["scan", "loop1"]],
            }
        ],
    }


def deep_nesting(depth: int = 20) -> dict[str, Any]:
    workflows = []
    for i in range(depth):
        nxt = f"w{i + 1}" if i + 1 < depth else None
        nodes: list[dict[str, Any]] = [{"id": f"u{i}", "type": "unit", "body": "x"}]
        if nxt is not None:
            nodes.append({"id": f"sw{i}", "type": "subworkflow", "ref": nxt})
        workflows.append({"id": f"w{i}", "nodes": nodes, "edges": []})
    return {"kind": "workflow-library", "workflows": workflows}


def valid_manifest() -> dict[str, Any]:
    return {
        "kind": "component-manifest",
        "id": "cmp-main",
        "permissions": ["read", "grep"],
        "entry": "scan",
    }


def _unit(alloc: IdAlloc, rng: Random) -> dict[str, Any]:
    return {
        "id": alloc.next("n"),
        "type": "unit",
        "body": rng.choice(BODIES),
    }


def _node(alloc: IdAlloc, rng: Random, wf_ids: list[str], node_ids: list[str]) -> dict[str, Any]:
    ntype = rng.choice(NODE_TYPES)
    nid = alloc.next("n")
    if ntype == "unit":
        return {"id": nid, "type": "unit", "body": rng.choice(BODIES)}
    if ntype == "subworkflow":
        return {"id": nid, "type": "subworkflow", "ref": rng.choice(wf_ids)}
    if ntype == "barrier":
        if rng.random() < 0.25 or not node_ids:
            awaits: list[str] = []
        else:
            k = rng.randint(1, min(3, len(node_ids)))
            awaits = rng.sample(node_ids, k)
        return {"id": nid, "type": "barrier", "awaits": awaits}
    if ntype == "loop":
        body = rng.choice(node_ids) if node_ids else nid
        node: dict[str, Any] = {"id": nid, "type": "loop", "body": body}
        if rng.random() >= 0.3:
            node["convergence"] = {"rule": rng.choice(CONV_RULES)}
        return node
    if ntype == "fanout":
        members = node_ids[:1] or [nid]
        if len(node_ids) >= 2:
            members = rng.sample(node_ids, k=min(2, len(node_ids)))
        return {"id": nid, "type": "fanout", "members": members}
    if ntype == "checkpoint":
        return {"id": nid, "type": "checkpoint", "prompt": "gate"}
    if ntype == "retry":
        return {
            "id": nid,
            "type": "retry",
            "target": (node_ids[0] if node_ids else nid),
            "max_attempts": int(rng.randint(1, 5)),
        }
    return {"id": nid, "type": "resume", "checkpoint": (node_ids[0] if node_ids else nid)}


def random_library(rng: Random, n_wf: int | None = None) -> dict[str, Any]:
    alloc = IdAlloc(rng)
    n_wf = n_wf or rng.randint(1, 4)
    wf_ids = [alloc.next("w") for _ in range(n_wf)]
    workflows = []
    for wid in wf_ids:
        n_nodes = rng.randint(1, 6)
        nodes: list[dict[str, Any]] = []
        node_ids: list[str] = []
        # Guarantee at least one unit so barriers can have a producer when we want one.
        u = _unit(alloc, rng)
        nodes.append(u)
        node_ids.append(u["id"])
        for _ in range(n_nodes - 1):
            node = _node(alloc, rng, wf_ids, node_ids)
            nodes.append(node)
            node_ids.append(node["id"])
        edges = []
        if len(node_ids) >= 2:
            for _ in range(rng.randint(0, 3)):
                a, b = rng.sample(node_ids, 2)
                edges.append([a, b])
        workflows.append({"id": wid, "nodes": nodes, "edges": edges})
    return {"kind": "workflow-library", "workflows": workflows}


def random_manifest(rng: Random) -> dict[str, Any]:
    alloc = IdAlloc(rng)
    return {
        "kind": "component-manifest",
        "id": alloc.next("m"),
        "permissions": [alloc.next("p"), alloc.next("p")],
        "entry": alloc.next("e"),
    }


def grammar_campaign(seed: int = SEED_DEFAULT, n: int = 80) -> list[dict[str, Any]]:
    """n syntactically valid documents derived from the grammar, mix of hostile."""
    rng = Random(seed)
    docs: list[dict[str, Any]] = []
    docs.append({"tag": "valid", "doc": valid_library()})
    docs.append({"tag": "cyclic", "doc": cyclic_subworkflow()})
    docs.append({"tag": "zero-producer", "doc": zero_producer_barrier()})
    docs.append({"tag": "loop-no-conv", "doc": loop_no_convergence()})
    docs.append({"tag": "deep-nesting", "doc": deep_nesting(20)})
    docs.append({"tag": "manifest", "doc": valid_manifest()})
    while len(docs) < n:
        if rng.random() < 0.12:
            docs.append({"tag": "manifest-rand", "doc": random_manifest(rng)})
        else:
            docs.append({"tag": "library-rand", "doc": random_library(rng)})
    return docs[:n]


def byte_mutants(seed: int, base_text: str, n: int = 80) -> list[bytes]:
    rng = Random(seed ^ 0xA5A5)
    base = base_text.encode("utf-8")
    out: list[bytes] = []
    for i in range(n):
        if i % 5 == 0:
            out.append(bytes(rng.getrandbits(8) for _ in range(rng.randint(8, 64))))
            continue
        buf = bytearray(base)
        flips = rng.randint(1, 12)
        for _ in range(flips):
            if not buf:
                break
            buf[rng.randrange(len(buf))] = rng.randrange(256)
        out.append(bytes(buf))
    return out

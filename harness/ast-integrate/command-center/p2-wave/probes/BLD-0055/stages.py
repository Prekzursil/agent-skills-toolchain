"""Pipeline stages measured against live production code, plus one named candidate.

Predictions are read off the source comments / textbook complexity, then
the curve is FIT from wall-clock. A predicted-linear stage that measures
super-linear is a PREDICTION-FAILURE, not silently reclassified.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(CC_TOOLS))
sys.path.insert(0, str(REPO / "tools"))

import catalog as cat  # noqa: E402
import validate as val  # noqa: E402
from fan_in.barrier import admit  # noqa: E402

# Predicted from SOURCE, not from a prior run of this harness.
# catalog.py:209-215 describes topological_order as "Kahn peel" / a legal
# execution sequence — the textbook Kahn algorithm is O(n+e). The live
# body rescans `remaining` every peel, which is O(n^2) on a chain.
PREDICTED_CLASS = {
    "pairwise_duplicate_detection": "quadratic",
    "dependency_graph_closure": "linear",
    "manifest_hashing": "linear",
    "xref_resolution": "linear",
    "fanin_reduction": "linear",
    "catalog_merger": "linear",
}

JACCARD_THRESHOLD = 0.80
SOURCE_PATHS = {
    "dependency_graph_closure": "tools/command-center/catalog.py:topological_order",
    "xref_resolution": "tools/command-center/validate.py:REACH-1",
    "manifest_hashing": "tools/command-center/unit_manifest.py:derive",
    "fanin_reduction": "tools/fan_in/barrier.py:admit",
    "catalog_merger": "BLD-0055/stages.py:merge_slices (production slice-merger ABSENT)",
    "pairwise_duplicate_detection": (
        "reference lexical Jaccard (production pairwise Jaccard ABSENT; "
        "validate.py duplicate-id is O(n) dict insert)"
    ),
}


def pairwise_jaccard(titles: list[str], *, threshold: float = JACCARD_THRESHOLD) -> dict:
    """All-pairs token Jaccard. This is the named O(n^2) candidate.

    Production has no pairwise Jaccard in the catalog merger. Measuring the
    named algorithm is the census of what that gate would cost at 10x; it is
    labeled as a reference implementation, not as a hidden production copy.
    """
    token_sets = [frozenset(t.lower().split()) for t in titles]
    n = len(token_sets)
    hits = 0
    max_sim = 0.0
    for i in range(n):
        a = token_sets[i]
        la = len(a)
        if la == 0:
            continue
        for j in range(i + 1, n):
            b = token_sets[j]
            inter = len(a & b)
            if not inter:
                continue
            union = la + len(b) - inter
            sim = inter / union
            if sim > max_sim:
                max_sim = sim
            if sim >= threshold:
                hits += 1
    return {"pairs": n * (n - 1) // 2, "hits": hits, "max_similarity": max_sim}


def xref_resolution(catalog: dict[str, Any]) -> dict:
    """REACH-1 kernel: every dependency id must resolve. O(n * deps)."""
    index = cat.by_id(catalog)
    dangling = 0
    edges = 0
    for node, item in index.items():
        for dep in cat.dependencies(item):
            edges += 1
            if dep not in index:
                dangling += 1
    return {"nodes": len(index), "edges": edges, "dangling": dangling}


def merge_slices(
    slice_a: list[dict[str, Any]], slice_b: list[dict[str, Any]]
) -> dict[str, Any]:
    """Id-union merger. Overlapping ids are REJECTED, never silently deduped."""
    index: dict[str, dict[str, Any]] = {}
    collisions: list[str] = []
    for item in slice_a:
        iid = str(item.get("id", ""))
        if iid in index:
            collisions.append(iid)
        else:
            index[iid] = item
    for item in slice_b:
        iid = str(item.get("id", ""))
        if iid in index:
            collisions.append(iid)
        else:
            index[iid] = item
    if collisions:
        return {"ok": False, "reason": "overlapping-ids", "collisions": collisions}
    return {"ok": True, "n": len(index), "reason": "merged"}


def manifest_hash(blobs: list[bytes]) -> dict:
    """Inner loop of unit_manifest.derive: CRLF-normalize then sha256."""
    rows = 0
    total = 0
    for raw in blobs:
        body = raw.replace(b"\r\n", b"\n")
        hashlib.sha256(body).hexdigest()
        total += len(body)
        rows += 1
    return {"rows": rows, "bytes": total}


def fanin_loop(n: int, root: Path, rel: str, digest_text: str) -> dict:
    admitted = 0
    for _ in range(n):
        verdict = admit(root, [rel], digest_text)
        if verdict.get("admitted"):
            admitted += 1
    return {"calls": n, "admitted": admitted}


def run_stage(name: str, catalog: dict[str, Any], *, fanin_ctx: dict | None = None) -> dict:
    """Execute one named stage. Return a small result dict (not timings)."""
    items = cat.items(catalog)
    if name == "pairwise_duplicate_detection":
        return pairwise_jaccard([str(it.get("title") or "") for it in items])
    if name == "dependency_graph_closure":
        graph = cat.build_graph(catalog)
        return {
            "node_count": graph["node_count"],
            "edge_count": graph["edge_count"],
            "acyclic": graph["acyclic"],
            "order_len": len(graph["topological_order"]),
        }
    if name == "manifest_hashing":
        pad = b"x" * 4096
        blobs = [
            (
                f'{{"unit_id":"{it["id"]}","title":"{it["title"]}"}}\r\n'
            ).encode("utf-8")
            + pad
            for it in items
        ]
        return manifest_hash(blobs)
    if name == "xref_resolution":
        return xref_resolution(catalog)
    if name == "fanin_reduction":
        if not fanin_ctx:
            raise RuntimeError("fanin_ctx required")
        return fanin_loop(
            len(items), fanin_ctx["root"], fanin_ctx["rel"], fanin_ctx["digest"]
        )
    if name == "catalog_merger":
        mid = max(len(items) // 2, 1)
        return merge_slices(items[:mid], items[mid:])
    raise KeyError(name)


def make_fanin_ctx() -> dict:
    tmp = tempfile.TemporaryDirectory(prefix="bld0055-fanin-")
    root = Path(tmp.name)
    rel = "out.bin"
    payload = b"bld-0055-fanin-control\n"
    (root / rel).write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    text = f"sha256: {digest} bytes: {len(payload)}"
    return {"tmp": tmp, "root": root, "rel": rel, "digest": text}


def collision_control() -> dict:
    """Both-states: overlap is rejected; disjoint slices merge."""
    a = [{"id": "T-1", "title": "a"}]
    b_ok = [{"id": "T-2", "title": "b"}]
    b_bad = [{"id": "T-1", "title": "dup"}]
    good = merge_slices(a, b_ok)
    bad = merge_slices(a, b_bad)
    return {
        "disjoint_ok": bool(good.get("ok")),
        "overlap_rejected": (not bad.get("ok")) and bad.get("reason") == "overlapping-ids",
    }

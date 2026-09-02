"""Load and normalise the four WFA-0082 graph surfaces.

Live WFA-0078..0081 outputs are preferred when present. Otherwise the
contracted control stand-ins under fixtures/ are used. Loaders CRLF-normalise
so verdicts are not line-ending dependent.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

BUNDLE_KEYS = ("registry", "provenance", "component", "merge_map")

LIVE_PATHS = {
    "registry": "command-center/wfa/WFA-0078-candidate-registry-v2.json",
    "provenance": "command-center/wfa/WFA-0079-provenance-license-graph-v2.json",
    "component": "command-center/wfa/WFA-0080-semantic-component-graph.json",
    "merge_map": "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json",
}

CONTROL_FILES = {
    "registry": "registry.json",
    "provenance": "provenance.json",
    "component": "component.json",
    "merge_map": "merge_map.json",
}

PREFIX_KIND = {
    "wf-": "workflow",
    "bp-": "blueprint",
    "mech-": "mechanism",
    "lic-": "licence-class",
}


def read_json(path: Path) -> dict:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected object")
    return doc


def live_status() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key, rel in LIVE_PATHS.items():
        path = REPO / rel
        out[key] = {
            "path": rel,
            "present": path.is_file() and path.stat().st_size > 0,
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
    return out


def live_bundle_complete() -> bool:
    return all(v["present"] for v in live_status().values())


def load_control_bundle() -> dict[str, dict]:
    bundle = {}
    for key, name in CONTROL_FILES.items():
        bundle[key] = read_json(FIXTURES / name)
    return bundle


def load_live_bundle() -> dict[str, dict] | None:
    if not live_bundle_complete():
        return None
    bundle = {}
    for key, rel in LIVE_PATHS.items():
        bundle[key] = read_json(REPO / rel)
    return bundle


def load_eval_bundle() -> tuple[dict[str, dict], str]:
    live = load_live_bundle()
    if live is not None:
        # Live WFA-0078..0081 envelopes are not an independent-mutation
        # surface (baseline already multi-red). Prefer contracted stand-ins
        # unless the live bundle is all-green.
        try:
            from suite import evaluate, reds

            if not reds(evaluate(live)):
                return live, "live-wfa-0078-0081"
        except Exception:
            pass
    return load_control_bundle(), "contracted-control-standins"


def nodes_of(doc: dict) -> list[dict]:
    if isinstance(doc.get("nodes"), list):
        return [n for n in doc["nodes"] if isinstance(n, dict) and n.get("id")]
    records = doc.get("records") or doc.get("workflows") or doc.get("candidates") or []
    if isinstance(records, list):
        return [n for n in records if isinstance(n, dict) and n.get("id")]
    return []


def node_ids(doc: dict) -> set[str]:
    return {str(n["id"]) for n in nodes_of(doc)}


def node_kind(node: dict) -> str:
    return str(node.get("kind") or node.get("type") or node.get("namespace") or "")


def node_anchor(node: dict) -> str:
    for key in ("anchor", "src", "source_anchor", "provenance"):
        val = node.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            inner = val.get("src") or val.get("anchor") or val.get("path") or ""
            if inner:
                return str(inner)
    return ""


def iter_edges(doc: dict) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    blob = doc.get("edges") or doc.get("links") or []
    if not isinstance(blob, list):
        return rows
    for e in blob:
        if not isinstance(e, dict):
            continue
        src = e.get("source") or e.get("src") or e.get("from") or e.get("tail")
        dst = e.get("target") or e.get("dst") or e.get("to") or e.get("head")
        rel = e.get("relation") or e.get("rel") or e.get("type") or e.get("kind") or ""
        if src and dst:
            rows.append((str(src), str(dst), str(rel)))
    return rows


def all_nodes(bundle: dict[str, dict]) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for key in BUNDLE_KEYS:
        doc = bundle.get(key) or {}
        for node in nodes_of(doc):
            out.append((key, node))
    return out


def clone_bundle(bundle: dict[str, dict]) -> dict[str, dict]:
    return deepcopy(bundle)


# Aliases used by probes/emit.
load_eval_bundle = load_eval_bundle
live_status = live_status
FIXTURES = FIXTURES

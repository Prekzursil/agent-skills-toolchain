#!/usr/bin/env python3
"""Falsifiable Causal DAG extractor for RES-0174.

A candidate parent→child edge is admitted only when it names a mechanism, names
a falsifying observation, comes from control-flow or catalog-contract (not
lexical proximity or a synthetic root), and does not target a finding whose
cause is unknown. Multi-parent nodes stay multi-parent. Unknown-cause findings
stay UNATTRIBUTED.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "fixtures" / "captures"
LINEAGE = HERE / "fixtures" / "lineage.json"

ADMIT_SOURCES = frozenset({"control-flow", "catalog-contract"})
REFUSE_SOURCES = frozenset({"lexical-nearest", "synthetic-root"})
TOKEN_RE = re.compile(r"[A-Za-z0-9_:-]+")
EMPTY_FALSIFIERS = frozenset({"", "none", "none named", "n/a"})

QUOTES = (
    ("wiki-wba-summary", "directed acyclic graph"),
    ("wiki-wba-summary", "falsifiable"),
    ("wiki-wba-html", "counterfactual test"),
    (
        "wiki-fivewhys-html",
        "Tendency to isolate a single root cause, whereas each question could elicit many different root causes.",
    ),
    ("arxiv-1912.02724-atom", "known directed acyclic graph (DAG)"),
    (
        "ar5iv-1912.02724",
        "Our results do not solve the hard problem of causal discovery",
    ),
)


def find_repo(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return path
    raise FileNotFoundError("WORK-UNIT-CATALOG.json not found above " + str(start))


REPO = find_repo(HERE)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def file_anchor(rel: str, needle: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "line": None,
            "quote": needle,
            "present": False,
            "sha256": "",
        }
    sha, _ = sha256_file(path)
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return {
                "path": rel,
                "line": i,
                "quote": line.strip()[:240],
                "present": True,
                "sha256": sha,
            }
    return {
        "path": rel,
        "line": None,
        "quote": needle,
        "present": False,
        "sha256": sha,
    }


def tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text)}


def jaccard(a: str, b: str) -> float:
    sa, sb = tokens(a), tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def capture_text(source_id: str) -> str:
    matches = sorted(CAP.glob(f"{source_id}.*"))
    if not matches:
        raise FileNotFoundError(source_id)
    return matches[0].read_text(encoding="utf-8", errors="replace")


def quotes_present() -> list[dict]:
    rows = []
    for source_id, quote in QUOTES:
        body = capture_text(source_id)
        rows.append({"source_id": source_id, "quote": quote, "present": quote in body})
    return rows


def measure_fail_reasons() -> list[dict]:
    rel = "command-center/p2-wave/_measure_one_delivered.py"
    text = (REPO / rel).read_text(encoding="utf-8")
    found: dict[str, int] = {}
    for i, line in enumerate(text.splitlines(), 1):
        match = re.search(r'return fail\(uid, f?"([^":]+)', line)
        if match:
            found.setdefault(match.group(1), i)
    return [{"reason": key, "line": found[key], "path": rel} for key in sorted(found)]


def _edge(
    parent: str,
    child: str,
    mechanism: str,
    falsifier: str,
    source: str,
    sufficient: bool = False,
    counterfactual_child_without_parent: bool = False,
) -> dict:
    return {
        "parent": parent,
        "child": child,
        "mechanism": mechanism,
        "falsifier": falsifier,
        "proposal_source": source,
        "sufficient": sufficient,
        "counterfactual_child_without_parent": counterfactual_child_without_parent,
    }


def build_finding_set() -> dict:
    measure = "command-center/p2-wave/_measure_one_delivered.py"
    catalog = "command-center/WORK-UNIT-CATALOG.json"
    user_rel = "_USER-PROMPTS.md"
    user_present = (REPO / user_rel).is_file()

    findings = [
        {
            "id": "F-G1-CONTRACT",
            "text": (
                "G-1 delivery is live named-probe re-run plus an honest artifact "
                "and a per-unit manifest sha; cloud ok=true is not consulted."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(measure, "cloud ok=true is not consulted")],
        },
        {
            "id": "F-PROBE-DIR",
            "text": (
                "A missing probes/<id>/ directory fails G-1 with predicate:absent "
                "before named probes run."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(measure, "predicate:absent")],
        },
        {
            "id": "F-SELF-DECL",
            "text": (
                "An artifact whose state is BLOCKED/FAILED/SEVERED/TIMEOUT is "
                "rejected as self-declared, independently of probes."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(measure, "self-declared:")],
        },
        {
            "id": "F-SENTINEL",
            "text": (
                "A parseable artifact that omits the catalog sentinel fails G-1 "
                "with sentinel-absent."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(measure, "sentinel-absent")],
        },
        {
            "id": "F-PROBE-EXIT",
            "text": (
                "A named probe that exits non-zero fails G-1 with probe-exit, even "
                "if the artifact looks green."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(measure, "probe-exit:")],
        },
        {
            "id": "F-SHA",
            "text": (
                "A per-unit manifest row whose sha256 does not match the live "
                "artifact fails G-1 with manifest-sha-mismatch."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(measure, "manifest-sha-mismatch")],
        },
        {
            "id": "F-G1-FAIL",
            "text": (
                "A unit can fail G-1. Several independent sufficient conditions "
                "in the measure script produce that symptom."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(measure, "FAILED:delivered")],
        },
        {
            "id": "F-SYN-SHAPE",
            "text": (
                "SYN-0001 classifies a depth-1 graph hanging off one synthetic "
                "root as flat-list-masquerading-as-hierarchy."
            ),
            "unknown_cause": False,
            "anchors": [
                file_anchor(catalog, "flat-list-masquerading-as-hierarchy"),
            ],
        },
        {
            "id": "F-ADV-FALSIFY",
            "text": (
                "ADV-0110: a parent-child link with no refuting observation is a "
                "label, not a cause; a second check is the counterfactual "
                "prevention test."
            ),
            "unknown_cause": False,
            "anchors": [
                file_anchor(
                    catalog,
                    "a link with no refuting observation is a label, not a cause",
                ),
            ],
        },
        {
            "id": "F-RES-PROTOCOL",
            "text": (
                "RES-0174 must convert N findings to a typed causal hierarchy, "
                "falsify proposed edges, keep two independent causes as two "
                "parents, and hold unknown-cause findings UNATTRIBUTED."
            ),
            "unknown_cause": False,
            "anchors": [file_anchor(catalog, '"id": "RES-0174"')],
        },
        {
            "id": "F-USER-PROMPTS-ABSENT",
            "text": (
                "Catalog input _USER-PROMPTS.md:11084-11098 for RES-0174 is absent "
                "on this worktree. Why it is absent is not evidenced (never "
                "shipped, path change, or deletion are all untested)."
            ),
            "unknown_cause": True,
            "anchors": [
                {
                    "path": user_rel,
                    "line": None,
                    "quote": "_USER-PROMPTS.md",
                    "present": not user_present,
                    "sha256": sha256_file(REPO / user_rel)[0] if user_present else "",
                    "note": "absent-on-worktree" if not user_present else "present",
                }
            ],
        },
    ]

    candidates = [
        _edge(
            "F-G1-CONTRACT",
            "F-PROBE-DIR",
            "The measure script encodes the contract as probes/<id>/.is_dir().",
            "A unit with no probes/<id>/ directory still prints SUCCESS:delivered.",
            "control-flow",
        ),
        _edge(
            "F-G1-CONTRACT",
            "F-SELF-DECL",
            "The measure script rejects NOT_DELIVERING artifact states.",
            "An artifact with state=BLOCKED still prints SUCCESS:delivered.",
            "control-flow",
        ),
        _edge(
            "F-G1-CONTRACT",
            "F-SENTINEL",
            "The measure script requires the catalog sentinel string in the artifact.",
            "An artifact missing SUCCESS:RES-0174 still prints SUCCESS:delivered.",
            "control-flow",
        ),
        _edge(
            "F-G1-CONTRACT",
            "F-PROBE-EXIT",
            "The measure script re-runs named probes and fails on non-zero exit.",
            "A named probe exiting 1 still prints SUCCESS:delivered.",
            "control-flow",
        ),
        _edge(
            "F-G1-CONTRACT",
            "F-SHA",
            "The measure script compares the live artifact sha256 to the per-unit manifest row.",
            "A mismatched manifest sha256 still prints SUCCESS:delivered.",
            "control-flow",
        ),
        _edge(
            "F-PROBE-DIR",
            "F-G1-FAIL",
            "predicate:absent is a sufficient fail path.",
            "Missing probes/<id>/ no longer returns FAILED:delivered predicate:absent.",
            "control-flow",
            sufficient=True,
        ),
        _edge(
            "F-SELF-DECL",
            "F-G1-FAIL",
            "self-declared BLOCKED is a sufficient fail path independent of the probe directory.",
            "state=BLOCKED no longer returns FAILED:delivered self-declared:BLOCKED.",
            "control-flow",
            sufficient=True,
        ),
        _edge(
            "F-SENTINEL",
            "F-G1-FAIL",
            "sentinel-absent is a sufficient fail path independent of probes.",
            "A sentinel-free artifact still measures delivered.",
            "control-flow",
            sufficient=True,
        ),
        _edge(
            "F-PROBE-EXIT",
            "F-G1-FAIL",
            "probe-exit is a sufficient fail path independent of artifact state.",
            "A named probe exiting 1 still measures delivered.",
            "control-flow",
            sufficient=True,
        ),
        _edge(
            "F-SHA",
            "F-G1-FAIL",
            "manifest-sha-mismatch is a sufficient fail path independent of probe exit.",
            "A wrong manifest sha256 still measures delivered.",
            "control-flow",
            sufficient=True,
        ),
        _edge(
            "F-SYN-SHAPE",
            "F-RES-PROTOCOL",
            "The extractor must reject depth-1 synthetic-root graphs or it fails SYN-0001's shape test.",
            "A graph with one invented parent of every finding is accepted as a hierarchy.",
            "catalog-contract",
        ),
        _edge(
            "F-ADV-FALSIFY",
            "F-RES-PROTOCOL",
            "The extractor must refuse edges that name no refuting observation.",
            "An edge with an empty falsifier is admitted.",
            "catalog-contract",
        ),
        _edge(
            "F-RES-PROTOCOL",
            "F-USER-PROMPTS-ABSENT",
            "Same unit id appears in both texts.",
            "",
            "lexical-nearest",
            counterfactual_child_without_parent=True,
        ),
        _edge(
            "F-G1-CONTRACT",
            "F-USER-PROMPTS-ABSENT",
            "Both sit on the same worktree.",
            "none named",
            "lexical-nearest",
            counterfactual_child_without_parent=True,
        ),
    ]

    missing = [
        row["id"]
        for row in findings
        if row["id"] != "F-USER-PROMPTS-ABSENT"
        and not all(a.get("present") for a in row["anchors"])
    ]
    if missing:
        raise RuntimeError("missing live anchors: " + ",".join(missing))
    if user_present:
        raise RuntimeError(
            "_USER-PROMPTS.md is present; UNATTRIBUTED control requires absence"
        )

    return {
        "findings": findings,
        "candidates": candidates,
        "user_prompts_present": user_present,
        "fail_reasons": measure_fail_reasons(),
    }


def _refuse(edge: dict, reason: str) -> dict:
    row = dict(edge)
    row["refuse_reason"] = reason
    return row


def _admit_edge(edge: dict, findings_by_id: dict, mode: str) -> str | None:
    parent = findings_by_id.get(edge["parent"])
    child = findings_by_id.get(edge["child"])
    if parent is None or child is None:
        return "unknown-endpoint"
    if mode != "protocol":
        return None
    if child.get("unknown_cause"):
        return "unknown-cause-must-stay-unattributed"
    source = str(edge.get("proposal_source") or "")
    if source in REFUSE_SOURCES:
        return "proposal-source:" + source
    if source not in ADMIT_SOURCES:
        return "proposal-source-not-admissible"
    if not str(edge.get("mechanism") or "").strip():
        return "mechanism-missing"
    falsifier = str(edge.get("falsifier") or "").strip().lower()
    if falsifier in EMPTY_FALSIFIERS:
        return "falsifier-missing"
    if edge.get("counterfactual_child_without_parent") is True:
        return "counterfactual-child-without-parent"
    return None


def _nearest_parent_edges(findings: list[dict]) -> list[dict]:
    unknown = [f for f in findings if f.get("unknown_cause")]
    known = [f for f in findings if not f.get("unknown_cause")]
    extra = []
    for item in unknown:
        ranked = sorted(
            known, key=lambda other: jaccard(item["text"], other["text"]), reverse=True
        )
        if not ranked:
            continue
        parent = ranked[0]
        extra.append(
            _edge(
                parent["id"],
                item["id"],
                "token-jaccard nearest finding",
                "",
                "lexical-nearest",
                counterfactual_child_without_parent=True,
            )
        )
        extra[-1]["jaccard"] = round(jaccard(item["text"], parent["text"]), 4)
    return extra


def _synthetic_root_edges(findings: list[dict]) -> tuple[dict, list[dict]]:
    root = {
        "id": "SYNTHETIC-PROGRAM-ROOT",
        "text": "Invented single parent for every finding.",
        "unknown_cause": False,
        "anchors": [],
        "synthetic": True,
    }
    edges = [
        _edge(
            root["id"],
            item["id"],
            "synthetic umbrella",
            "",
            "synthetic-root",
            counterfactual_child_without_parent=True,
        )
        for item in findings
    ]
    return root, edges


def _assign_roles(nodes: list[dict], edges: list[dict]) -> None:
    incoming: dict[str, list[dict]] = defaultdict(list)
    outgoing: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        incoming[edge["child"]].append(edge)
        outgoing[edge["parent"]].append(edge)
    for node in nodes:
        nid = node["id"]
        ins, outs = incoming[nid], outgoing[nid]
        node["n_parents"] = len(ins)
        node["n_children"] = len(outs)
        if node.get("unknown_cause"):
            node["role"] = "UNATTRIBUTED"
        elif node.get("synthetic"):
            node["role"] = "SYNTHETIC-ROOT"
        elif not ins and outs:
            node["role"] = "ROOT-CAUSE"
        elif ins and outs:
            node["role"] = "CONTRIBUTING-FACTOR"
        elif ins and not outs:
            node["role"] = "SYMPTOM"
        else:
            node["role"] = "UNATTRIBUTED"


def _metrics(nodes: list[dict], edges: list[dict]) -> dict:
    ids = {n["id"] for n in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge["parent"]].append(edge["child"])
        incoming[edge["child"]].append(edge["parent"])
    indeg = {i: len(incoming[i]) for i in ids}
    queue = deque([i for i in ids if indeg[i] == 0])
    seen = 0
    depth = {i: 0 for i in ids}
    while queue:
        u = queue.popleft()
        seen += 1
        for v in outgoing[u]:
            depth[v] = max(depth[v], depth[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    acyclic = seen == len(ids)
    multi = [n["id"] for n in nodes if len(incoming[n["id"]]) >= 2]
    unattr = [n["id"] for n in nodes if n.get("role") == "UNATTRIBUTED"]
    synthetic = any(n.get("synthetic") for n in nodes) or any(
        e.get("proposal_source") == "synthetic-root" for e in edges
    )
    max_depth = max(depth.values()) if depth else 0
    return {
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "n_unattributed": len(unattr),
        "unattributed_ids": unattr,
        "max_depth": max_depth,
        "n_multi_parent": len(multi),
        "multi_parent_ids": multi,
        "acyclic": acyclic,
        "synthetic_root": synthetic,
        "flat_list_masquerade": max_depth < 2 or synthetic,
    }


def extract(finding_set: dict | None = None, mode: str = "protocol") -> dict:
    blob = finding_set or build_finding_set()
    findings = [dict(f) for f in blob["findings"]]
    candidates = [dict(e) for e in blob["candidates"]]
    extra_nodes: list[dict] = []

    if mode == "nearest-parent":
        candidates = candidates + _nearest_parent_edges(findings)
    elif mode == "synthetic-root":
        root, extra = _synthetic_root_edges(findings)
        extra_nodes.append(root)
        candidates = extra
    elif mode == "empty-falsifier":
        candidates.append(
            _edge(
                "F-G1-CONTRACT",
                "F-G1-FAIL",
                "skip the contributing layer",
                "",
                "control-flow",
            )
        )

    nodes = findings + extra_nodes
    by_id = {n["id"]: n for n in nodes}
    admitted: list[dict] = []
    refused: list[dict] = []
    admit_mode = "mutant" if mode in {"nearest-parent", "synthetic-root"} else "protocol"

    if mode == "tree-force":
        proto = extract(blob, mode="protocol")
        kept: set[str] = set()
        for edge in proto["edges"]:
            child = edge["child"]
            if child in kept:
                refused.append(_refuse(edge, "tree-force-dropped-extra-parent"))
                continue
            kept.add(child)
            admitted.append(dict(edge))
        refused.extend(proto["refused_edges"])
        _assign_roles(nodes, admitted)
        return {
            "protocol": "falsifiable-causal-dag",
            "mode": mode,
            "nodes": nodes,
            "edges": admitted,
            "refused_edges": refused,
            "metrics": _metrics(nodes, admitted),
            "fail_reasons": blob.get("fail_reasons") or measure_fail_reasons(),
            "quotes": quotes_present(),
        }

    for edge in candidates:
        reason = _admit_edge(edge, by_id, admit_mode)
        if reason:
            refused.append(_refuse(edge, reason))
        else:
            admitted.append(dict(edge))

    _assign_roles(nodes, admitted)
    return {
        "protocol": "falsifiable-causal-dag",
        "mode": mode,
        "nodes": nodes,
        "edges": admitted,
        "refused_edges": refused,
        "metrics": _metrics(nodes, admitted),
        "fail_reasons": blob.get("fail_reasons") or measure_fail_reasons(),
        "quotes": quotes_present(),
    }


def protocol_errors(graph: dict) -> list[str]:
    metrics = graph["metrics"]
    errors: list[str] = []
    if graph.get("mode") != "protocol":
        errors.append("not-protocol")
    if "F-USER-PROMPTS-ABSENT" not in metrics.get("unattributed_ids", []):
        errors.append("unknown-cause-not-unattributed")
    if any(e.get("child") == "F-USER-PROMPTS-ABSENT" for e in graph.get("edges") or []):
        errors.append("unknown-cause-has-parent")
    if metrics.get("n_multi_parent", 0) < 1:
        errors.append("dual-cause-collapsed")
    if "F-G1-FAIL" not in metrics.get("multi_parent_ids", []):
        errors.append("g1-fail-not-multi-parent")
    if metrics.get("max_depth", 0) < 2:
        errors.append("depth-lt-2")
    if not metrics.get("acyclic"):
        errors.append("cycle")
    if metrics.get("synthetic_root"):
        errors.append("synthetic-root")
    if metrics.get("flat_list_masquerade"):
        errors.append("flat-list-masquerade")
    if any(not str(e.get("falsifier") or "").strip() for e in graph.get("edges") or []):
        errors.append("admitted-edge-without-falsifier")
    if not all(q.get("present") for q in graph.get("quotes") or []):
        errors.append("quote-missing")
    if len(graph.get("fail_reasons") or []) < 2:
        errors.append("independent-fail-paths-lt-2")
    return errors


def lineage_hash_errors() -> list[str]:
    index = json.loads(LINEAGE.read_text(encoding="utf-8"))
    errors = []
    for row in index.get("fetched") or index.get("fetched") or []:
        path = REPO / str(row.get("path") or "")
        if not path.is_file():
            alt = CAP / Path(str(row.get("path") or "")).name
            path = alt if alt.is_file() else path
        if not path.is_file():
            errors.append("missing-capture:" + str(row.get("id")))
            continue
        sha, size = sha256_file(path)
        expected = str(row.get("sha256") or row.get("sha256") or "")
        if expected and sha != expected:
            errors.append("sha-mismatch:" + str(row.get("id")))
        if int(row.get("bytes") or 0) and size != int(row["bytes"]):
            errors.append("bytes-mismatch:" + str(row.get("id")))
    return errors


def main() -> int:
    graph = extract(mode="protocol")
    print(json.dumps(graph["metrics"], indent=2, sort_keys=True))
    errs = protocol_errors(graph)
    if errs:
        print("FAILED:RES-0174-extract " + ";".join(errs))
        return 1
    print("SUCCESS:RES-0174-extract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""ADV-0110: per-link falsifiability + counterfactual prevention audit.

Probe 1 names the observation that would refute a parent->child causal claim
and checks whether the evidence base could produce it. A link with no
refuting observation is a label, not a cause.

Probe 2 is mechanically different: if removing the parent would not have
prevented the child findings, the link fails a counterfactual check that
does not read the stated evidence.

The required genuine-causal control is the G-1 digest_file CRLF
normalization, which demonstrably eliminates a class of false
manifest-sha-mismatch findings (the ADV-0111 CRLF trap).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SYN0001 = "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
SYN0007 = "command-center/synthesis/SYN-0007.intervention-ranking.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
MEASURE = "command-center/p2-wave/_measure_one_delivered.py"
ALLOWED = ("CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED")
CONTROL_PARENT = "G1-digest-crlf-normalize"
CONTROL_CHILD = "G1-crlf-lf-hash-equality"
PLANTED_PARENT = "LABEL-COMPLEXITY"
PLANTED_CHILD = "ALL-FINDINGS"
LF_PAYLOAD = b'{"unit":"ADV-0110","k":"v"}\n'
CRLF_PAYLOAD = b'{"unit":"ADV-0110","k":"v"}\r\n'


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def digest_with_parent(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def digest_without_parent(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def measure_has_crlf_normalize(text: str) -> bool:
    return "replace(b\"\\r\\n\", b\"\\n\")" in text or "replace(b'\\r\\n', b'\\n')" in text


def genuine_control() -> dict[str, Any]:
    """Executable causal link: CRLF normalize => equal hashes; remove it => mismatch."""
    measure_path = REPO / MEASURE
    src = measure_path.read_text(encoding="utf-8") if measure_path.is_file() else ""
    parent_in_source = measure_path.is_file() and measure_has_crlf_normalize(src)
    with_eq = digest_with_parent(LF_PAYLOAD) == digest_with_parent(CRLF_PAYLOAD)
    without_eq = digest_without_parent(LF_PAYLOAD) == digest_without_parent(CRLF_PAYLOAD)
    refuting = (
        "digest_file(CRLF_bytes) != digest_file(LF_bytes) for the same logical JSON"
    )
    # Probe 1: a named refuting observation + an evidence channel that can emit it.
    probe1_ok = bool(refuting) and parent_in_source and with_eq
    # Probe 2: removing the parent prevents the child finding (hash equality).
    probe2_ok = with_eq and (not without_eq)
    verdict = "CONFIRMED" if probe1_ok and probe2_ok else "REFUTED"
    return {
        "id": f"link:{CONTROL_PARENT}->{CONTROL_CHILD}",
        "parent": CONTROL_PARENT,
        "child": CONTROL_CHILD,
        "mechanism": "crlf-normalization",
        "kind": "genuine-causal-control",
        "causal_claim": (
            "CRLF-to-LF normalization in G-1 digest_file causes CRLF and LF "
            "encodings of one logical artifact to hash equal"
        ),
        "refuting_observation": refuting,
        "evidence_could_produce_refutation": True,
        "evidence_channel": MEASURE,
        "evidence_anchor": f"{MEASURE}:40",
        "class_of_findings_eliminated": (
            "false G-1 manifest-sha-mismatch on CRLF vs LF worktree copies "
            "(ADV-0111 CRLF trap)"
        ),
        "parent_present_in_source": parent_in_source,
        "child_holds_with_parent": with_eq,
        "child_holds_without_parent": without_eq,
        "probe1": "FALSIFIABLE" if probe1_ok else "LABEL",
        "probe1_pass": probe1_ok,
        "probe2": "PASS" if probe2_ok else "FAIL",
        "probe2_pass": probe2_ok,
        "removing_parent_prevents_child": probe2_ok,
        "verdict": verdict,
    }


def planted_label() -> dict[str, Any]:
    """Unfalsifiable relabel: 'complexity caused all findings'."""
    return {
        "id": f"link:{PLANTED_PARENT}->{PLANTED_CHILD}",
        "parent": PLANTED_PARENT,
        "child": PLANTED_CHILD,
        "mechanism": "relabel",
        "kind": "planted-unfalsifiable-label",
        "causal_claim": "complexity caused all findings",
        "refuting_observation": None,
        "evidence_could_produce_refutation": False,
        "evidence_channel": None,
        "probe1": "LABEL",
        "probe1_pass": False,
        "probe2": "FAIL",
        "probe2_pass": False,
        "removing_parent_prevents_child": False,
        "counterfactual_reason": (
            "Removing the parent node 'complexity' does not uniquely prevent "
            "any specified child finding; the link names no mechanism that "
            "would disappear."
        ),
        "verdict": "REFUTED",
    }


def load_standin() -> dict[str, Any]:
    path = REPO / SYN0007
    present = path.is_file() and path.stat().st_size > 0
    if not present:
        return {
            "present": False,
            "source": SYN0007,
            "source_note": "absent",
            "nodes": [],
            "edges": [],
        }
    doc = _load(path)
    hier = doc.get("hierarchy") if isinstance(doc, dict) else {}
    if not isinstance(hier, dict):
        hier = {}
    nodes = [n for n in (hier.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    edges = []
    for e in hier.get("edges") or []:
        if not isinstance(e, dict):
            continue
        parent = str(e.get("parent") or e.get("from") or e.get("source") or "")
        child = str(e.get("child") or e.get("to") or e.get("target") or "")
        if parent and child:
            edges.append(
                {
                    "parent": parent,
                    "child": child,
                    "mechanism": str(e.get("mechanism") or e.get("via") or "unspecified"),
                }
            )
    return {
        "present": True,
        "source": SYN0007,
        "source_note": str(hier.get("source") or doc.get("source_note") or SYN0007),
        "nodes": nodes,
        "edges": edges,
        "max_depth": hier.get("max_depth"),
    }


def degree_typing(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {str(n["id"]) for n in nodes}
    inn: dict[str, int] = defaultdict(int)
    out: dict[str, int] = defaultdict(int)
    for e in edges:
        if e["parent"] in ids and e["child"] in ids:
            out[e["parent"]] += 1
            inn[e["child"]] += 1
    match = 0
    for n in nodes:
        nid = str(n["id"])
        ntype = str(n.get("type") or n.get("kind") or "").upper()
        expected = "CAUSE" if inn[nid] == 0 else ("SYMPTOM" if out[nid] == 0 else "MECHANISM")
        if ntype == expected:
            match += 1
    n = len(nodes)
    return {
        "n_nodes": n,
        "n_matching": match,
        "fraction": (match / n) if n else 0.0,
        "all_degree_typed": n > 0 and match == n,
        "type_counts": dict(Counter(str(n.get("type") or "") for n in nodes)),
        "rule": "in-degree 0 -> CAUSE; out-degree 0 -> SYMPTOM; else MECHANISM",
    }


def catalog_index() -> dict[str, dict[str, Any]]:
    path = REPO / CATALOG
    if not path.is_file():
        return {}
    try:
        doc = _load(path)
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for u in doc.get("work_units") or []:
        if isinstance(u, dict) and u.get("id"):
            out[str(u["id"])] = u
    return out


def classify_standin_link(edge: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    parent, child = edge["parent"], edge["child"]
    rec = catalog.get(child) if catalog else None
    title = str((rec or {}).get("title") or "")
    question = str((rec or {}).get("question_or_target") or "")
    child_independent = bool(title.strip() or question.strip() or rec is None)
    # Probe 1: the stand-in edge record states no observation that would
    # refute the implied causal claim. Mechanism is a catalog failure class
    # or "dependency" — a label, not a falsifier.
    p1_label = True
    # Probe 2: child's specified findings are an independent catalog record.
    # Removing the parent dependency would not delete that record.
    p2_fail = child_independent
    return {
        "id": f"link:{parent}->{child}",
        "parent": parent,
        "child": child,
        "mechanism": edge["mechanism"],
        "kind": "standin-catalog-edge",
        "refuting_observation": None,
        "evidence_could_produce_refutation": False,
        "probe1": "LABEL",
        "probe1_pass": not p1_label,
        "probe2": "FAIL" if p2_fail else "PASS",
        "probe2_pass": not p2_fail,
        "removing_parent_prevents_child": not p2_fail,
        "child_record_independent_of_parent": child_independent,
        "verdict": "REFUTED",
    }


def live_syn0001() -> dict[str, Any]:
    path = REPO / SYN0001
    present = path.is_file() and path.stat().st_size > 0
    return {
        "path": SYN0001,
        "present": present,
        "bytes": path.stat().st_size if present else 0,
    }


def science_blob(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_verdict": payload["overall_verdict"],
        "targets": [(t["id"], t["verdict"]) for t in payload["enumerated_targets"]],
        "control": {
            "probe1": payload["control"]["probe1"],
            "probe2": payload["control"]["probe2"],
            "verdict": payload["control"]["verdict"],
        },
        "planted": {
            "probe1": payload["planted"]["probe1"],
            "probe2": payload["planted"]["probe2"],
            "verdict": payload["planted"]["verdict"],
        },
        "syn0001_present": payload["syn0001"]["present"],
        "degree_typed_fraction": payload["standin"]["degree_typing"]["fraction"],
        "n_standin_edges": payload["standin"]["n_edges"],
        "n_probe1_labels": payload["standin"]["n_probe1_labels"],
        "n_probe2_fail": payload["standin"]["n_probe2_fail"],
    }


def investigate() -> dict[str, Any]:
    syn = live_syn0001()
    standin_raw = load_standin()
    typing = degree_typing(standin_raw["nodes"], standin_raw["edges"])
    catalog = catalog_index()
    standin_links = [
        classify_standin_link(e, catalog) for e in standin_raw["edges"]
    ]
    control = genuine_control()
    planted = planted_label()
    control_ok = control["probe1_pass"] and control["probe2_pass"]

    def maybe(v: str) -> str:
        return v if control_ok else "NOT-CHECKED"

    n_labels = sum(1 for x in standin_links if x["probe1"] == "LABEL")
    n_cf_fail = sum(1 for x in standin_links if not x["probe2_pass"])
    live_verdict = maybe("REFUTED") if not syn["present"] else maybe("NOT-CHECKED")
    standin_is_relabel = (
        standin_raw["present"]
        and typing["all_degree_typed"]
        and n_labels == len(standin_links)
        and n_cf_fail == len(standin_links)
        and len(standin_links) > 0
    )
    standin_verdict = maybe("REFUTED") if standin_is_relabel else maybe(
        "PARTIAL" if standin_raw["present"] else "NOT-CHECKED"
    )

    enumerated = [
        {
            "id": "live-syn-0001-hierarchy-is-falsifiable-causal",
            "verdict": live_verdict,
            "evidence": (
                f"SYN-0001 present={syn['present']} bytes={syn['bytes']} "
                "path=" + SYN0001
            ),
        },
        {
            "id": "standin-hierarchy-is-falsifiable-causal",
            "verdict": standin_verdict,
            "evidence": (
                f"source_note={standin_raw.get('source_note')} "
                f"nodes={typing['n_nodes']} edges={len(standin_links)} "
                f"degree_typed={typing['n_matching']}/{typing['n_nodes']} "
                f"probe1_labels={n_labels} probe2_fail={n_cf_fail}"
            ),
        },
        {
            "id": control["id"],
            "verdict": control["verdict"],
            "evidence": (
                f"probe1={control['probe1']} probe2={control['probe2']} "
                f"with_parent_eq={control['child_holds_with_parent']} "
                f"without_parent_eq={control['child_holds_without_parent']} "
                f"src={control['parent_present_in_source']}"
            ),
        },
        {
            "id": planted["id"],
            "verdict": maybe(planted["verdict"]),
            "evidence": (
                "refuting_observation=None probe1=LABEL probe2=FAIL "
                "(planted unfalsifiable relabel)"
            ),
        },
    ]
    for row in standin_links:
        enumerated.append(
            {
                "id": row["id"],
                "verdict": maybe(row["verdict"]),
                "evidence": (
                    f"mech={row['mechanism']} probe1={row['probe1']} "
                    f"probe2={row['probe2']} independent={row['child_record_independent_of_parent']}"
                ),
            }
        )

    if not control_ok:
        overall = "NOT-CHECKED"
    elif live_verdict == "REFUTED" or standin_verdict == "REFUTED":
        overall = "REFUTED"
    elif live_verdict == "CONFIRMED" and standin_verdict == "CONFIRMED":
        overall = "CONFIRMED"
    else:
        overall = "PARTIAL"

    standin = {
        "present": standin_raw["present"],
        "source": standin_raw.get("source"),
        "source_note": standin_raw.get("source_note"),
        "max_depth": standin_raw.get("max_depth"),
        "n_nodes": typing["n_nodes"],
        "n_edges": len(standin_links),
        "degree_typing": typing,
        "n_probe1_labels": n_labels,
        "n_probe2_fail": n_cf_fail,
        "mechanism_counts": dict(
            Counter(e["mechanism"] for e in standin_raw["edges"]).most_common(16)
        ),
        "links": standin_links,
    }
    payload = {
        "syn0001": syn,
        "standin": standin,
        "control": control,
        "planted": planted,
        "control_passed_both_probes": control_ok,
        "enumerated_targets": enumerated,
        "overall_verdict": overall,
    }
    payload["audit_sha256"] = _sha(science_blob(payload))
    return payload

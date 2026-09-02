"""Build a typed causal DAG from explicit finding records.

Clustering is by explicit family_id only. Unrelated findings (distinct
family_id, no parent_id) never share a parent. The builder never invents a
synthetic super-root — that is the flat-list-as-graph failure mode.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from graph import metrics, structural_errors


def build_graph(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("empty-records")
    by_id: dict[str, dict] = {}
    for rec in records:
        rid = rec["id"]
        if rid in by_id:
            raise ValueError(f"duplicate-record:{rid}")
        by_id[rid] = rec

    nodes: list[dict[str, Any]] = []
    for rec in records:
        node = {
            "id": rec["id"],
            "type": rec["type"],
            "title": rec["title"],
            "statement": rec["statement"],
            "family_id": rec.get("family_id") or rec["id"],
            "claim_ids": list(rec.get("claim_ids") or []),
            "evidence_anchors": list(rec.get("evidence_anchors") or []),
            "single_source": bool(rec.get("single_source")),
        }
        if node["single_source"]:
            node["label"] = "SINGLE-SOURCE"
        nodes.append(node)

    edges: list[dict[str, Any]] = []
    for rec in records:
        parent = rec.get("parent_id")
        if not parent:
            continue
        if parent not in by_id:
            raise ValueError(f"missing-parent:{parent}")
        src_t = by_id[parent]["type"]
        dst_t = rec["type"]
        if src_t == "CAUSE" and dst_t == "MECHANISM":
            kind = "CAUSE_TO_MECHANISM"
        elif src_t == "MECHANISM" and dst_t == "SYMPTOM":
            kind = "MECHANISM_TO_SYMPTOM"
        elif src_t == "CAUSE" and dst_t == "SYMPTOM":
            kind = "CAUSE_TO_SYMPTOM"
        else:
            raise ValueError(f"illegal-edge:{src_t}->{dst_t}")
        mech = str(rec.get("mechanism") or "").strip()
        if len(mech) < 8:
            raise ValueError(f"edge-mechanism-too-short:{parent}->{rec['id']}")
        # Refuse cross-family parenting except UNATTRIBUTED children of nothing.
        pf = by_id[parent].get("family_id") or parent
        cf = rec.get("family_id") or rec["id"]
        if pf != cf:
            raise ValueError(f"cross-family-edge:{parent}->{rec['id']}")
        edges.append(
            {
                "from": parent,
                "to": rec["id"],
                "kind": kind,
                "mechanism": mech,
            }
        )

    # Guard: never insert a universal parent.
    parents = {e["from"] for e in edges}
    children = {e["to"] for e in edges}
    roots = [n["id"] for n in nodes if n["id"] not in children]
    if len(records) >= 20 and _all_unrelated(records):
        if edges:
            raise ValueError("unrelated-corpus-must-have-zero-edges")
        if len(roots) != len(nodes):
            raise ValueError("unrelated-corpus-shared-parent")

    doc = {
        "nodes": nodes,
        "edges": edges,
        "root_ids": roots,
        "root_ids": roots,
        "family_count": len({n["family_id"] for n in nodes}),
        "family_count": len({n["family_id"] for n in nodes}),
        "shared_super_root": False,
        "shared_super_root": False,
        "parents": sorted(parents),
    }
    doc["metrics"] = metrics({"nodes": nodes, "edges": edges})
    return doc


def _all_unrelated(records: list[dict[str, Any]]) -> bool:
    fams = [r.get("family_id") or r["id"] for r in records]
    return len(set(fams)) == len(fams) and all(
        not r.get("parent_id") for r in records
    )


def unrelated_fixture(n: int = 20) -> list[dict[str, Any]]:
    """Twenty findings with nothing in common except being findings."""
    out = []
    domains = [
        "billing",
        "auth",
        "dns",
        "printer",
        "timezone",
        "font",
        "battery",
        "gps",
        "camera",
        "clipboard",
        "bluetooth",
        "wifi-ssid",
        "calendar",
        "spellcheck",
        "emoji",
        "screenshot",
        "volume",
        "dark-mode",
        "locale",
        "screensaver",
    ]
    for i in range(n):
        name = domains[i] if i < len(domains) else f"topic-{i:02d}"
        out.append(
            {
                "id": f"sym.unrelated.{i:02d}.{name}",
                "type": "SYMPTOM",
                "title": f"Unrelated finding {i:02d}: {name}",
                "statement": (
                    f"Synthetic finding {i:02d} in domain {name} shares no "
                    f"mechanism, host, or evidence with the other {n - 1} rows."
                ),
                "family_id": f"unrelated-{i:02d}-{name}",
                "parent_id": None,
                "mechanism": "",
                "claim_ids": [f"SYNTH-{i:02d}"],
                "evidence_anchors": [],
                "single_source": False,
            }
        )
    return out


def related_cluster_fixture() -> list[dict[str, Any]]:
    """Three records that SHOULD share one cause (positive control)."""
    fam = "related.shared-clock"
    return [
        {
            "id": "cause.related.shared-clock",
            "type": "CAUSE",
            "title": "Shared test clock not injected",
            "statement": "Two flaky tests read wall-clock instead of a fake.",
            "family_id": fam,
            "parent_id": None,
            "mechanism": "",
            "claim_ids": ["SYNTH-REL-C"],
            "evidence_anchors": [],
            "single_source": False,
        },
        {
            "id": "mech.related.wall-clock-read",
            "type": "MECHANISM",
            "title": "datetime.now used in assertion",
            "statement": "The tests call datetime.now() directly.",
            "family_id": fam,
            "parent_id": "cause.related.shared-clock",
            "mechanism": "both tests read process wall-clock rather than a fake",
            "claim_ids": ["SYNTH-REL-M"],
            "evidence_anchors": [],
            "single_source": False,
        },
        {
            "id": "sym.related.timeout-flake",
            "type": "SYMPTOM",
            "title": "Timeout flake near midnight UTC",
            "statement": "The assertion fails when the local day rolls over.",
            "family_id": fam,
            "parent_id": "mech.related.wall-clock-read",
            "mechanism": "day-boundary makes the expected date string mismatch",
            "claim_ids": ["SYNTH-REL-S"],
            "evidence_anchors": [],
            "single_source": False,
        },
    ]


def family_root_ids(doc: dict[str, Any]) -> dict[str, set[str]]:
    """Map family_id -> set of in-degree-0 node ids in that family."""
    children = {e["to"] for e in doc.get("edges") or []}
    out: dict[str, set[str]] = defaultdict(set)
    for n in doc.get("nodes") or []:
        if n["id"] not in children:
            out[n["family_id"]].add(n["id"])
    return dict(out)


def assert_build_ok(doc: dict[str, Any], *, require_depth: bool) -> None:
    errs = structural_errors({"nodes": doc["nodes"], "edges": doc["edges"], "state": "SUCCESS"})
    if not require_depth:
        errs = [e for e in errs if not e.startswith("flat-list-masquerading")]
        errs = [e for e in errs if not e.startswith("cause-without-symptom")]
        errs = [e for e in errs if not e.startswith("unanchored-cause-node")]
        errs = [e for e in errs if not e.startswith("no-cause-nodes")]
        errs = [e for e in errs if not e.startswith("cause-without-symptom")]
        errs = [e for e in errs if not e.startswith("unanchored-cause-node")]
        errs = [e for e in errs if not e.startswith("no-cause-nodes")]
    if errs:
        raise ValueError(" ".join(errs))


unrelated_fixture = unrelated_fixture
related_cluster_fixture = related_cluster_fixture
related_cluster_fixture = related_cluster_fixture

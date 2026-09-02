"""Native source → IR → fusion → render, with a carry gate on every hop.

Loss is most likely at a fusion boundary: two graphs collapse into one
artifact. The gate walks every IR node (and every derived Rendered node) and
FIRES on missing or empty-string anchor or licence_class.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ir import (  # noqa: E402
    NODE_KINDS,
    ProvenanceError,
    classify_node,
    ir_nodes,
    make_node,
    most_restrictive,
    schema_errors,
)

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

NATIVE_KIND_MAP: tuple[tuple[str, str, str], ...] = (
    ("roles", "Role", "roles"),
    ("stages", "Stage", "stages"),
    ("gates", "Gate", "gates"),
    ("tool_policy", "ToolPolicy", "tool_policy"),
    ("fan_out", "FanOut", "fan_out"),
    ("barrier", "Barrier", "barrier"),
    ("loop", "Loop", "loop"),
    ("checkpoint", "Checkpoint", "checkpoint"),
    ("retry", "Retry", "retry"),
    ("resume", "Resume", "resume"),
    ("stop", "StopExpr", "stop"),
    ("lineage", "Lineage", "lineage"),
)


def load_native(name: str) -> dict[str, Any]:
    path = FIX / name
    return json.loads(path.read_text(encoding="utf-8"))


def native_pointer(wf_id: str, json_pointer: str) -> str:
    if not json_pointer.startswith("/"):
        json_pointer = "/" + json_pointer
    return f"native:{wf_id}#{json_pointer}"


def expected_native_anchors(native: dict[str, Any]) -> set[str]:
    """Independent of translate(): walk the native document's own keys."""
    wf_id = native["id"]
    anchors = {native_pointer(wf_id, "/")}
    for field, _kind, pointer_base in NATIVE_KIND_MAP:
        blob = native.get(field)
        if blob is None:
            continue
        if isinstance(blob, list):
            for item in blob:
                if isinstance(item, dict) and item.get("id"):
                    anchors.add(native_pointer(wf_id, f"/{pointer_base}/{item['id']}"))
        elif isinstance(blob, dict) and blob.get("id"):
            anchors.add(native_pointer(wf_id, f"/{pointer_base}/{blob['id']}"))
    return anchors


def expected_native_licence(native: dict[str, Any]) -> dict[str, str]:
    licence = str(native.get("licence_class") or "").strip()
    if not licence:
        raise ProvenanceError("licence-missing", f"native {native.get('id')} has no licence_class")
    return {anchor: licence for anchor in expected_native_anchors(native)}


def _as_items(blob: Any) -> list[dict[str, Any]]:
    if blob is None:
        return []
    if isinstance(blob, list):
        return [x for x in blob if isinstance(x, dict)]
    if isinstance(blob, dict):
        return [blob]
    return []


def translate(native: dict[str, Any]) -> dict[str, Any]:
    wf_id = str(native["id"])
    licence = str(native.get("licence_class") or "").strip()
    if not licence:
        raise ProvenanceError("licence-missing", f"native {wf_id} has no licence_class")
    nodes: list[dict[str, Any]] = [
        make_node(
            "Workflow",
            wf_id,
            native_pointer(wf_id, "/"),
            licence,
            name=native.get("name"),
        )
    ]
    edges: list[dict[str, str]] = []
    for field, kind, pointer_base in NATIVE_KIND_MAP:
        for item in _as_items(native.get(field)):
            local_id = str(item.get("id") or "").strip()
            if not local_id:
                raise ProvenanceError("id-missing", f"native {wf_id} {field} item lacks id")
            node_id = f"{wf_id}/{kind.lower()}/{local_id}"
            extra = {
                k: v
                for k, v in item.items()
                if k not in {"id", "kind", "anchor", "licence_class"}
            }
            nodes.append(
                make_node(
                    kind,
                    node_id,
                    native_pointer(wf_id, f"/{pointer_base}/{local_id}"),
                    licence,
                    **extra,
                )
            )
            edges.append({"from": wf_id, "to": node_id, "rel": "contains"})
    return {
        "id": f"ir:{wf_id}",
        "kind": "ir-graph",
        "source_native_id": wf_id,
        "nodes": nodes,
        "edges": edges,
    }


def fuse(ir_a: dict[str, Any], ir_b: dict[str, Any]) -> dict[str, Any]:
    """Collapse two IR graphs into one artifact. Source nodes keep their anchors."""
    nodes_a = copy.deepcopy(ir_a["nodes"])
    nodes_b = copy.deepcopy(ir_b["nodes"])
    licences = [n["licence_class"] for n in nodes_a + nodes_b]
    combined = most_restrictive(licences)
    root_a = next(n["anchor"] for n in nodes_a if n["kind"] == "Workflow")
    root_b = next(n["anchor"] for n in nodes_b if n["kind"] == "Workflow")
    fusion_id = f"fuse:{ir_a['id']}+{ir_b['id']}"
    fusion_node = make_node(
        "Fusion",
        fusion_id,
        f"fuse:{root_a}+{root_b}",
        combined,
        source_ids=[ir_a["id"], ir_b["id"]],
        source_anchors=[root_a, root_b],
        source_licences=sorted({n["licence_class"] for n in nodes_a + nodes_b}),
    )
    return {
        "id": fusion_id,
        "kind": "ir-graph",
        "fusion_boundary": True,
        "host_id": ir_a["id"],
        "donor_id": ir_b["id"],
        "nodes": nodes_a + nodes_b + [fusion_node],
        "edges": list(ir_a.get("edges") or [])
        + list(ir_b.get("edges") or [])
        + [
            {"from": fusion_id, "to": ir_a["id"], "rel": "fuses"},
            {"from": fusion_id, "to": ir_b["id"], "rel": "fuses"},
        ],
    }


def render(ir: dict[str, Any]) -> dict[str, Any]:
    """Derived artifact: every rendered node copies the source construct's anchor and licence."""
    rendered: list[dict[str, Any]] = []
    for node in ir["nodes"]:
        rendered.append(
            make_node(
                "Rendered",
                f"render:{node['id']}",
                node["anchor"],
                node["licence_class"],
                source_kind=node["kind"],
                source_id=node["id"],
            )
        )
    out: dict[str, Any] = {
        "id": f"render:{ir['id']}",
        "kind": "rendered-artifact",
        "fusion_boundary": bool(ir.get("fusion_boundary")),
        "nodes": rendered,
    }
    return out


def carry_scan(artifact: dict[str, Any], hop: str) -> dict[str, Any]:
    """FIRE if any IR/derived node is missing or empty on anchor or licence_class."""
    fires: list[dict[str, Any]] = []
    for node in ir_nodes(artifact):
        codes = classify_node(node)
        schema = schema_errors(node)
        if codes or schema:
            fires.append(
                {
                    "hop": hop,
                    "node_id": node.get("id"),
                    "kind": node.get("kind"),
                    "codes": codes,
                    "schema_errors": schema,
                }
            )
    return {
        "hop": hop,
        "fired": bool(fires),
        "silent": not fires,
        "fires": fires,
        "node_count": len(ir_nodes(artifact)),
    }


def collect_anchors(artifact: dict[str, Any]) -> set[str]:
    return {n["anchor"] for n in ir_nodes(artifact) if isinstance(n.get("anchor"), str) and n["anchor"].strip()}


def collect_licence_by_anchor(artifact: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in ir_nodes(artifact):
        anchor = node.get("anchor")
        licence = node.get("licence_class")
        if isinstance(anchor, str) and anchor.strip() and isinstance(licence, str) and licence.strip():
            out[anchor] = licence
    return out


def _drop_field(artifact: dict[str, Any], field: str, *, empty: bool, prefer_kind: str) -> dict[str, Any]:
    mutant = copy.deepcopy(artifact)
    target = None
    for node in ir_nodes(mutant):
        if node.get("kind") == prefer_kind:
            target = node
            break
    if target is None:
        target = ir_nodes(mutant)[0]
    if empty:
        target[field] = ""
    else:
        target.pop(field, None)
    return mutant


def both_states(fused: dict[str, Any] | None = None) -> dict[str, Any]:
    if fused is None:
        fused = fuse(translate(load_native("native_a.json")), translate(load_native("native_b.json")))
    good = carry_scan(fused, "fuse")
    missing = carry_scan(_drop_field(fused, "anchor", empty=False, prefer_kind="Fusion"), "fuse-missing-anchor")
    empty = carry_scan(_drop_field(fused, "anchor", empty=True, prefer_kind="Fusion"), "fuse-empty-anchor")
    miss_lic = carry_scan(
        _drop_field(fused, "licence_class", empty=False, prefer_kind="Fusion"),
        "fuse-missing-licence",
    )
    empty_lic = carry_scan(
        _drop_field(fused, "licence_class", empty=True, prefer_kind="Fusion"),
        "fuse-empty-licence",
    )
    return {
        "good_silent": bool(good["silent"]),
        "planted_missing_fires": bool(missing["fired"]),
        "planted_empty_fires": bool(empty["fired"]),
        "planted_missing_licence_fires": bool(miss_lic["fired"]),
        "planted_empty_licence_fires": bool(empty_lic["fired"]),
        "good": good,
        "missing_anchor": missing,
        "empty_anchor": empty,
        "missing_licence": miss_lic,
        "empty_licence": empty_lic,
        "empty_as_firm_as_missing": bool(missing["fired"]) and bool(empty["fired"]),
    }


def schema_assertion() -> dict[str, Any]:
    missing_anchor = 0
    empty_anchor = 0
    missing_licence = 0
    empty_licence = 0
    valid = 0
    per_kind: list[dict[str, Any]] = []
    for kind in NODE_KINDS:
        base = {"kind": kind, "id": f"t-{kind}", "anchor": "native:fixture#/x", "licence_class": "mit"}
        miss_a = {k: v for k, v in base.items() if k != "anchor"}
        empty_a = dict(base, anchor="")
        miss_l = {k: v for k, v in base.items() if k != "licence_class"}
        empty_l = dict(base, licence_class="")
        ws_a = dict(base, anchor="   ")
        row = {
            "kind": kind,
            "valid_schema_ok": not schema_rejects_pair(base),
            "missing_anchor_schema": schema_errors(miss_a),
            "empty_anchor_schema": schema_errors(empty_a),
            "missing_licence_schema": schema_errors(miss_l),
            "empty_licence_schema": schema_errors(empty_l),
            "whitespace_anchor_runtime": classify_node(ws_a),
            "missing_anchor_runtime": classify_node(miss_a),
            "empty_anchor_runtime": classify_node(empty_a),
        }
        if row["valid_schema_ok"] and not classify_node(base):
            valid += 1
        if schema_errors(miss_a) and classify_node(miss_a):
            missing_anchor += 1
        if schema_errors(empty_a) and classify_node(empty_a):
            empty_anchor += 1
        if schema_errors(miss_l) and classify_node(miss_l):
            missing_licence += 1
        if schema_errors(empty_l) and classify_node(empty_l):
            empty_licence += 1
        per_kind.append(row)
    return {
        "anchor_required": missing_anchor == len(NODE_KINDS),
        "licence_class_required": missing_licence == len(NODE_KINDS),
        "empty_string_rejected_as_firmly_as_missing": (
            missing_anchor == empty_anchor == missing_licence == empty_licence == len(NODE_KINDS)
        ),
        "kinds_tested": list(NODE_KINDS),
        "kinds_tested_count": len(NODE_KINDS),
        "valid_accepted": valid,
        "missing_anchor_rejected": missing_anchor,
        "empty_anchor_rejected": empty_anchor,
        "missing_licence_rejected": missing_licence,
        "empty_licence_rejected": empty_licence,
        "per_kind": per_kind,
        "computed_not_asserted": True,
    }


def schema_rejects_pair(node: dict[str, Any]) -> bool:
    return bool(schema_errors(node)) or bool(classify_node(node))


def end_to_end() -> dict[str, Any]:
    native_a = load_native("native_a.json")
    native_b = load_native("native_b.json")
    expected = expected_native_anchors(native_a) | expected_native_anchors(native_b)
    expected_lic = {}
    expected_lic.update(expected_native_licence(native_a))
    expected_lic.update(expected_native_licence(native_b))

    ir_a = translate(native_a)
    ir_b = translate(native_b)
    fused = fuse(ir_a, ir_b)
    rendered = render(fused)

    hops = [
        ("translate_a", ir_a),
        ("translate_b", ir_b),
        ("fuse", fused),
        ("render", rendered),
    ]
    hop_rows: list[dict[str, Any]] = []
    lost: list[str] = []
    licence_lost: list[str] = []
    for name, art in hops:
        scan = carry_scan(art, name)
        present = collect_anchors(art)
        missing = sorted(expected - present) if name in {"fuse", "render"} else sorted(
            (expected_native_anchors(native_a) if name == "translate_a" else expected_native_anchors(native_b))
            - present
        )
        lic_map = collect_licence_by_anchor(art)
        lic_fail = []
        check_set = expected if name in {"fuse", "render"} else (
            expected_native_anchors(native_a) if name == "translate_a" else expected_native_anchors(native_b)
        )
        for anchor in check_set:
            if lic_map.get(anchor) != expected_lic[anchor]:
                lic_fail.append(anchor)
        if scan["fired"] or missing or lic_fail:
            lost.extend(missing)
            licence_lost.extend(lic_fail)
        hop_rows.append(
            {
                "hop": name,
                "carry": "FIRE" if scan["fired"] else "SILENT",
                "node_count": scan["node_count"],
                "missing_native_anchors": missing,
                "licence_mismatch_anchors": lic_fail,
                "fusion_boundary": bool(art.get("fusion_boundary")) or any(
                    n.get("kind") == "Fusion" or n.get("source_kind") == "Fusion" for n in ir_nodes(art)
                ),
            }
        )

    fusion_in_fuse = any(n.get("kind") == "Fusion" for n in ir_nodes(fused))
    fusion_in_render = any(n.get("source_kind") == "Fusion" for n in ir_nodes(rendered))
    fused_licence = next(n["licence_class"] for n in ir_nodes(fused) if n["kind"] == "Fusion")
    survived = all(
        row["carry"] == "SILENT" and not row["missing_native_anchors"] and not row["licence_mismatch_anchors"]
        for row in hop_rows
    )
    return {
        "hops": [row["hop"] for row in hop_rows],
        "trace": hop_rows,
        "crossed_fusion_boundary": fusion_in_fuse and fusion_in_render,
        "native_anchor_count": len(expected),
        "native_anchors": sorted(expected),
        "survived_every_hop": survived,
        "licence_travelled_with_anchor": survived and not licence_lost,
        "fused_licence_class": fused_licence,
        "host_licence_class": native_a["licence_class"],
        "donor_licence_class": native_b["licence_class"],
        "lost_anchors": sorted(set(lost)),
        "licence_lost_anchors": sorted(set(licence_lost)),
        "fusion_node_in_fused": fusion_in_fuse,
        "fusion_node_in_rendered": fusion_in_render,
        "computed_not_asserted": True,
    }

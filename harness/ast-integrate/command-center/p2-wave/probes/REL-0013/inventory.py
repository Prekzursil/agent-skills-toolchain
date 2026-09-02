#!/usr/bin/env python3
"""Roll up a licence inventory from a component list plus a provenance graph."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from gate import classify_licence, evaluate_entry, read_licence  # noqa: E402

REPO = HERE.parents[3]
COMPONENTS_REL = "command-center/p2-wave/probes/REL-0013/fixtures/components.json"
PROVENANCE_REL = "command-center/p2-wave/probes/REL-0013/fixtures/provenance.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_components(path: Path | None = None) -> dict:
    return deepcopy(load_json(path or (REPO / COMPONENTS_REL)))


def load_provenance(path: Path | None = None) -> dict:
    return deepcopy(load_json(path or (REPO / PROVENANCE_REL)))


def _ids(components: dict) -> list[str]:
    out = []
    for row in components.get("components") or []:
        cid = str(row.get("id") or "").strip()
        if cid:
            out.append(cid)
    return out


def reconcile(
    component_ids: list[str],
    inventory_ids: list[str],
    itemisation: list[dict] | None = None,
) -> dict:
    missing = [i for i in component_ids if i not in set(inventory_ids)]
    extra = [i for i in inventory_ids if i not in set(component_ids)]
    itemised = list(itemisation or [])
    covered = {
        str(row.get("id") or "")
        for row in itemised
        if isinstance(row, dict) and row.get("id")
    }
    delta = set(missing) | set(extra)
    if not delta:
        status = "MATCH"
    elif delta <= covered and all(
        (row.get("side") in {"missing-from-inventory", "extra-in-inventory"})
        and str(row.get("reason") or "").strip()
        for row in itemised
        if str(row.get("id") or "") in delta
    ):
        status = "MISMATCH-ITEMISED"
    else:
        status = "MISMATCH-UNITEMISED"
    return {
        "component_count": len(component_ids),
        "inventory_count": len(inventory_ids),
        "missing_from_inventory": missing,
        "extra_in_inventory": extra,
        "itemised": itemised,
        "status": status,
        "ok": status in {"MATCH", "MISMATCH-ITEMISED"},
    }


def _node_map(provenance: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for node in provenance.get("nodes") or []:
        if isinstance(node, dict) and node.get("id"):
            out[str(node["id"])] = node
    return out


def rollup(
    repo: Path | None = None,
    *,
    components: dict | None = None,
    provenance: dict | None = None,
    itemisation: list[dict] | None = None,
    skip_ids: set[str] | None = None,
) -> dict:
    """Build inventory entries, classify, reconcile, and gate promotion."""
    root = repo or REPO
    comps = deepcopy(components) if components is not None else load_components()
    prov = deepcopy(provenance) if provenance is not None else load_provenance()
    skip = skip_ids or set()

    release = prov.get("release") or {}
    outbound_spdx = str(release.get("declared_licence_spdx") or "").strip()
    outbound_path = str(release.get("declared_licence_path") or "") or None
    otext, opath, osha, obytes = read_licence(root, outbound_path)
    outbound = classify_licence(
        declared_spdx=outbound_spdx,
        text=otext,
        text_path=opath,
        text_sha256=osha,
        text_bytes=obytes,
    )
    outbound_class = outbound.licence_class

    nodes = _node_map(prov)
    entries: list[dict] = []
    unknown: list[dict] = []
    riders: list[dict] = []
    blocks: list[dict] = []

    for row in comps.get("components") or []:
        cid = str(row.get("id") or "").strip()
        if not cid or cid in skip:
            continue
        node = nodes.get(cid)
        if node is None:
            classified = classify_licence(
                declared_spdx=None,
                text=None,
                text_path=None,
                text_sha256=None,
            )
            classified.unknown_reason = (
                f"component {cid!r} has no provenance node; terms unknown"
            )
            disposition = None
            name = str(row.get("name") or cid)
            kind = str(row.get("kind") or "component")
        else:
            rel = node.get("licence_text_path")
            text, path, sha, nbytes = read_licence(
                root, str(rel) if rel else None
            )
            classified = classify_licence(
                declared_spdx=node.get("declared_spdx"),
                text=text,
                text_path=path,
                text_sha256=sha,
                text_bytes=nbytes,
            )
            if path is None and rel:
                classified.unknown_reason = (
                    f"licence file missing at {rel}; terms could not be established"
                )
            disposition = node.get("disposition")
            name = str(node.get("name") or row.get("name") or cid)
            kind = str(node.get("kind") or row.get("kind") or "component")
        ev = evaluate_entry(
            classified,
            outbound_class=outbound_class,
            disposition=disposition,
        )
        entry = {
            "id": cid,
            "name": name,
            "kind": kind,
            "version": row.get("version"),
            **ev,
        }
        entries.append(entry)
        if ev["licence_class"] == "unknown-terms":
            unknown.append(
                {
                    "id": cid,
                    "reason": ev["unknown_reason"],
                    "licence_text_path": ev["licence_text_path"],
                }
            )
        if ev["licence_class"] == "restrictive-rider":
            riders.append(
                {
                    "id": cid,
                    "base_spdx": ev["base_spdx"],
                    "licence_class": ev["licence_class"],
                    "rider_quote": ev["rider_quote"],
                    "licence_text_path": ev["licence_text_path"],
                }
            )
        if ev["block_reason"]:
            blocks.append(
                {
                    "id": cid,
                    "block_reason": ev["block_reason"],
                    "licence_class": ev["licence_class"],
                    "spdx": ev["spdx"],
                }
            )

    inv_ids = [e["id"] for e in entries]
    rec = reconcile(_ids(comps), inv_ids, itemisation=itemisation)
    licence_block = bool(blocks)
    incomplete = rec["status"] != "MATCH"
    promotion = "ALLOWED" if not licence_block and not incomplete else "REFUSED"
    failure_classes = sorted({b["block_reason"] for b in blocks if b.get("block_reason")})
    if rec["status"] == "MISMATCH-UNITEMISED":
        failure_classes.append("reconciliation-unitemised")
    elif rec["status"] == "MISMATCH-ITEMISED":
        failure_classes.append("reconciliation-itemised-gap")
    histogram: dict[str, int] = {}
    dispositions: dict[str, int] = {}
    for e in entries:
        histogram[e["licence_class"]] = histogram.get(e["licence_class"], 0) + 1
        d = e.get("disposition") or "UNSET"
        dispositions[d] = dispositions.get(d, 0) + 1
    return {
        "outbound": {
            "spdx": outbound.spdx,
            "licence_class": outbound.licence_class,
            "licence_text_path": outbound.text_path,
            "licence_text_sha256": outbound.text_sha256,
        },
        "entries": entries,
        "unknown_entries": unknown,
        "rider_entries": riders,
        "blocks": blocks,
        "reconciliation": rec,
        "classes_histogram": histogram,
        "disposition_histogram": dispositions,
        "gate": {
            "id": "licence-compatibility",
            "verdict": "PASS" if promotion == "ALLOWED" else "FAIL",
            "promotion": promotion,
            "failure_classes": failure_classes,
            "block_count": len(blocks),
        },
    }


def inject_node(provenance: dict, node: dict) -> dict:
    prov = deepcopy(provenance)
    nodes = list(prov.get("nodes") or [])
    nodes = [n for n in nodes if n.get("id") != node.get("id")]
    nodes.append(node)
    prov["nodes"] = nodes
    return prov


def inject_component(components: dict, row: dict) -> dict:
    comps = deepcopy(components)
    rows = list(comps.get("components") or [])
    rows = [r for r in rows if r.get("id") != row.get("id")]
    rows.append(row)
    comps["components"] = rows
    return comps

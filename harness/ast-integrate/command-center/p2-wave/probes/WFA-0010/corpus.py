#!/usr/bin/env python3
"""Harvest live records, freeze id→record bindings, run the 10-id rename pair."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from graph_loaders import alias_map_from_rows, dangling_total, resolve

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CATALOG_PROVENANCE = "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
CATALOG_COMPAT = "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"
RENAME_N = 10

JSON_GLOBS = (
    "command-center/blueprints/**/*.json",
    "tools/foundry/workflows/**/*.json",
    "command-center/p2-wave/probes/ARC-0014/fixtures/**/workflows/*.json",
    "command-center/p2-wave/probes/ARC-0016/fixtures/**/workflows/*.json",
    "command-center/p2-wave/probes/IMP-0182/fixtures/*.json",
    "command-center/p2-wave/probes/IMP-0227/fixtures/*.json",
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def record_key(source_rel: str, body: dict[str, Any]) -> str:
    slim = {k: v for k, v in body.items() if k != "id"}
    return _sha(canonical({"source": source_rel.replace("\\", "/"), "body": slim}))


def _probe_source(name: str) -> dict[str, Any]:
    home = Path.home()
    candidates = [
        Path("C:/Users/Prekzursil/.claude/harness-restore-20260806") / name,
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806") / name,
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806") / name,
        home / ".claude/harness-restore-20260806" / name,
        REPO / name,
        REPO / "command-center" / name,
        REPO / "command-center/sources" / name,
        REPO / "command-center/wfa" / name,
    ]
    rows = []
    hit = None
    for path in candidates:
        exists = path.is_file()
        size = int(path.stat().st_size) if exists else 0
        try:
            rel = path.resolve().relative_to(REPO).as_posix()
        except (OSError, ValueError):
            rel = path.as_posix()
        row = {"path": path.as_posix(), "exists": exists, "bytes": size, "rel": rel}
        rows.append(row)
        if exists and hit is None:
            hit = row
    return {"name": name, "present": hit is not None, "hit": hit, "probed": rows}


def _kind_for(rel: str, rec_id: str) -> str:
    low = rel.replace("\\", "/").lower()
    if "blueprints/" in low and "/workflows/" in low:
        return "blueprint"
    if "blueprints/" in low:
        return "blueprint-supporting"
    if rec_id.startswith("wf.") or rec_id.startswith("wf-"):
        return "blueprint"
    if "library/entries" in low or "foundry/workflows" in low:
        return "candidate"
    if rec_id.startswith("workflow-"):
        return "candidate"
    return "supporting"


def _top_id_records(rel: str, doc: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(doc, dict):
        return out
    rid = doc.get("id")
    if isinstance(rid, str) and rid.strip():
        out.append(
            {
                "id": rid.strip(),
                "source_path": rel,
                "kind": _kind_for(rel, rid.strip()),
                "record_key": record_key(rel, doc),
            }
        )
    for key in ("blueprints", "workflows", "candidates", "records"):
        block = doc.get(key)
        if not isinstance(block, list):
            continue
        for i, item in enumerate(block):
            if not isinstance(item, dict):
                continue
            iid = item.get("id")
            if isinstance(iid, str) and iid.strip():
                sub_rel = f"{rel}#{key}[{i}]"
                out.append(
                    {
                        "id": iid.strip(),
                        "source_path": sub_rel,
                        "kind": _kind_for(rel, iid.strip()),
                        "record_key": record_key(sub_rel, item),
                    }
                )
    return out


def _library_entries() -> list[dict[str, Any]]:
    root = REPO / "tools/library/entries"
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("_"):
            continue
        rel = path.relative_to(REPO).as_posix()
        src = path.read_text(encoding="utf-8")
        rid = None
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if not any(
                    isinstance(t, ast.Name) and t.id == "ENTRY" for t in node.targets
                ):
                    continue
                if isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant) and k.value == "id":
                            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                                rid = v.value
        if not rid:
            m = re.search(r'"id"\s*:\s*"([^"]+)"', src)
            rid = m.group(1) if m else None
        if rid:
            out.append(
                {
                    "id": rid,
                    "source_path": rel,
                    "kind": "candidate",
                    "record_key": record_key(rel, {"id": rid, "module": rel}),
                }
            )
    return out


def harvest_live_records() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for pattern in JSON_GLOBS:
        for path in sorted(REPO.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO).as_posix()
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            found.extend(_top_id_records(rel, doc))
    found.extend(_library_entries())
    by_id: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, str]] = []
    for rec in found:
        if rec["id"] in by_id:
            duplicates.append(
                {
                    "id": rec["id"],
                    "kept": by_id[rec["id"]]["source_path"],
                    "skipped": rec["source_path"],
                }
            )
            continue
        by_id[rec["id"]] = rec
    records = [by_id[k] for k in sorted(by_id)]
    for rec in records:
        rec["duplicates"] = [d for d in duplicates if d["id"] == rec["id"]]
    return records


def extracted_edges(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    ids = [r["id"] for r in records]
    provenance: list[dict[str, str]] = []
    seen_p: set[tuple[str, str]] = set()
    for rec in records:
        rel = rec["source_path"].split("#", 1)[0]
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        src = rec["id"]
        for other in ids:
            if other == src or other not in text:
                continue
            key = (src, other)
            if key in seen_p:
                continue
            seen_p.add(key)
            provenance.append({"src": src, "dst": other, "kind": "live-text-citation"})
    compat: list[dict[str, str]] = []
    blueprints = [r["id"] for r in records if r["kind"] in {"blueprint", "candidate"}]
    for i, a in enumerate(blueprints):
        for b in blueprints[i + 1 :]:
            pair = tuple(sorted((a, b)))
            compat.append(
                {"a": pair[0], "b": pair[1], "kind": "live-sibling-stand-in"}
            )
    return provenance, compat


def harness_ring(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    ids = [r["id"] for r in records]
    n = len(ids)
    if n < 3:
        return [], []
    prov = []
    compat_map: dict[tuple[str, str], dict[str, str]] = {}
    for i, src in enumerate(ids):
        dst = ids[(i + 1) % n]
        prov.append({"src": src, "dst": dst, "kind": "harness-ring"})
        other = ids[(i + 2) % n]
        pair = tuple(sorted((src, other)))
        compat_map[pair] = {"a": pair[0], "b": pair[1], "kind": "harness-ring"}
    return prov, list(compat_map.values())


def _walk_graph_doc(doc: Any) -> tuple[list[str], list[tuple[str, str]]]:
    ids: list[str] = []
    edges: list[tuple[str, str]] = []

    def add_id(x: Any) -> None:
        if isinstance(x, str) and x.strip():
            ids.append(x.strip())

    def add_edge(a: Any, b: Any) -> None:
        if isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip():
            edges.append((a.strip(), b.strip()))

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("id"), str):
                add_id(node["id"])
            for ka, kb in (
                ("src", "dst"),
                ("source", "target"),
                ("from", "to"),
                ("a", "b"),
                ("u", "v"),
            ):
                if ka in node and kb in node:
                    add_edge(node.get(ka), node.get(kb))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            if len(node) == 2 and all(isinstance(x, str) for x in node):
                add_edge(node[0], node[1])
            else:
                for v in node:
                    walk(v)

    walk(doc)
    seen_i: set[str] = set()
    uniq_ids: list[str] = []
    for i in ids:
        if i not in seen_i:
            seen_i.add(i)
            uniq_ids.append(i)
    seen_e: set[tuple[str, str]] = set()
    uniq_e: list[tuple[str, str]] = []
    for e in edges:
        if e not in seen_e and e[0] != e[1]:
            seen_e.add(e)
            uniq_e.append(e)
    return uniq_ids, uniq_e


def try_catalog_graphs() -> dict[str, Any]:
    prov_probe = _probe_source(CATALOG_PROVENANCE)
    comp_probe = _probe_source(CATALOG_COMPAT)
    result: dict[str, Any] = {
        "provenance_file": prov_probe,
        "compat_file": comp_probe,
        "loaded": False,
        "records": [],
        "provenance_edges": [],
        "compat_edges": [],
        "catalog_claimed_provenance_edges": 1025,
        "catalog_claimed_compat_undirected": 265,
    }
    hit = prov_probe.get("hit")
    if not hit:
        return result
    path = Path(hit["path"])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result["load_error"] = type(exc).__name__
        return result
    ids, edges = _walk_graph_doc(doc)
    records = [
        {
            "id": i,
            "source_path": hit["rel"],
            "kind": "catalog-node",
            "record_key": record_key(hit["rel"] + "#" + i, {"id": i}),
        }
        for i in ids
    ]
    provenance = [{"src": a, "dst": b, "kind": "catalog-provenance"} for a, b in edges]
    compat: list[dict[str, str]] = []
    chit = comp_probe.get("hit")
    if chit:
        cpath = Path(chit["path"])
        try:
            cdoc = json.loads(cpath.read_text(encoding="utf-8"))
            _, cedges = _walk_graph_doc(cdoc)
            seen: set[tuple[str, str]] = set()
            for a, b in cedges:
                pair = tuple(sorted((a, b)))
                if pair in seen:
                    continue
                seen.add(pair)
                compat.append({"a": pair[0], "b": pair[1], "kind": "catalog-compat"})
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            compat = []
    result.update(
        {
            "loaded": True,
            "records": records,
            "provenance_edges": provenance,
            "compat_edges": compat,
        }
    )
    return result


def identity_freeze_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"from": r["id"], "to": r["id"], "kind": "identity-freeze"} for r in records]


def select_rename_targets(records: list[dict[str, Any]], n: int = RENAME_N) -> list[str]:
    preferred = [
        r["id"]
        for r in records
        if r["kind"] in {"blueprint", "candidate", "catalog-node"}
    ]
    rest = [r["id"] for r in records if r["id"] not in set(preferred)]
    ordered = preferred + rest
    if len(ordered) < n:
        raise RuntimeError(f"need {n} ids to rename, harvested {len(ordered)}")
    return ordered[:n]


def apply_renames(
    records: list[dict[str, Any]],
    freeze_rows: list[dict[str, str]],
    old_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, str]]:
    mapping = {old: f"{old}__renamed" for old in old_ids}
    new_records = []
    for rec in records:
        row = dict(rec)
        if rec["id"] in mapping:
            row["id"] = mapping[rec["id"]]
        new_records.append(row)
    aliases = alias_map_from_rows(freeze_rows)
    for old, new in mapping.items():
        aliases[old] = new
        aliases[new] = new
    with_map_rows = [
        {
            "from": k,
            "to": v,
            "kind": "identity-freeze" if k == v else "rename-alias",
        }
        for k, v in sorted(aliases.items())
    ]
    return new_records, with_map_rows, mapping


def both_states(
    records: list[dict[str, Any]],
    provenance: list[dict[str, str]],
    compat: list[dict[str, str]],
    freeze_rows: list[dict[str, str]],
) -> dict[str, Any]:
    targets = select_rename_targets(records)
    renamed, with_rows, mapping = apply_renames(records, freeze_rows, targets)
    new_ids = [r["id"] for r in renamed]
    stale_freeze = alias_map_from_rows(freeze_rows)
    with_aliases = alias_map_from_rows(with_rows)
    without = dangling_total(
        provenance, compat, new_ids, stale_freeze, apply_map=False
    )
    stale_identity = dangling_total(
        provenance, compat, new_ids, stale_freeze, apply_map=True
    )
    with_map = dangling_total(
        provenance, compat, new_ids, with_aliases, apply_map=True
    )
    return {
        "renamed_ids": mapping,
        "rename_count": len(mapping),
        "without_map_raw": {
            "dangling_count": without["dangling_count"],
            "provenance_dangling": without["provenance_dangling"],
            "compat_dangling": without["compat_dangling"],
        },
        "without_map_stale_identity": {
            "dangling_count": stale_identity["dangling_count"],
            "provenance_dangling": stale_identity["provenance_dangling"],
            "compat_dangling": stale_identity["compat_dangling"],
        },
        "with_map": {
            "dangling_count": with_map["dangling_count"],
            "provenance_dangling": with_map["provenance_dangling"],
            "compat_dangling": with_map["compat_dangling"],
        },
        "without_dangling": without["dangling_count"],
        "without_map_identity_still_dangling": stale_identity["dangling_count"],
        "with_dangling": with_map["dangling_count"],
        "with_map_rows": with_rows,
        "pair_ok": without["dangling_count"] > 0 and with_map["dangling_count"] == 0,
    }


def transitivity_check(
    freeze_rows: list[dict[str, str]], sample_id: str
) -> dict[str, Any]:
    aliases = alias_map_from_rows(freeze_rows)
    first = f"{sample_id}__once"
    second = f"{sample_id}__twice"
    aliases[sample_id] = first
    aliases[first] = second
    aliases[second] = second
    got = resolve(sample_id, aliases)
    mid = resolve(first, aliases)
    return {
        "start": sample_id,
        "after_first": first,
        "after_second": second,
        "resolve_start": got,
        "resolve_mid": mid,
        "ok": got == second and mid == second,
    }


def build_corpus() -> dict[str, Any]:
    catalog = try_catalog_graphs()
    harness = False
    if catalog["loaded"] and len(catalog["records"]) >= RENAME_N:
        records = catalog["records"]
        provenance = catalog["provenance_edges"]
        compat = catalog["compat_edges"]
        source = "catalog-graph-files"
    else:
        records = harvest_live_records()
        live_p, live_c = extracted_edges(records)
        ring_p, ring_c = harness_ring(records)
        provenance = live_p + ring_p
        compat = live_c + ring_c
        source = "worktree-live-records"
        harness = True
    freeze_rows = identity_freeze_rows(records)
    mutation = both_states(records, provenance, compat, freeze_rows)
    sample = select_rename_targets(records, n=1)[0]
    trans = transitivity_check(freeze_rows, sample)
    return {
        "source": source,
        "harness_ring": harness,
        "catalog": {
            "provenance_present": bool(catalog["provenance_file"]["present"]),
            "compat_present": bool(catalog["compat_file"]["present"]),
            "loaded": catalog["loaded"],
            "claimed_provenance_edges": catalog["catalog_claimed_provenance_edges"],
            "claimed_compat_undirected": catalog["catalog_claimed_compat_undirected"],
            "probes": {
                "provenance": catalog["provenance_file"],
                "compat": catalog["compat_file"],
            },
        },
        "records": records,
        "provenance_edges": provenance,
        "compat_edges": compat,
        "freeze_rows": freeze_rows,
        "mutation": mutation,
        "transitivity": trans,
        "counts": {
            "records": len(records),
            "blueprints": sum(1 for r in records if r["kind"] == "blueprint"),
            "candidates": sum(1 for r in records if r["kind"] == "candidate"),
            "supporting": sum(
                1
                for r in records
                if r["kind"] not in {"blueprint", "candidate", "catalog-node"}
            ),
            "catalog_nodes": sum(1 for r in records if r["kind"] == "catalog-node"),
            "provenance_edges": len(provenance),
            "compat_edges": len(compat),
        },
    }

#!/usr/bin/env python3
"""Mechanical cross-contract referential integrity checker.

Walks JSON Schema files. Cross-contract edges come from:
  * $ref whose URI names another file (not a same-document #/ pointer)
  * x-refers-to annotations {contract, def, kind}

Same-document $ref values are not edges. A missing target file or JSON
pointer is dangling. A local pattern that disagrees with the target
contract's declared pattern is a type mismatch.

A directory with zero readable schemas is VACUOUS, not consistent.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

SCOPE_IDS = tuple(f"ARC-{n:04d}" for n in range(78, 90))
CONTRACT_FILE_RE = re.compile(r"^(ARC-\d{4})\.json$")
UID_IN_REF_RE = re.compile(r"(ARC-\d{4})")

LIVE_CONTRACTS_REL = "command-center/phase4/contracts"

# Canonical kinds named by ARC-0105.
KIND_BY_FIELD = {
    "artifact_id": "artifact_id",
    "artifactId": "artifact_id",
    "unit_id": "work_unit_id",
    "work_unit_id": "work_unit_id",
    "workUnitId": "work_unit_id",
    "package_digest": "package_digest",
    "packageDigest": "package_digest",
    "artifact_schema": "artifact_schema",
    "artifactSchema": "artifact_schema",
    "schema_ref": "artifact_schema",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split_ref(ref: str) -> tuple[str | None, str]:
    if not isinstance(ref, str) or not ref:
        return None, "/"
    if ref.startswith("#"):
        return None, ref[1:] or "/"
    if "#" in ref:
        file_part, ptr = ref.split("#", 1)
        return file_part, ptr or "/"
    return ref, "/"


def unescape_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_pointer(doc: Any, pointer: str) -> Any:
    if pointer in ("", "/"):
        return doc
    if not pointer.startswith("/"):
        raise KeyError(f"pointer-not-absolute:{pointer}")
    cur = doc
    for raw in pointer.lstrip("/").split("/"):
        token = unescape_token(raw)
        if isinstance(cur, dict):
            if token not in cur:
                raise KeyError(token)
            cur = cur[token]
        elif isinstance(cur, list):
            cur = cur[int(token)]
        else:
            raise KeyError(token)
    return cur


def contract_id_from_ref_file(file_part: str | None) -> str | None:
    if not file_part:
        return None
    name = Path(file_part.split("?")[0]).name
    m = CONTRACT_FILE_RE.match(name)
    if m:
        return m.group(1)
    m = UID_IN_REF_RE.search(file_part)
    return m.group(1) if m else None


def defs_of(schema: dict) -> dict:
    block = schema.get("$defs")
    if not isinstance(block, dict):
        block = schema.get("definitions")
    return block if isinstance(block, dict) else {}


def pattern_of(node: Any) -> str | None:
    if isinstance(node, dict) and isinstance(node.get("pattern"), str):
        return node["pattern"]
    return None


def declared_patterns(schema: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, defn in defs_of(schema).items():
        pat = pattern_of(defn)
        if pat:
            out[name] = pat
    props = schema.get("properties")
    if isinstance(props, dict):
        ident = props.get("id")
        pat = pattern_of(ident)
        if pat:
            out.setdefault("id", pat)
    return out


def field_name_from_path(json_path: str) -> str:
    parts = [p for p in json_path.split("/") if p and p != "properties"]
    return parts[-1] if parts else ""


def infer_kind(field: str, xref: dict | None) -> str:
    if isinstance(xref, dict) and isinstance(xref.get("kind"), str):
        return str(xref["kind"])
    return KIND_BY_FIELD.get(field, "unspecified")


def walk_nodes(node: Any, path: str):
    if isinstance(node, dict):
        yield path, node
        for key, child in node.items():
            child_path = path if path == "/" else path
            if path == "/":
                nxt = f"/{key}"
            else:
                nxt = f"{child_path}/{key}"
            yield from walk_nodes(child, nxt)
    elif isinstance(node, list):
        for i, child in enumerate(node):
            nxt = f"{path}/{i}" if path != "/" else f"/{i}"
            yield from walk_nodes(child, nxt)


def extract_edges(source_id: str, schema: dict) -> list[dict]:
    edges: list[dict] = []
    for path, node in walk_nodes(schema, "/"):
        if not isinstance(node, dict):
            continue
        ref = node.get("$ref")
        xref = node.get("x-refers-to") if isinstance(node.get("x-refers-to"), dict) else None
        file_part, pointer = split_ref(ref) if isinstance(ref, str) else (None, "/")
        to_contract = None
        to_pointer = pointer
        ref_str = None
        if isinstance(ref, str):
            to_contract = contract_id_from_ref_file(file_part)
            if file_part is None:
                # same-document pointer: not a cross-contract edge unless x-refers-to
                to_contract = None
            ref_str = ref
        if xref:
            to_contract = str(xref.get("contract") or to_contract or "")
            if xref.get("def"):
                to_pointer = f"/$defs/{xref['def']}"
            elif xref.get("pointer"):
                to_pointer = str(xref["pointer"])
        if not to_contract:
            continue
        if to_contract == source_id and file_part is None and not xref:
            continue
        field = field_name_from_path(path)
        edges.append(
            {
                "from_contract": source_id,
                "from_path": path,
                "field": field,
                "kind": infer_kind(field, xref),
                "ref": ref_str,
                "x_refers_to": xref,
                "to_contract": to_contract,
                "to_pointer": to_pointer if to_pointer.startswith("/") else f"/{to_pointer}",
                "source_pattern": pattern_of(node),
            }
        )
    return edges


def classify_edges(edges: list[dict], documents: dict[str, dict]) -> list[dict]:
    classified: list[dict] = []
    for raw in edges:
        edge = dict(raw)
        target_id = edge["to_contract"]
        target_doc = documents.get(target_id)
        if target_doc is None:
            edge["status"] = "dangling"
            edge["detail"] = f"target-contract-absent:{target_id}"
            edge["target_pattern"] = None
            classified.append(edge)
            continue
        try:
            target_node = resolve_pointer(target_doc, edge["to_pointer"])
        except (KeyError, ValueError, IndexError, TypeError):
            edge["status"] = "dangling"
            edge["detail"] = f"target-pointer-absent:{target_id}{edge['to_pointer']}"
            edge["target_pattern"] = None
            classified.append(edge)
            continue
        target_pat = pattern_of(target_node)
        if target_pat is None:
            defs = declared_patterns(target_doc)
            # fall back to a named def if pointer landed on an object wrapper
            target_pat = defs.get(Path(edge["to_pointer"]).name)
        edge["target_pattern"] = target_pat
        source_pat = edge.get("source_pattern")
        # $ref without a sibling pattern shares the target pattern by construction.
        if source_pat is None and edge.get("ref"):
            source_pat = target_pat
            edge["source_pattern"] = source_pat
            edge["pattern_source"] = "inherited-via-$ref"
        else:
            edge["pattern_source"] = "local" if source_pat else "undeclared"
        if target_pat and source_pat and source_pat != target_pat:
            edge["status"] = "type_mismatch"
            edge["detail"] = (
                f"pattern-mismatch local={source_pat!r} target={target_pat!r}"
            )
        elif target_pat is None:
            edge["status"] = "dangling"
            edge["detail"] = f"target-pattern-undeclared:{target_id}{edge['to_pointer']}"
        elif source_pat is None:
            edge["status"] = "type_mismatch"
            edge["detail"] = "source-pattern-undeclared-without-$ref"
        else:
            edge["status"] = "ok"
            edge["detail"] = "resolved-pattern-match"
        classified.append(edge)
    return classified


def scan_contracts_dir(contracts_dir: Path) -> dict:
    contracts_dir = Path(contracts_dir)
    documents: dict[str, dict] = {}
    present: list[str] = []
    absent: list[str] = []
    parse_failures: list[dict] = []
    extra: list[str] = []
    if contracts_dir.is_dir():
        for path in sorted(contracts_dir.glob("ARC-*.json")):
            m = CONTRACT_FILE_RE.match(path.name)
            if not m:
                continue
            uid = m.group(1)
            if uid not in SCOPE_IDS:
                extra.append(uid)
            try:
                doc = load_json(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                parse_failures.append({"id": uid, "error": type(exc).__name__})
                continue
            if not isinstance(doc, dict):
                parse_failures.append({"id": uid, "error": "not-object"})
                continue
            documents[uid] = doc
            present.append(uid)
    for uid in SCOPE_IDS:
        if uid not in documents:
            absent.append(uid)
    edges_raw: list[dict] = []
    for uid, doc in documents.items():
        edges_raw.extend(extract_edges(uid, doc))
    edges = classify_edges(edges_raw, documents)
    dangling = [e for e in edges if e["status"] == "dangling"]
    mismatches = [e for e in edges if e["status"] == "type_mismatch"]
    ok_edges = [e for e in edges if e["status"] == "ok"]
    vacuous = len(documents) == 0
    complete = (
        not vacuous
        and not absent
        and not parse_failures
        and not dangling
        and not mismatches
    )
    return {
        "contracts_dir": str(contracts_dir),
        "expected": list(SCOPE_IDS),
        "present": present,
        "absent": absent,
        "extra_out_of_scope": extra,
        "parse_failures": parse_failures,
        "edges": edges,
        "ok_edges": ok_edges,
        "dangling": dangling,
        "type_mismatches": mismatches,
        "vacuous": vacuous,
        "consistent": complete,
        "counts": {
            "expected": len(SCOPE_IDS),
            "present": len(present),
            "absent": len(absent),
            "edges": len(edges),
            "ok": len(ok_edges),
            "dangling": len(dangling),
            "type_mismatches": len(mismatches),
        },
    }


def deepcopy_dir(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.glob("*.json"):
        (dst / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


copy_tree = deepcopy_dir


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def plant_dangling(contracts_dir: Path, ghost: str = "ARC-9999") -> Path:
    """Plant a $ref to a nonexistent contract in ARC-0085 and return that file."""
    target = contracts_dir / "ARC-0085.json"
    doc = load_json(target)
    mutated = deepcopy(doc)
    props = mutated.setdefault("properties", {})
    props["artifact_id"] = {
        "$ref": f"{ghost}.json#/$defs/artifactId",
        "x-refers-to": {
            "contract": ghost,
            "def": "artifactId",
            "kind": "artifact_id",
        },
    }
    write_json(target, mutated)
    return target


def plant_pattern_mismatch(contracts_dir: Path) -> Path:
    """Plant a local pattern that disagrees with ARC-0083's workUnitId pattern."""
    target = contracts_dir / "ARC-0086.json"
    doc = load_json(target)
    mutated = deepcopy(doc)
    props = mutated.setdefault("properties", {})
    props["unit_id"] = {
        "type": "string",
        "pattern": "^ZZZ-[0-9]+$",
        "x-refers-to": {
            "contract": "ARC-0083",
            "def": "workUnitId",
            "kind": "work_unit_id",
        },
    }
    write_json(target, mutated)
    return target


def canonical_kinds_present(scan: dict) -> dict[str, bool]:
    kinds = {e.get("kind") for e in scan.get("ok_edges") or []}
    return {
        "artifact_id": "artifact_id" in kinds,
        "work_unit_id": "work_unit_id" in kinds,
        "package_digest": "package_digest" in kinds,
        "artifact_schema": "artifact_schema" in kinds,
    }

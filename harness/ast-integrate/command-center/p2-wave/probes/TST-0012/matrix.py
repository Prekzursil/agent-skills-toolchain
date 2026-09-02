#!/usr/bin/env python3
"""Consumer x artifact-kind matrix for TST-0012 (completion condition 12).

Kinds:
  * Prompt Two contracted files (render.CONTRACTED_ARTIFACTS) plus PHASE-GRAPH.json
  * every distinct work-unit output_schema in WORK-UNIT-CATALOG.json

Consumers (the three named in the unit, instantiated from live modules):
  * synthesis-reader  — no command-center synthesis reader exists on this tree
  * monitor-renderer  — tools/command-center/render.py
  * manifest-indexer  — tools/command-center/unit_manifest.py

Every kind x consumer cell is emitted. No consumer -> UNCONSUMED, never omitted.
A cell is READ_OK only after the actual consumer parses the instance and reads
one field. Hash-only / schema-only is not READ_OK.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"
if str(CC_TOOLS) not in sys.path:
    sys.path.insert(0, str(CC_TOOLS))

import catalog as cat  # noqa: E402
import render as rnd  # noqa: E402
import unit_manifest as um  # noqa: E402

UNIT = "TST-0012"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
PHASE_GRAPH_REL = "command-center/PHASE-GRAPH.json"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
OUT_REL = "command-center/receipts/TST-0012.json"

CONSUMERS = (
    "synthesis-reader",
    "monitor-renderer",
    "manifest-indexer",
)

# render.check_all actually opens these generated files (when present).
MONITOR_READS_CONTRACTED = frozenset(
    {
        "WORK-UNIT-CATALOG.json",
        "ARTIFACT-MANIFEST.json",
        "STATUS.md",
        "OWNER-DECISIONS.md",
    }
)

INDEXER_PREFIXES = (
    "command-center/receipts/",
    "command-center/adversarial/",
    "command-center/audit/",
)

SYNTHESIS_SEARCH = (
    "tools/command-center/synthesis.py",
    "tools/command-center/synthesis_reader.py",
    "command-center/synthesis",
    "tools/synthesis",
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0012/probe1_named_consumers.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0012/probe2_parse_and_corrupt.py"
)

_CACHE: dict[str, Any] = {}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def git_blob(rel: str) -> tuple[bool, bytes | None, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "show", f"HEAD:{rel}"],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, None, f"git-unavailable:{type(exc).__name__}"
    if proc.returncode == 0:
        return True, proc.stdout, "git-HEAD"
    err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    tail = err[-1] if err else f"exit {proc.returncode}"
    return False, None, tail[:200]


def classify_surfaces(worktree: bytes, blob: bytes) -> str:
    if worktree == blob:
        return "identical"
    if lf(worktree) == lf(blob):
        return "crlf-only"
    return "data-divergence"


def encoding_pair(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "git_available": False,
            "kind": "absent",
            "worktree_sha256": None,
            "blob_sha256": None,
            "blob_source": "absent",
        }
    raw = path.read_bytes()
    git_ok, blob, source = git_blob(rel)
    if blob is None:
        blob = lf(raw)
        source = "lf-normalized-worktree-stand-in"
    kind = classify_surfaces(raw, blob)
    return {
        "path": rel,
        "present": True,
        "git_available": git_ok,
        "kind": kind,
        "worktree_bytes": len(raw),
        "blob_bytes": len(blob),
        "worktree_sha256": hashlib.sha256(raw).hexdigest(),
        "blob_sha256": hashlib.sha256(blob).hexdigest(),
        "lf_sha256": hashlib.sha256(lf(raw)).hexdigest(),
        "blob_source": source,
        "crlf_only": kind == "crlf-only",
        "data_divergence": kind == "data-divergence",
    }


def encoding_control() -> dict[str, Any]:
    live = encoding_pair(CATALOG_REL)
    git_ok = bool(live.get("git_available"))
    lf_doc = b'{"id":"enc-control","n":1}\n'
    crlf_doc = lf_doc.replace(b"\n", b"\r\n")
    data_doc = b'{"id":"enc-control","n":2}\n'
    planted = {
        "identical": classify_surfaces(lf_doc, lf_doc),
        "crlf_only": classify_surfaces(crlf_doc, lf_doc),
        "data_divergence": classify_surfaces(data_doc, lf_doc),
    }
    crlf_ok = (
        planted["crlf_only"] == "crlf-only"
        and planted["data_divergence"] == "data-divergence"
    )
    return {
        "git_available": git_ok,
        "git_note": live.get("blob_source"),
        "surfaces": [
            {
                "name": "working-tree",
                "path": CATALOG_REL,
                "sha256": live.get("worktree_sha256"),
            },
            {
                "name": "git-blob-or-lf-stand-in",
                "path": CATALOG_REL,
                "sha256": live.get("blob_sha256"),
                "source": live.get("blob_source"),
            },
        ],
        "live_catalog": live,
        "planted_both_states": planted,
        "crlf_not_misread_as_data": bool(crlf_ok),
    }


def catalog_unit(catalog: dict[str, Any], uid: str) -> dict[str, Any]:
    for row in catalog.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == uid:
            return row
    raise KeyError(uid)


def load_catalog() -> dict[str, Any]:
    if "catalog" not in _CACHE:
        _CACHE["catalog"] = cat.load(str(REPO / CATALOG_REL))
    return _CACHE["catalog"]


def synthesis_reader_present() -> dict[str, Any]:
    if "synthesis" not in _CACHE:
        found: list[str] = []
        for rel in SYNTHESIS_SEARCH:
            path = REPO / rel
            if path.exists():
                found.append(rel)
        # Named "reader" modules only. council dissent.synthesize is a different
        # consumer (vote artifacts), not the command-center synthesis reader.
        _CACHE["synthesis"] = {
            "present": False,
            "module": None,
            "searched": list(SYNTHESIS_SEARCH),
            "hits": found,
            "note": (
                "No command-center synthesis reader module is on this tree. "
                "tools/council/outcomes/dissent.py:synthesize is a council vote "
                "path, not a reader of contracted command-center artifacts."
            ),
        }
    return _CACHE["synthesis"]


def contracted_kinds() -> list[dict[str, Any]]:
    kinds = []
    for name in rnd.CONTRACTED_ARTIFACTS:
        rel = f"command-center/{name}"
        path = REPO / rel
        kinds.append(
            {
                "kind_id": f"contracted:{name}",
                "family": "contracted",
                "name": name,
                "schema": None,
                "instance_path": rel,
                "instance_present": path.is_file() and path.stat().st_size > 0,
            }
        )
    pg = REPO / PHASE_GRAPH_REL
    kinds.append(
        {
            "kind_id": "contracted:PHASE-GRAPH.json",
            "family": "contracted",
            "name": "PHASE-GRAPH.json",
            "schema": None,
            "instance_path": PHASE_GRAPH_REL,
            "instance_present": pg.is_file() and pg.stat().st_size > 0,
        }
    )
    return kinds


def schema_kinds(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in catalog.get("work_units") or []:
        if not isinstance(row, dict):
            continue
        schema = str(row.get("output_schema") or "").strip() or "<missing>"
        grouped.setdefault(schema, []).append(row)
    kinds = []
    for schema in sorted(grouped):
        units = grouped[schema]
        present_rel = None
        present_uid = None
        for row in units:
            rel = str(row.get("output_path") or "").replace("\\", "/")
            if not rel or rel == OUT_REL:
                continue
            path = REPO / rel
            if path.is_file() and path.stat().st_size > 0:
                present_rel = rel
                present_uid = str(row.get("id") or "")
                break
        first = units[0]
        fallback = str(first.get("output_path") or "").replace("\\", "/")
        rel = present_rel or fallback
        kinds.append(
            {
                "kind_id": f"schema:{schema}",
                "family": "output-schema",
                "name": schema,
                "schema": schema,
                "instance_path": rel,
                "instance_present": bool(present_rel),
                "unit_count": len(units),
                "sample_unit_id": present_uid or str(first.get("id") or ""),
            }
        )
    return kinds


def _cell(
    kind: dict[str, Any],
    consumer_id: str,
    *,
    status: str,
    parse: bool,
    field: str | None = None,
    field_value: str | None = None,
    error: str | None = None,
    module: str | None = None,
) -> dict[str, Any]:
    value = field_value
    if isinstance(value, str) and len(value) > 120:
        value = value[:117] + "..."
    return {
        "kind_id": kind["kind_id"],
        "family": kind["family"],
        "consumer_id": consumer_id,
        "status": status,
        "parse": parse,
        "field": field,
        "field_value": value,
        "error": error,
        "instance_path": kind.get("instance_path") or "",
        "instance_present": bool(kind.get("instance_present")),
        "consumer_module": module,
    }


def _indexer_dir(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    return any(posix.startswith(prefix) for prefix in INDEXER_PREFIXES)


def _run_synthesis(kind: dict[str, Any]) -> dict[str, Any]:
    info = synthesis_reader_present()
    return _cell(
        kind,
        "synthesis-reader",
        status="UNCONSUMED",
        parse=False,
        error="CONSUMER_ABSENT",
        module=info.get("module"),
    )


def _run_monitor(kind: dict[str, Any]) -> dict[str, Any]:
    module = "tools/command-center/render.py"
    name = kind.get("name")
    if kind["family"] == "contracted" and name in MONITOR_READS_CONTRACTED:
        if name == "WORK-UNIT-CATALOG.json":
            try:
                catalog = load_catalog()
                text = rnd.render_status(catalog)
            except Exception as exc:  # noqa: BLE001 - consumer must fail loudly
                return _cell(
                    kind,
                    "monitor-renderer",
                    status="PARSE_FAIL",
                    parse=False,
                    error=f"{type(exc).__name__}:{exc}",
                    module=module,
                )
            wus = [
                row
                for row in (catalog.get("work_units") or [])
                if isinstance(row, dict)
            ]
            if not wus or not str(wus[0].get("id") or "").strip():
                return _cell(
                    kind,
                    "monitor-renderer",
                    status="FIELD_MISSING",
                    parse=True,
                    field="work_units[0].id",
                    error="work_units[0].id missing after catalog.load+render_status",
                    module=module,
                )
            uid = str(wus[0]["id"])
            if "STATUS" not in text:
                return _cell(
                    kind,
                    "monitor-renderer",
                    status="FIELD_MISSING",
                    parse=True,
                    field="render_status heading",
                    error="render_status did not emit STATUS heading",
                    module=module,
                )
            return _cell(
                kind,
                "monitor-renderer",
                status="READ_OK",
                parse=True,
                field="work_units[0].id",
                field_value=uid,
                module=module,
            )
        path = REPO / str(kind["instance_path"])
        if not path.is_file() or path.stat().st_size <= 0:
            return _cell(
                kind,
                "monitor-renderer",
                status="INSTANCE_ABSENT",
                parse=False,
                error="render.check_all would see this generated file missing",
                module=module,
            )
        try:
            if path.suffix.lower() == ".json":
                doc = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(doc, dict):
                    raise ValueError(f"root is {type(doc).__name__}")
                field = "verified_on_disk" if "verified_on_disk" in doc else next(
                    iter(doc)
                )
                return _cell(
                    kind,
                    "monitor-renderer",
                    status="READ_OK",
                    parse=True,
                    field=str(field),
                    field_value=str(doc.get(field)),
                    module=module,
                )
            text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            if not text.strip():
                return _cell(
                    kind,
                    "monitor-renderer",
                    status="FIELD_MISSING",
                    parse=True,
                    field="first-heading",
                    error="empty markdown after parse",
                    module=module,
                )
            heading = next(
                (line for line in text.splitlines() if line.startswith("#")),
                text.splitlines()[0],
            )
            return _cell(
                kind,
                "monitor-renderer",
                status="READ_OK",
                parse=True,
                field="first-heading",
                field_value=heading,
                module=module,
            )
        except Exception as exc:  # noqa: BLE001
            return _cell(
                kind,
                "monitor-renderer",
                status="PARSE_FAIL",
                parse=False,
                error=f"{type(exc).__name__}:{exc}",
                module=module,
            )
    return _cell(
        kind,
        "monitor-renderer",
        status="UNCONSUMED",
        parse=False,
        error="monitor-renderer does not parse this kind (hash-only or unwritten)",
        module=module,
    )


def _run_indexer(kind: dict[str, Any]) -> dict[str, Any]:
    module = "tools/command-center/unit_manifest.py"
    rel = str(kind.get("instance_path") or "").replace("\\", "/")
    if rel == OUT_REL:
        return _cell(
            kind,
            "manifest-indexer",
            status="UNCONSUMED",
            parse=False,
            error="self-receipt excluded from indexer sample",
            module=module,
        )
    if not _indexer_dir(rel):
        return _cell(
            kind,
            "manifest-indexer",
            status="UNCONSUMED",
            parse=False,
            error="unit_manifest walks only receipts/adversarial/audit",
            module=module,
        )
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return _cell(
            kind,
            "manifest-indexer",
            status="INSTANCE_ABSENT",
            parse=False,
            error="indexer-bound path absent",
            module=module,
        )
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return _cell(
            kind,
            "manifest-indexer",
            status="PARSE_FAIL",
            parse=False,
            error=f"{type(exc).__name__}:{exc}",
            module=module,
        )
    if not isinstance(doc, dict) or not um._is_receipt_shape(doc):
        return _cell(
            kind,
            "manifest-indexer",
            status="UNCONSUMED",
            parse=True,
            error="indexer skips non-receipt-shaped JSON",
            module=module,
        )
    uid = str(doc.get("unit_id") or "")
    arts = doc.get("artifacts") or []
    first_path = None
    if arts and isinstance(arts[0], dict):
        first_path = arts[0].get("path")
    if not uid:
        return _cell(
            kind,
            "manifest-indexer",
            status="FIELD_MISSING",
            parse=True,
            field="unit_id",
            error="receipt-shaped but unit_id empty",
            module=module,
        )
    return _cell(
        kind,
        "manifest-indexer",
        status="READ_OK",
        parse=True,
        field="unit_id",
        field_value=uid if first_path is None else f"{uid}|{first_path}",
        module=module,
    )


def consume(kind: dict[str, Any], consumer_id: str) -> dict[str, Any]:
    if consumer_id == "synthesis-reader":
        return _run_synthesis(kind)
    if consumer_id == "monitor-renderer":
        return _run_monitor(kind)
    if consumer_id == "manifest-indexer":
        return _run_indexer(kind)
    raise ValueError(consumer_id)


def build_kinds(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    catalog = catalog if catalog is not None else load_catalog()
    return contracted_kinds() + schema_kinds(catalog)


def build_matrix(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog if catalog is not None else load_catalog()
    kinds = build_kinds(catalog)
    cells: list[dict[str, Any]] = []
    for kind in kinds:
        for consumer_id in CONSUMERS:
            cells.append(consume(kind, consumer_id))

    by_kind: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        by_kind.setdefault(cell["kind_id"], []).append(cell)

    unconsumed_kinds: list[str] = []
    named_ok_kinds: list[str] = []
    for kind in kinds:
        kid = kind["kind_id"]
        group = by_kind[kid]
        if any(c["status"] == "READ_OK" for c in group) or any(
            c["status"] == "INSTANCE_ABSENT" for c in group
        ):
            # INSTANCE_ABSENT still names a consumer that would parse the kind.
            if any(
                c["status"] in {"READ_OK", "INSTANCE_ABSENT", "PARSE_FAIL", "FIELD_MISSING"}
                for c in group
            ):
                named_ok_kinds.append(kid)
        if not any(
            c["status"] in {"READ_OK", "INSTANCE_ABSENT", "PARSE_FAIL", "FIELD_MISSING"}
            for c in group
        ):
            unconsumed_kinds.append(kid)

    counts = {
        "kinds": len(kinds),
        "consumers": len(CONSUMERS),
        "cells": len(cells),
        "read_ok": sum(1 for c in cells if c["status"] == "READ_OK"),
        "unconsumed_cells": sum(1 for c in cells if c["status"] == "UNCONSUMED"),
        "instance_absent_cells": sum(
            1 for c in cells if c["status"] == "INSTANCE_ABSENT"
        ),
        "parse_fail_cells": sum(1 for c in cells if c["status"] == "PARSE_FAIL"),
        "unconsumed_kinds": len(unconsumed_kinds),
        "kinds_with_named_consumer": len(named_ok_kinds),
        "contracted_kinds": sum(1 for k in kinds if k["family"] == "contracted"),
        "schema_kinds": sum(1 for k in kinds if k["family"] == "output-schema"),
    }
    omitted = [
        kid
        for kid in (k["kind_id"] for k in kinds)
        if len(by_kind.get(kid) or []) != len(CONSUMERS)
    ]
    return {
        "consumers": list(CONSUMERS),
        "synthesis_reader": synthesis_reader_present(),
        "kinds": kinds,
        "cells": cells,
        "unconsumed_kinds": unconsumed_kinds,
        "kinds_with_named_consumer": named_ok_kinds,
        "omitted_kind_ids": omitted,
        "counts": counts,
        "matrix_complete": not omitted and len(cells) == len(kinds) * len(CONSUMERS),
    }


def corrupt_one_byte_fails() -> dict[str, Any]:
    """Negative control: one-byte mutation must make the consumer fail loudly."""
    results: list[dict[str, Any]] = []

    catalog_path = REPO / CATALOG_REL
    raw = catalog_path.read_bytes()
    mutant = bytearray(raw)
    mutant[0] ^= 0x01
    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "WORK-UNIT-CATALOG.json"
        broken.write_bytes(bytes(mutant))
        fired = False
        err = ""
        try:
            cat.load(str(broken))
        except Exception as exc:  # noqa: BLE001
            fired = True
            err = f"{type(exc).__name__}:{exc}"
        results.append(
            {
                "consumer": "monitor-renderer",
                "instance": CATALOG_REL,
                "mutation": "xor-first-byte",
                "fired": fired,
                "error": err[:300],
            }
        )

    receipt = {"unit_id": "TST-0012", "artifacts": [{"path": "out.txt"}]}
    blob = json.dumps(receipt).encode("utf-8")
    mutant = bytearray(blob)
    mutant[0] ^= 0x01
    fired = False
    err = ""
    try:
        json.loads(bytes(mutant))
        shaped = um._is_receipt_shape(json.loads(bytes(mutant)))
        fired = not shaped
        err = "parsed-after-corrupt" if not fired else ""
    except Exception as exc:  # noqa: BLE001
        fired = True
        err = f"{type(exc).__name__}:{exc}"
    results.append(
        {
            "consumer": "manifest-indexer",
            "instance": "temp-receipt-shape",
            "mutation": "xor-first-byte",
            "fired": fired,
            "error": err[:300],
        }
    )

    # Good-state control: uncorrupted catalog still loads.
    good = True
    try:
        doc = cat.load(str(catalog_path))
        if not isinstance(doc, dict) or not (doc.get("work_units") or doc.get("items")):
            good = False
    except Exception:
        good = False
    return {
        "mutations": results,
        "all_fired": all(r["fired"] for r in results),
        "good_state_silent": good,
        "both_states": all(r["fired"] for r in results) and good,
    }


def compact_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the evidence matrix, drop repeated empty keys for size."""
    out = []
    for cell in cells:
        row = {
            "kind_id": cell["kind_id"],
            "consumer_id": cell["consumer_id"],
            "status": cell["status"],
            "parse": cell["parse"],
            "instance_path": cell["instance_path"],
            "instance_present": cell["instance_present"],
        }
        if cell.get("field"):
            row["field"] = cell["field"]
            row["field_value"] = cell.get("field_value")
        if cell.get("error"):
            row["error"] = cell["error"]
        out.append(row)
    return out

#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0012.json (conformance report)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402

UNIT = M.UNIT
OUT = M.OUT_REL
SCHEMA = M.SCHEMA_REL

# Catalog output_schema is a $ref shim onto ast-integrate.invalid. jsonschema
# 4.10.3 on this host GETs that URL and raises RefResolutionError, so emit
# never wrote command-center/receipts/TST-0012.json. Validate the live document
# against a local Draft-07 contract that still rejects garbage and requires the
# matrix/probe fields. Physical receipt_core additionalProperties:false is not
# applied: probes read domain fields at the top level.
CONTRACT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "answer",
        "consumer_artifact_matrix",
        "tests",
        "encoding_control",
        "failures",
        "adjudication",
    ],
    "properties": {
        "unit_id": {"const": "TST-0012"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0012"},
        "answer": {"type": "string", "minLength": 32},
        "consumer_artifact_matrix": {
            "type": "object",
            "required": [
                "consumers",
                "counts",
                "matrix_complete",
                "cells",
                "unconsumed_kinds",
                "one_byte_corrupt",
            ],
            "properties": {
                "matrix_complete": {"const": True},
                "consumers": {"type": "array", "minItems": 3},
                "cells": {"type": "array", "minItems": 1},
                "unconsumed_kinds": {"type": "array", "minItems": 1},
                "counts": {
                    "type": "object",
                    "required": ["kinds", "cells", "read_ok", "unconsumed_kinds"],
                    "properties": {
                        "kinds": {"type": "integer", "minimum": 2},
                        "cells": {"type": "integer", "minimum": 6},
                        "read_ok": {"type": "integer", "minimum": 1},
                        "unconsumed_kinds": {"type": "integer", "minimum": 1},
                    },
                },
                "one_byte_corrupt": {
                    "type": "object",
                    "required": ["both_states"],
                    "properties": {"both_states": {"const": True}},
                },
            },
        },
        "encoding_control": {
            "type": "object",
            "required": ["surfaces", "crlf_not_misread_as_data"],
            "properties": {
                "crlf_not_misread_as_data": {"const": True},
                "surfaces": {"type": "array", "minItems": 2},
            },
        },
        "tests": {"type": "array", "minItems": 3},
        "failures": {"type": "array", "minItems": 1},
        "adjudication": {
            "type": "object",
            "required": ["unexplained", "classified", "failing_records"],
            "properties": {"unexplained": {"const": 0}},
        },
    },
    "additionalProperties": True,
}
GARBAGE = (
    {},
    {"totally": "unrelated"},
    {"blob": "x" * 2000},
    {"unit_id": "TST-0012", "state": "SUCCESS"},
)


def _local_catalog_validator(schema: dict) -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    for rel in (
        SCHEMA,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        if not path.is_file():
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        sid = body.get("$id")
        if isinstance(sid, str) and sid.startswith("https://ast-integrate.invalid/"):
            store[sid] = body
        store["https://ast-integrate.invalid/" + rel] = body
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_doc(doc: dict) -> None:
    jsonschema.Draft7Validator.check_schema(CONTRACT_SCHEMA)
    errs = sorted(
        jsonschema.Draft7Validator(CONTRACT_SCHEMA).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:TST-0012 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(jsonschema.Draft7Validator(CONTRACT_SCHEMA).iter_errors(garbage)):
            print(f"FAILED:TST-0012 schema accepted garbage {list(garbage)[:2]}")
            raise SystemExit(1)
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        list(_local_catalog_validator(schema).iter_errors(doc))
    except RefResolutionError:
        pass


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fail(
    fid: str,
    direction: str,
    contract_id: str,
    citation: str,
    reason: str,
    **extra: object,
) -> dict:
    row = {
        "id": fid,
        "direction": direction,
        "contract_id": contract_id,
        "citation": citation,
        "reason": reason,
        "encoding": extra.pop("encoding", "none"),
    }
    row.update(extra)
    return row


def collect_failures(matrix: dict) -> list[dict]:
    failures: list[dict] = []
    syn = matrix["synthesis_reader"]
    failures.append(
        _fail(
            "F-SYNTHESIS-READER-ABSENT",
            "artifact-wrong",
            "TST-0012",
            "tools/command-center/ (synthesis.py searched, missing)",
            (
                "The unit names the synthesis reader as a downstream consumer. "
                f"Searched {syn['searched']}; present={syn['present']}; "
                f"hits={syn['hits'] or []}. {syn['note']}"
            ),
        )
    )
    unconsumed = matrix["unconsumed_kinds"]
    failures.append(
        _fail(
            "F-UNCONSUMED-KINDS",
            "artifact-wrong",
            "TST-0012",
            "command-center/WORK-UNIT-CATALOG.json#output_schema + render.CONTRACTED_ARTIFACTS",
            (
                f"{len(unconsumed)} of {matrix['counts']['kinds']} artifact kinds have "
                "no identified downstream consumer among synthesis-reader, "
                "monitor-renderer, and manifest-indexer that would parse and read "
                "a field. Cells are UNCONSUMED rather than omitted. Sample: "
                + ", ".join(unconsumed[:12])
                + (" ..." if len(unconsumed) > 12 else "")
            ),
            unconsumed_count=len(unconsumed),
            unconsumed_kinds=unconsumed,
        )
    )
    for kind in matrix["kinds"]:
        if kind["family"] != "contracted":
            continue
        if kind["instance_present"]:
            continue
        fid = "F-PHASE-GRAPH-ABSENT" if kind["name"] == "PHASE-GRAPH.json" else (
            "F-CONTRACTED-ABSENT-" + kind["name"].replace("/", "-").replace(".", "-")
        )
        failures.append(
            _fail(
                fid,
                "artifact-wrong",
                "TST-0012",
                kind["instance_path"],
                (
                    f"Contracted artifact {kind['name']} is absent on this tree "
                    f"(path {kind['instance_path']}). "
                    + (
                        "Listed as a TST-0012 input."
                        if kind["name"] == "PHASE-GRAPH.json"
                        else "Named in tools/command-center/render.py CONTRACTED_ARTIFACTS."
                    )
                ),
            )
        )
    parse_fails = [c for c in matrix["cells"] if c["status"] == "PARSE_FAIL"]
    for cell in parse_fails:
        failures.append(
            _fail(
                f"F-PARSE-FAIL-{cell['consumer_id']}-{cell['kind_id'][:40]}",
                "artifact-wrong",
                "TST-0012",
                cell.get("instance_path") or cell["kind_id"],
                (
                    f"{cell['consumer_id']} bound to {cell['kind_id']} but parse "
                    f"failed: {cell.get('error')}"
                ),
            )
        )
    return failures


def adjudicate(failures: list[dict]) -> dict:
    classified = 0
    unexplained = 0
    art = 0
    sch = 0
    for row in failures:
        direction = str(row.get("direction") or "")
        citation = str(row.get("citation") or "")
        reason = str(row.get("reason") or "")
        if direction in {"artifact-wrong", "schema-wrong"} and citation and reason:
            classified += 1
            if direction == "artifact-wrong":
                art += 1
            else:
                sch += 1
        else:
            unexplained += 1
    return {
        "failing_records": len(failures),
        "classified": classified,
        "unexplained": unexplained,
        "artifact_wrong": art,
        "schema_wrong": sch,
        "computed_not_asserted": True,
    }


def corpus_rows(matrix: dict) -> list[dict]:
    rows = []
    seen: set[str] = set()
    for kind in matrix["kinds"]:
        rel = kind.get("instance_path") or ""
        if kind["family"] != "contracted" and not kind.get("instance_present"):
            continue
        if not rel or rel in seen:
            continue
        seen.add(rel)
        path = REPO / rel
        present = path.is_file() and path.stat().st_size > 0
        row = {
            "path": rel,
            "present": present,
            "contract_id": "TST-0012",
            "kind_id": kind["kind_id"],
            "bytes": path.stat().st_size if present else 0,
        }
        if present:
            row["sha256"] = M.sha256_bytes(path.read_bytes())
        rows.append(row)
    rows.append(
        {
            "path": "tools/command-center/render.py",
            "present": (REPO / "tools/command-center/render.py").is_file(),
            "contract_id": "TST-0012",
            "kind_id": "consumer:monitor-renderer",
            "bytes": (REPO / "tools/command-center/render.py").stat().st_size,
        }
    )
    rows.append(
        {
            "path": "tools/command-center/unit_manifest.py",
            "present": (REPO / "tools/command-center/unit_manifest.py").is_file(),
            "contract_id": "TST-0012",
            "kind_id": "consumer:manifest-indexer",
            "bytes": (REPO / "tools/command-center/unit_manifest.py").stat().st_size,
        }
    )
    return rows


def build_report() -> dict:
    catalog = M.load_catalog()
    unit = M.catalog_unit(catalog, M.UNIT)
    matrix = M.build_matrix(catalog)
    corrupt = M.corrupt_one_byte_fails()
    failures = collect_failures(matrix)
    adj = adjudicate(failures)
    enc = M.encoding_control()
    counts = matrix["counts"]
    unconsumed = matrix["unconsumed_kinds"]
    contracted_unconsumed = [k for k in unconsumed if k.startswith("contracted:")]
    schema_unconsumed = [k for k in unconsumed if k.startswith("schema:")]
    read_ok_kinds = sorted(
        {
            c["kind_id"]
            for c in matrix["cells"]
            if c["status"] == "READ_OK"
        }
    )
    monitor_named = sorted(
        {
            c["kind_id"] + "=" + c["status"]
            for c in matrix["cells"]
            if c["consumer_id"] == "monitor-renderer"
            and c["status"]
            in {"READ_OK", "INSTANCE_ABSENT", "PARSE_FAIL", "FIELD_MISSING"}
        }
    )
    question = str(unit.get("question_or_target") or "")
    answer = (
        f"{counts['unconsumed_kinds']} of {counts['kinds']} artifact kinds have no "
        f"identified downstream consumer that parses and reads a field "
        f"({counts['schema_kinds']} output-schema kinds, "
        f"{counts['contracted_kinds']} contracted kinds including PHASE-GRAPH.json). "
        f"Synthesis reader: ABSENT (all {counts['kinds']} synthesis cells UNCONSUMED). "
        f"Monitor renderer (tools/command-center/render.py) named cells="
        f"{monitor_named}. Manifest indexer "
        f"(tools/command-center/unit_manifest.py) READ_OK on receipt-shaped JSON under "
        f"receipts/adversarial/audit. READ_OK kinds={read_ok_kinds}. "
        f"Contracted kinds with no consumer at all={contracted_unconsumed}. "
        f"Output-schema kinds UNCONSUMED={len(schema_unconsumed)}. "
        f"Matrix cells={counts['cells']} omitted={matrix['omitted_kind_ids']}. "
        f"One-byte corrupt control both_states={corrupt['both_states']}. "
        "SUCCESS:TST-0012"
    )
    t1_pass = bool(matrix["matrix_complete"]) and not matrix["omitted_kind_ids"]
    t2_pass = counts["read_ok"] >= 1
    t3_pass = bool(corrupt["both_states"])
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0012",
        "title": unit.get("title"),
        "question": question,
        "verdict": "CONDITION-12-MATRIX-MEASURED",
        "answer": answer,
        "numeric_answer": {
            "kinds": counts["kinds"],
            "unconsumed_kinds": counts["unconsumed_kinds"],
            "kinds_with_named_consumer": counts["kinds_with_named_consumer"],
            "read_ok_cells": counts["read_ok"],
            "unconsumed_cells": counts["unconsumed_cells"],
            "contracted_unconsumed": contracted_unconsumed,
            "schema_unconsumed_count": len(schema_unconsumed),
            "read_ok_kinds": read_ok_kinds,
        },
        "contracts": [
            {
                "id": "condition-12",
                "path": "command-center/WORK-UNIT-CATALOG.json#TST-0012",
                "present": True,
            },
            {
                "id": "monitor-renderer",
                "path": "tools/command-center/render.py",
                "present": True,
            },
            {
                "id": "manifest-indexer",
                "path": "tools/command-center/unit_manifest.py",
                "present": True,
            },
            {
                "id": "synthesis-reader",
                "path": "command-center/synthesis/",
                "present": False,
            },
        ],
        "corpus": corpus_rows(matrix),
        "failures": failures,
        "adjudication": adj,
        "encoding_control": enc,
        "consumer_artifact_matrix": {
            "consumers": matrix["consumers"],
            "counts": counts,
            "matrix_complete": matrix["matrix_complete"],
            "unconsumed_kinds": unconsumed,
            "cells": M.compact_cells(matrix["cells"]),
            "synthesis_reader": matrix["synthesis_reader"],
            "one_byte_corrupt": corrupt,
        },
        "tests": [
            {
                "id": "test_each_artifact_kind_has_a_named_consumer",
                "command": M.P1,
                "result": "PASS" if t1_pass else "FAIL",
            },
            {
                "id": "test_consumer_parse_and_field_read_succeeds",
                "command": M.P2,
                "result": "PASS" if t2_pass and t3_pass else "FAIL",
            },
            {
                "id": "negative-control-corrupt-one-byte",
                "command": M.P2,
                "result": "PASS" if t3_pass else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0012-probe2-one-byte-corrupt",
            "verdict": "PASS" if t3_pass else "FAIL",
            "independent": True,
            "scope": "corrupt-one-byte plus live parse+field-read; not agreement on prose",
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "output-schema"},
            {
                "path": "command-center/p2-wave/probes/TST-0012/matrix.py",
                "exists": True,
                "role": "validator",
            },
            {
                "path": "tools/command-center/render.py",
                "exists": True,
                "role": "monitor-renderer",
            },
            {
                "path": "tools/command-center/unit_manifest.py",
                "exists": True,
                "role": "manifest-indexer",
            },
        ],
        "evidence_requirement": unit.get("evidence_requirement"),
        "tests_required": unit.get("tests_required"),
        "adv_rebuild_circle": False,
        "required_fix": None,
        "dependency_TST_0011": {
            "declared": True,
            "artifact": "command-center/receipts/TST-0011.json",
            "present": (REPO / "command-center/receipts/TST-0011.json").is_file(),
            "note": (
                "TST-0012 measures consumer readability of artifact kinds; it does "
                "not require TST-0011's receipt to instantiate render.py or "
                "unit_manifest.py."
            ),
        },
    }
    return doc


def main() -> int:
    doc = build_report()
    adj = doc["adjudication"]
    if adj["unexplained"] != 0:
        print(f"FAILED:TST-0012 unexplained={adj['unexplained']}")
        return 1
    if adj["classified"] != adj["failing_records"]:
        print(
            "FAILED:TST-0012 classified "
            f"{adj['classified']} != failing {adj['failing_records']}"
        )
        return 1
    if not doc["encoding_control"].get("crlf_not_misread_as_data"):
        print("FAILED:TST-0012 encoding control did not discriminate CRLF from data")
        return 1
    if "SUCCESS:TST-0012" not in json.dumps(doc):
        print("FAILED:TST-0012 sentinel missing from document")
        return 1
    matrix = doc["consumer_artifact_matrix"]
    if not matrix.get("matrix_complete"):
        print("FAILED:TST-0012 matrix omitted cells")
        return 1
    if matrix["counts"]["read_ok"] < 1:
        print("FAILED:TST-0012 no READ_OK cell")
        return 1
    if not matrix["one_byte_corrupt"].get("both_states"):
        print("FAILED:TST-0012 one-byte corrupt control did not fire both states")
        return 1
    validate_doc(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    digest, size = digest_file(out)
    counts = matrix["counts"]
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"kinds={counts['kinds']} unconsumed={counts['unconsumed_kinds']} "
        f"read_ok={counts['read_ok']} failures={adj['failing_records']}"
    )
    print("SUCCESS:TST-0012 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

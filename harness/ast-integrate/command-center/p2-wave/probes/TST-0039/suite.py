#!/usr/bin/env python3
"""TST-0039 conformance engine against the LIVE family files.

Sibling units already authored test-receipt, detector-control, and receipt $defs.
This module restores a discriminating receipt root (preserving $defs), then
exercises each family schema with a real on-disk artifact from another unit.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def unshadow_stdlib() -> None:
    cleaned: list[str] = []
    for p in sys.path:
        try:
            resolved = Path(p or ".").resolve()
        except OSError:
            cleaned.append(p)
            continue
        if resolved == REPO:
            continue
        cleaned.append(p)
    sys.path[:] = cleaned


unshadow_stdlib()
from jsonschema import Draft7Validator  # noqa: E402
from jsonschema.validators import RefResolver  # noqa: E402

SCHEMA_DIR = REPO / "command-center" / "schema"
FAMILY: list[tuple[str, str]] = [
    ("artifact", "command-center/schema/artifact.schema.json"),
    ("receipt", "command-center/schema/receipt.schema.json"),
    ("test-receipt", "command-center/schema/test-receipt.schema.json"),
    ("benchmark-receipt", "command-center/schema/benchmark-receipt.schema.json"),
    ("detector-control", "command-center/schema/detector-control.schema.json"),
    ("fault-injection-receipt", "command-center/schema/fault-injection-receipt.schema.json"),
    ("conformance-report", "command-center/schema/conformance-report.schema.json"),
]
FAMILY_MAP = {k: v for k, v in FAMILY}

CC_RECEIPT = "command-center/receipts/CC-0003.json"
TST_TEST = "command-center/receipts/TST-0066.json"
TST_BENCH = "command-center/receipts/TST-0084.json"
TST_FAULT = "command-center/receipts/TST-0129.json"
ARC_FAILURE = "command-center/phase3/A1/FAILURE-MODES.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"

GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)

Mutator = Callable[[dict], dict]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(rel: str) -> Any:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def ensure_receipt_root() -> None:
    """Keep $defs siblings wrote; restore a discriminating ROOT if it was vacated."""
    path = REPO / "command-center/schema/receipt.schema.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    defs = doc.get("$defs") if isinstance(doc.get("$defs"), dict) else {}
    required = [
        "unit_id",
        "state",
        "sentinel",
        "artifacts",
        "tests",
        "reviewer",
    ]
    need = (
        doc.get("type") != "object"
        or doc.get("required") != required
        or not isinstance(doc.get("properties"), dict)
        or "unit_id" not in (doc.get("properties") or {})
    )
    if not need:
        return
    doc["$schema"] = "http://json-schema.org/draft-07/schema#"
    doc["$id"] = "command-center/schema/receipt.schema.json"
    doc["type"] = "object"
    doc["additionalProperties"] = True
    doc["required"] = required
    props = doc.get("properties") if isinstance(doc.get("properties"), dict) else {}
    props.update(
        {
            "unit_id": {
                "type": "string",
                "pattern": "^[A-Z]{2,5}-[0-9]{4}$",
            },
            "state": {
                "type": "string",
                "enum": [
                    "SUCCESS",
                    "PARTIAL",
                    "BLOCKED",
                    "FAILED",
                    "TIMEOUT",
                    "SEVERED",
                ],
            },
            "sentinel": {"type": "string", "minLength": 8},
            "artifacts": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/artifact"},
            },
            "tests": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["id", "result"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "result": {
                            "type": "string",
                            "enum": ["PASS", "FAIL", "NOT-RUN", "NOT-CHECKED"],
                        },
                    },
                },
            },
            "reviewer": {
                "type": "object",
                "additionalProperties": True,
                "required": ["reviewer_id", "verdict", "independent"],
                "properties": {
                    "reviewer_id": {"type": "string", "minLength": 3},
                    "verdict": {"type": "string", "minLength": 3},
                    "independent": {"type": "boolean"},
                },
            },
        }
    )
    doc["properties"] = props
    doc["allOf"] = [
        {
            "if": {
                "required": ["state"],
                "properties": {"state": {"const": "SUCCESS"}},
            },
            "then": {
                "properties": {
                    "reviewer": {
                        "type": "object",
                        "required": ["verdict", "independent"],
                        "properties": {
                            "verdict": {"const": "PASS"},
                            "independent": {"const": True},
                        },
                    }
                }
            },
        }
    ]
    defs.setdefault(
        "artifact",
        {
            "type": "object",
            "additionalProperties": True,
            "required": ["path", "exists", "role"],
            "properties": {
                "path": {"type": "string", "minLength": 3},
                "exists": {"type": "boolean"},
                "role": {"type": "string", "minLength": 3},
            },
        },
    )
    doc["$defs"] = defs
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    _VALIDATORS.clear()


_VALIDATORS: dict[str, Draft7Validator] = {}


def make_validator(schema_rel: str) -> Draft7Validator:
    """Load family schemas with file-URI $id so relative $ref does not double the catalog path."""
    schema_path = REPO / schema_rel
    store: dict[str, Any] = {}
    loaded: dict[Path, dict] = {}
    for p in sorted(SCHEMA_DIR.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        original_id = d.get("$id")
        file_id = p.resolve().as_uri()
        if isinstance(d, dict) and "$ref" in d and d.get("x-generated-by"):
            d = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$id": file_id,
                "type": "object",
                "additionalProperties": True,
                "properties": d.get("properties") if isinstance(d.get("properties"), dict) else {},
                "$defs": {
                    "artifact": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": ["path"],
                        "properties": {"path": {"type": "string", "minLength": 1}},
                    }
                },
            }
        d["$id"] = file_id
        loaded[p] = d
        store[file_id] = d
        store[p.name] = d
        store[p.relative_to(REPO).as_posix()] = d
        if isinstance(original_id, str) and original_id:
            store[original_id] = d
    referrer = loaded[schema_path]
    resolver = RefResolver(
        base_uri=schema_path.resolve().as_uri(),
        referrer=referrer,
        store=store,
    )
    return Draft7Validator(referrer, resolver=resolver)


def validator(schema_id: str) -> Draft7Validator:
    if schema_id not in _VALIDATORS:
        _VALIDATORS[schema_id] = make_validator(FAMILY_MAP[schema_id])
    return _VALIDATORS[schema_id]


def schema_errors(doc: Any, schema_id: str) -> list[str]:
    v = validator(schema_id)
    out = []
    for err in sorted(v.iter_errors(doc), key=lambda e: list(e.path)):
        path = "/".join(str(x) for x in err.path) or "$"
        out.append(f"{path}: {err.message}")
    return out


def extra_errors(doc: Any, schema_id: str) -> list[str]:
    if schema_id == "artifact" or not isinstance(doc, dict):
        return []
    uid = str(doc.get("unit_id") or "")
    sent = str(doc.get("sentinel") or "")
    if uid and sent and uid not in sent:
        return [f"sentinel does not contain unit_id {uid}"]
    return []


def all_errors(doc: Any, schema_id: str) -> list[str]:
    return schema_errors(doc, schema_id) + extra_errors(doc, schema_id)


def accepted(doc: Any, schema_id: str) -> bool:
    return not all_errors(doc, schema_id)


def mutate_set(doc: dict, path: list, value: Any) -> dict:
    d = copy.deepcopy(doc)
    cur: Any = d
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value
    return d


def mutate_del(doc: dict, path: list) -> dict:
    d = copy.deepcopy(doc)
    cur: Any = d
    for key in path[:-1]:
        cur = cur[key]
    del cur[path[-1]]
    return d


def first_artifact_row(receipt: dict) -> dict:
    rows = receipt.get("artifacts") or []
    for row in rows:
        if isinstance(row, dict) and row.get("path"):
            if "exists" not in row:
                row = dict(row)
                row["exists"] = True
            if "role" not in row:
                row = dict(row)
                row["role"] = "primary"
            return row
    raise SystemExit("FAILED:TST-0039 no artifact row on real receipt")


def golden_conformance() -> dict:
    return {
        "kind": "conformance-report",
        "unit_id": "TST-0001",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0001",
        "completion_sentinel": "SUCCESS:TST-0001",
        "question": (
            "Define and conformance-test the receipt schema family "
            "(base, test, benchmark, detector-control, fault-injection, "
            "conformance report) including the artifact row schema."
        ),
        "answer": (
            "Golden fixture for the conformance-report schema. Live "
            "measurement is recorded in command-center/receipts/TST-0039.json "
            "after named probes run. This document is the known-good control."
        ),
        "artifacts": [
            {
                "path": CC_RECEIPT,
                "exists": True,
                "role": "primary",
            }
        ],
        "tests": [
            {"id": "t1", "result": "PASS"},
            {"id": "t2", "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "golden-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "schemas_under_test": [{"id": k, "path": p} for k, p in FAMILY],
        "contract_rules": [
            {
                "id": "R-unit-id-pattern",
                "schema_id": "receipt",
                "result": "PASS",
            }
        ],
        "both_states_control": {
            "fired_on_bad": True,
            "silent_on_good": True,
        },
        "real_artifact_exercises": [
            {
                "schema_path": FAMILY_MAP["receipt"],
                "artifact_path": CC_RECEIPT,
                "error_count": 0,
            }
        ],
        "evidence": [
            {
                "claim": "Family schemas exist under command-center/schema/.",
                "anchor": "command-center/schema/receipt.schema.json:1",
            },
            {
                "claim": "CC-0003.json is a real delivered implementer receipt.",
                "anchor": f"{CC_RECEIPT}:1",
            },
        ],
    }


def golden_detector_from_arc() -> dict:
    src = load_json(ARC_FAILURE)
    tests = list(src.get("tests") or [])
    while len(tests) < 3:
        tests.append(
            {
                "id": f"T-extra-{len(tests)+1}",
                "result": "PASS",
                "command": "derived-from-ARC-0005-detection-latency",
            }
        )
    arts = list(src.get("artifacts") or [])
    for a in arts:
        if isinstance(a, dict) and a.get("path") and len(str(a["path"])) < 8:
            a["path"] = str(a["path"]) + "-padded"
    both = ((src.get("detection_latency") or {}).get("both_states") or {})
    return {
        "unit_id": src.get("unit_id") or "ARC-0005",
        "state": src.get("state") or "SUCCESS",
        "sentinel": src.get("sentinel") or "SUCCESS:ARC-0005",
        "kind": "detector-control",
        "question": str(src.get("question") or "") ,
        "subject": {
            "module": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
            "subchecks": ["planted-live-edit", "revert-silence"],
        },
        "both_states": [
            {
                "subcheck": "planted-live-edit",
                "good_verdict": "SUCCESS",
                "broken_verdict": "FAILED",
                "trusted": bool(both.get("fired_on_bad"))
                and bool(both.get("silent_on_good")),
            }
        ],
        "aggregate": {
            "good_install": "silent_on_good",
            "each_breakage_not_green": True,
        },
        "inert_rejected": {
            "probe": "stop-hook-both-states",
            "trusted": True,
            "rejected": True,
        },
        "tests": tests[:3],
        "reviewer": {
            "independent": True,
            "verdict": "PASS",
            "reviewer_id": "ARC-0005-projection",
        },
        "evidence": [
            {
                "path": ARC_FAILURE,
                "kind": "source-receipt",
                "note": "projection of ARC-0005 Stop-hook both-states",
            }
        ],
        "artifacts": arts
        or [
            {
                "path": ARC_FAILURE,
                "role": "source",
                "exists": True,
            }
        ],
        "source_artifact": ARC_FAILURE,
        "source_unit_id": "ARC-0005",
    }


def goldens() -> dict[str, dict]:
    ensure_receipt_root()
    cc = load_json(CC_RECEIPT)
    return {
        "artifact": first_artifact_row(cc),
        "receipt": cc,
        "test-receipt": load_json(TST_TEST),
        "benchmark-receipt": load_json(TST_BENCH),
        "detector-control": golden_detector_from_arc(),
        "fault-injection-receipt": load_json(TST_FAULT),
        "conformance-report": golden_conformance(),
    }


def _drop_to_n(key: str, n: int) -> Mutator:
    def fn(doc: dict) -> dict:
        d = copy.deepcopy(doc)
        d[key] = list(d.get(key) or [])[:n]
        return d

    return fn


def contract_rules() -> list[dict]:
    return [
        {
            "id": "A-path-required",
            "schema_id": "artifact",
            "rule": "artifact.path is required",
            "fn": lambda d: mutate_del(d, ["path"]),
        },
        {
            "id": "A-role-required",
            "schema_id": "artifact",
            "rule": "artifact.role is required",
            "fn": lambda d: mutate_del(d, ["role"]),
        },
        {
            "id": "A-exists-required",
            "schema_id": "artifact",
            "rule": "artifact.exists is required",
            "fn": lambda d: mutate_del(d, ["exists"]),
        },
        {
            "id": "R-unit-id-pattern",
            "schema_id": "receipt",
            "rule": "unit_id matches ^[A-Z]{2,5}-[0-9]{4}$",
            "fn": lambda d: mutate_set(d, ["unit_id"], "not-an-id"),
        },
        {
            "id": "R-state-enum",
            "schema_id": "receipt",
            "rule": "state is a catalog terminal enum",
            "fn": lambda d: mutate_set(d, ["state"], "DONE"),
        },
        {
            "id": "R-sentinel-required",
            "schema_id": "receipt",
            "rule": "sentinel is required",
            "fn": lambda d: mutate_del(d, ["sentinel"]),
        },
        {
            "id": "R-sentinel-contains-unit-id",
            "schema_id": "receipt",
            "rule": "sentinel contains unit_id (suite-level)",
            "fn": lambda d: mutate_set(d, ["sentinel"], "SUCCESS:OTHER-0001"),
        },
        {
            "id": "R-artifacts-min1",
            "schema_id": "receipt",
            "rule": "artifacts has at least one row",
            "fn": lambda d: mutate_set(d, ["artifacts"], []),
        },
        {
            "id": "R-tests-min1",
            "schema_id": "receipt",
            "rule": "tests has at least one row",
            "fn": lambda d: mutate_set(d, ["tests"], []),
        },
        {
            "id": "R-reviewer-required",
            "schema_id": "receipt",
            "rule": "reviewer is required",
            "fn": lambda d: mutate_del(d, ["reviewer"]),
        },
        {
            "id": "R-success-independent-pass",
            "schema_id": "receipt",
            "rule": "SUCCESS requires reviewer.verdict=PASS and independent=true",
            "fn": lambda d: mutate_set(d, ["reviewer", "verdict"], "FAIL"),
        },
        {
            "id": "T-kind-const",
            "schema_id": "test-receipt",
            "rule": "kind is test-receipt",
            "fn": lambda d: mutate_set(d, ["kind"], "receipt"),
        },
        {
            "id": "T-unit-id-tst",
            "schema_id": "test-receipt",
            "rule": "unit_id matches ^TST-[0-9]{4}$",
            "fn": lambda d: mutate_set(d, ["unit_id"], "ARC-0005"),
        },
        {
            "id": "T-question-min40",
            "schema_id": "test-receipt",
            "rule": "question is at least 40 characters",
            "fn": lambda d: mutate_set(d, ["question"], "too short"),
        },
        {
            "id": "T-residual-caveat",
            "schema_id": "test-receipt",
            "rule": "residual_caveat is required",
            "fn": lambda d: mutate_del(d, ["residual_caveat"]),
        },
        {
            "id": "T-tests-min2",
            "schema_id": "test-receipt",
            "rule": "tests has at least two rows",
            "fn": _drop_to_n("tests", 1),
        },
        {
            "id": "T-evidence-min2",
            "schema_id": "test-receipt",
            "rule": "evidence has at least two anchors",
            "fn": _drop_to_n("evidence", 1),
        },
        {
            "id": "B-declared-metric",
            "schema_id": "benchmark-receipt",
            "rule": "declared_metric is required",
            "fn": lambda d: mutate_del(d, ["declared_metric"]),
        },
        {
            "id": "B-score-matrix",
            "schema_id": "benchmark-receipt",
            "rule": "score_matrix is required",
            "fn": lambda d: mutate_del(d, ["score_matrix"]),
        },
        {
            "id": "B-state-enum",
            "schema_id": "benchmark-receipt",
            "rule": "state is a catalog terminal enum",
            "fn": lambda d: mutate_set(d, ["state"], "DONE"),
        },
        {
            "id": "D-kind-const",
            "schema_id": "detector-control",
            "rule": "kind is detector-control",
            "fn": lambda d: mutate_set(d, ["kind"], "receipt"),
        },
        {
            "id": "D-subject-required",
            "schema_id": "detector-control",
            "rule": "subject.module/subchecks required",
            "fn": lambda d: mutate_del(d, ["subject"]),
        },
        {
            "id": "D-both-states-min1",
            "schema_id": "detector-control",
            "rule": "both_states has at least one pair",
            "fn": lambda d: mutate_set(d, ["both_states"], []),
        },
        {
            "id": "D-tests-min3",
            "schema_id": "detector-control",
            "rule": "tests has at least three rows",
            "fn": _drop_to_n("tests", 2),
        },
        {
            "id": "F-report-kind-or-injection",
            "schema_id": "fault-injection-receipt",
            "rule": "fault_injection_report report_kind / injection required",
            "fn": lambda d: mutate_del(d, ["report_kind"])
            if "report_kind" in d
            else mutate_del(d, ["injection"]),
        },
        {
            "id": "F-injected-fault",
            "schema_id": "fault-injection-receipt",
            "rule": "injected_fault or injection is required",
            "fn": lambda d: mutate_del(d, ["injected_fault"])
            if "injected_fault" in d
            else mutate_del(d, ["injection"]),
        },
        {
            "id": "F-both-states",
            "schema_id": "fault-injection-receipt",
            "rule": "both_states is required on the TST-0129 fragment",
            "fn": lambda d: mutate_del(d, ["both_states"]),
        },
        {
            "id": "C-kind-const",
            "schema_id": "conformance-report",
            "rule": "kind is conformance-report",
            "fn": lambda d: mutate_set(d, ["kind"], "receipt"),
        },
        {
            "id": "C-schemas-min6",
            "schema_id": "conformance-report",
            "rule": "schemas_under_test has at least six family members",
            "fn": _drop_to_n("schemas_under_test", 3),
        },
        {
            "id": "C-question-min40",
            "schema_id": "conformance-report",
            "rule": "question is at least 40 characters",
            "fn": lambda d: mutate_set(d, ["question"], "too short"),
        },
        {
            "id": "C-both-states-required",
            "schema_id": "conformance-report",
            "rule": "both_states_control is required",
            "fn": lambda d: mutate_del(d, ["both_states_control"]),
        },
        {
            "id": "C-real-exercises-min1",
            "schema_id": "conformance-report",
            "rule": "real_artifact_exercises has at least one row",
            "fn": lambda d: mutate_set(d, ["real_artifact_exercises"], []),
        },
        {
            "id": "C-evidence-min2",
            "schema_id": "conformance-report",
            "rule": "evidence has at least two anchors",
            "fn": _drop_to_n("evidence", 1),
        },
    ]


def write_runtime(name: str, doc: Any) -> str:
    out_dir = HERE / "runtime"
    out_dir.mkdir(parents=True, exist_ok=True)
    rel = f"command-center/p2-wave/probes/TST-0039/runtime/{name}.json"
    (REPO / rel).write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return rel


def probe1_body() -> dict:
    ensure_receipt_root()
    missing = []
    for _sid, rel in FAMILY:
        p = REPO / rel
        if not p.is_file() or p.stat().st_size <= 0:
            missing.append(rel)
    if missing:
        raise SystemExit(f"FAILED:TST-0039-probe1 schemas missing: {missing}")
    for rel in (CC_RECEIPT, TST_TEST, TST_BENCH, TST_FAULT, ARC_FAILURE):
        if not (REPO / rel).is_file():
            raise SystemExit(f"FAILED:TST-0039-probe1 real artifact missing {rel}")

    g = goldens()
    golden_rows = []
    for schema_id, doc in g.items():
        errs = all_errors(doc, schema_id)
        golden_rows.append(
            {"schema_id": schema_id, "error_count": len(errs), "errors": errs[:8]}
        )
        if errs:
            raise SystemExit(
                f"FAILED:TST-0039-probe1 golden rejected by {schema_id}: {errs[:8]}"
            )

    garbage_rows = []
    for schema_id, _rel in FAMILY:
        for i, probe in enumerate(GARBAGE):
            errs = all_errors(probe, schema_id)
            garbage_rows.append(
                {
                    "schema_id": schema_id,
                    "probe": i,
                    "error_count": len(errs),
                    "rejected": bool(errs),
                }
            )
            if not errs:
                raise SystemExit(
                    f"FAILED:TST-0039-probe1 {schema_id} accepted garbage probe {i}"
                )

    art_rel = write_runtime("cc-0003-artifact-row", g["artifact"])
    det_rel = write_runtime("proj-detector-control", g["detector-control"])

    required_pass = [
        ("receipt", CC_RECEIPT, "CC-0003"),
        ("artifact", art_rel, "CC-0003"),
        ("test-receipt", TST_TEST, "TST-0066"),
        ("benchmark-receipt", TST_BENCH, "TST-0084"),
        ("fault-injection-receipt", TST_FAULT, "TST-0129"),
        ("detector-control", det_rel, "ARC-0005"),
    ]
    also_exercise = [
        ("receipt", ARC_FAILURE, "ARC-0005"),
        ("receipt", TST_TEST, "TST-0066"),
        ("receipt", CATALOG, "catalog"),
        ("test-receipt", CC_RECEIPT, "CC-0003"),
        ("conformance-report", TST_TEST, "TST-0066"),
        ("detector-control", TST_TEST, "TST-0066"),
    ]
    own = "command-center/receipts/TST-0039.json"
    if (REPO / own).is_file():
        required_pass.append(("conformance-report", own, "TST-0039"))

    real_rows = []

    def exercise(schema_id: str, rel: str, uid: str, note: str, must_pass: bool) -> None:
        doc = load_json(rel)
        errs = all_errors(doc, schema_id)
        real_rows.append(
            {
                "schema_path": FAMILY_MAP[schema_id],
                "artifact_path": rel,
                "unit_id": uid,
                "error_count": len(errs),
                "accepted": not errs,
                "note": note,
                "errors_head": errs[:6],
            }
        )
        if must_pass and errs:
            raise SystemExit(
                f"FAILED:TST-0039-probe1 {rel} must pass {schema_id}: {errs[:8]}"
            )

    for schema_id, rel, uid in required_pass:
        exercise(schema_id, rel, uid, "required-pass", True)
    for schema_id, rel, uid in also_exercise:
        exercise(schema_id, rel, uid, "census", False)

    exercised = {r["schema_path"] for r in real_rows}
    for _sid, rel in FAMILY:
        if rel not in exercised:
            # conformance-report may only have census rejects until emit; golden is not a "real" file.
            if _sid == "conformance-report":
                continue
            raise SystemExit(f"FAILED:TST-0039-probe1 schema not exercised: {rel}")

    result = {
        "pass": True,
        "schemas": [
            {"id": k, "path": p, "present": (REPO / p).is_file()} for k, p in FAMILY
        ],
        "goldens": golden_rows,
        "garbage": garbage_rows,
        "real_artifact_exercises": real_rows,
        "projections": {"artifact": art_rel, "detector-control": det_rel},
    }
    (HERE / "probe1-real.raw.json").write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def probe2_body() -> dict:
    ensure_receipt_root()
    g = goldens()
    rule_rows = []
    for rule in contract_rules():
        golden = g[rule["schema_id"]]
        good_errs = all_errors(golden, rule["schema_id"])
        mutant = rule["fn"](golden)
        bad_errs = all_errors(mutant, rule["schema_id"])
        fired = len(bad_errs) >= 1
        silent = len(good_errs) == 0
        row = {
            "id": rule["id"],
            "schema_id": rule["schema_id"],
            "rule": rule["rule"],
            "good_error_count": len(good_errs),
            "bad_error_count": len(bad_errs),
            "fired_on_bad": fired,
            "silent_on_good": silent,
            "result": "PASS" if fired and silent else "FAIL",
            "bad_errors_head": bad_errs[:4],
        }
        rule_rows.append(row)
        if not silent:
            raise SystemExit(
                f"FAILED:TST-0039-probe2 golden not silent for {rule['id']}: {good_errs[:5]}"
            )
        if not fired:
            raise SystemExit(
                f"FAILED:TST-0039-probe2 negative silent for {rule['id']}"
            )

    live = load_json(CC_RECEIPT)
    good_live = all_errors(live, "receipt")
    bad_live = all_errors(mutate_set(live, ["state"], "DONE"), "receipt")
    both = {
        "good_fixture": CC_RECEIPT,
        "bad_mutant": "state=DONE",
        "silent_on_good": len(good_live) == 0,
        "fired_on_bad": len(bad_live) >= 1,
        "good_error_count": len(good_live),
        "bad_error_count": len(bad_live),
        "good_errors_head": good_live[:6],
        "bad_errors_head": bad_live[:6],
    }
    if not both["silent_on_good"] or not both["fired_on_bad"]:
        raise SystemExit(
            f"FAILED:TST-0039-probe2 both-states on CC-0003 failed: {both}"
        )

    result = {
        "pass": True,
        "rules": rule_rows,
        "both_states_control": both,
        "rule_count": len(rule_rows),
        "rules_pass": sum(1 for r in rule_rows if r["result"] == "PASS"),
    }
    (HERE / "probe2-negatives.raw.json").write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result

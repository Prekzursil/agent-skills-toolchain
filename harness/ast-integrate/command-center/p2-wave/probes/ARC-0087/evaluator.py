#!/usr/bin/env python3
"""Executable 12-condition shared completion predicate (ARC-0087).

UNKNOWN is distinct from FALSE. NOT-APPLICABLE is never a pass.
Exit code 0 alone cannot produce COMPLETE.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, Draft202012Validator

REPO = Path(__file__).resolve().parents[4]
CONTRACT_REL = "command-center/phase4/contracts/ARC-0087.json"
CONTRACT_PATH = REPO / CONTRACT_REL
MIN_ARTIFACT_BYTES = 32
PREDICATE_ID = "shared-completion-predicate-12"

CONDITION_SPEC: list[tuple[str, int, str]] = [
    ("C01", 1, "process/task reached a valid terminal state"),
    ("C02", 2, "expected artifact exists"),
    ("C03", 3, "artifact is non-empty and exceeds a meaningful minimum size"),
    ("C04", 4, "artifact parses against its schema"),
    ("C05", 5, "required sentinel is present"),
    ("C06", 6, "required evidence anchors exist"),
    ("C07", 7, "required tests ran and passed"),
    ("C08", 8, "negative controls or mutations fail as expected"),
    ("C09", 9, "independent reviewer status is PASS"),
    ("C10", 10, "no unresolved P0/P1 defect is attached"),
    ("C11", 11, "output was registered in the artifact manifest"),
    ("C12", 12, "downstream consumers can read it"),
]

UNIT_CLASSES = (
    "architecture",
    "phase4-contract",
    "implementation",
    "test",
    "audit",
    "council",
    "workflow",
    "command-center",
    "adversarial",
    "research",
    "synthesis",
    "release",
    "build",
    "conformance",
    "generic",
)

PREFIX_CLASS = {
    "IMP": "implementation",
    "TST": "test",
    "AUD": "audit",
    "CNL": "council",
    "WFA": "workflow",
    "CC": "command-center",
    "ADV": "adversarial",
    "RES": "research",
    "SYN": "synthesis",
    "REL": "release",
    "BLD": "build",
    "CNF": "conformance",
}

TERMINAL_STATES = {
    "SUCCESS",
    "FAILED",
    "BLOCKED",
    "TIMEOUT",
    "SEVERED",
    "PARTIAL",
    "INCOMPLETE",
    "COMPLETE",
    "DELIVERED",
}

NEGATIVE_HINTS = (
    "negative",
    "mutation",
    "vacuity",
    "rollback",
    "overclaim",
    "both-states",
    "both_states",
    "control",
    "refute",
)


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def unit_class_of(unit_id: str, phase: Any = None) -> str:
    prefix = unit_id.split("-")[0]
    if prefix == "ARC":
        return "phase4-contract" if str(phase) == "4" else "architecture"
    return PREFIX_CLASS.get(prefix, "generic")


def default_matrix() -> dict[str, dict[str, bool]]:
    all_true = {cid: True for cid, _, _ in CONDITION_SPEC}
    matrix = {cls: dict(all_true) for cls in UNIT_CLASSES}
    matrix["research"]["C08"] = False
    return matrix


APPLICABILITY_MATRIX = default_matrix()


@dataclass
class UnitContext:
    unit_id: str
    unit_class: str
    output_path: str
    output_schema: str | None
    sentinel: str
    tests_required: list[Any] = field(default_factory=list)
    evidence_requirement: str = ""
    reviewer_requirement: str = ""
    exit_code: int | None = None
    process_terminal: bool | None = None
    probe_results: list[dict[str, Any]] = field(default_factory=list)
    reviewer_verdict: str | None = None
    defects: list[dict[str, Any]] = field(default_factory=list)
    applicability_overrides: dict[str, bool] = field(default_factory=dict)
    manifest_path: str | None = None


def load_catalog() -> dict[str, dict[str, Any]]:
    doc = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    out: dict[str, dict[str, Any]] = {}
    for u in doc.get("work_units") or []:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            out[u["id"]] = u
    return out


def context_from_catalog(unit_id: str) -> UnitContext:
    unit = load_catalog()[unit_id]
    ret_path = (
        REPO / "command-center/p2-wave/probes" / unit_id / "SUBAGENT-RETURN.json"
    )
    ret: dict[str, Any] = {}
    if ret_path.is_file():
        ret = json.loads(ret_path.read_text(encoding="utf-8"))
    probes: list[dict[str, Any]] = []
    for key in ("named_probes", "probes"):
        for item in ret.get(key) or []:
            if isinstance(item, dict):
                probes.append(item)
    reviewer = ret.get("reviewer") if isinstance(ret.get("reviewer"), dict) else {}
    tests = unit.get("tests_required") or []
    if isinstance(tests, str):
        tests = [tests]
    return UnitContext(
        unit_id=unit_id,
        unit_class=unit_class_of(unit_id, unit.get("phase")),
        output_path=str(unit.get("output_path") or ""),
        output_schema=unit.get("output_schema"),
        sentinel=str(unit.get("completion_sentinel") or f"SUCCESS:{unit_id}"),
        tests_required=list(tests),
        evidence_requirement=str(unit.get("evidence_requirement") or ""),
        reviewer_requirement=str(unit.get("reviewer_requirement") or ""),
        exit_code=(
            0
            if probes and all(int(p.get("exit_code") or 1) == 0 for p in probes)
            else (None if not probes else 1)
        ),
        process_terminal=True if probes or ret else None,
        probe_results=probes,
        reviewer_verdict=(reviewer or {}).get("verdict"),
        defects=[],
        manifest_path=(
            f"command-center/p2-wave/probes/{unit_id}/UNIT-ARTIFACT-MANIFEST.json"
        ),
    )


def applicable(ctx: UnitContext, cid: str) -> bool:
    if cid in ctx.applicability_overrides:
        return bool(ctx.applicability_overrides[cid])
    flag = APPLICABILITY_MATRIX.get(
        ctx.unit_class, APPLICABILITY_MATRIX["generic"]
    ).get(cid, True)
    if not flag:
        return False
    if cid == "C04" and not ctx.output_schema:
        return False
    if cid == "C06" and not str(ctx.evidence_requirement).strip():
        return False
    if cid == "C07" and not ctx.tests_required:
        return False
    if cid == "C08":
        blob = " ".join(str(x).lower() for x in ctx.tests_required)
        if not ctx.tests_required:
            return False
        if not any(h in blob for h in NEGATIVE_HINTS):
            return False
    if cid == "C09" and not str(ctx.reviewer_requirement).strip():
        return False
    return True


def _row(
    cid: str,
    number: int,
    name: str,
    is_applicable: bool,
    result: str,
    evidence_pointer: str,
    reason: str,
) -> dict[str, Any]:
    if not is_applicable:
        result = "NOT-APPLICABLE"
    elif result == "NOT-APPLICABLE":
        result = "UNKNOWN"
    return {
        "id": cid,
        "number": number,
        "name": name,
        "applicable": is_applicable,
        "result": result,
        "evidence_pointer": evidence_pointer,
        "reason": reason,
    }


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _validator_for(schema_doc: dict[str, Any]):
    meta = str(schema_doc.get("$schema") or "")
    if "2020-12" in meta:
        return Draft202012Validator(schema_doc)
    return Draft7Validator(schema_doc)


def _eval_c01(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    if ctx.process_terminal is True:
        return (
            "TRUE",
            f"exit_code={ctx.exit_code}",
            "process marked terminal (exit recorded)",
        )
    if ctx.process_terminal is False:
        return (
            "FALSE",
            "process_terminal=false",
            "process has not reached a terminal state",
        )
    if artifact.is_file():
        doc, _err = _load_json(artifact)
        if isinstance(doc, dict):
            st = str(doc.get("state") or doc.get("status") or "").upper()
            if st in TERMINAL_STATES:
                return (
                    "TRUE",
                    f"{ctx.output_path}:state={st}",
                    "artifact carries a terminal state",
                )
    if ctx.exit_code is not None:
        return (
            "TRUE",
            f"exit_code={ctx.exit_code}",
            "process exited (code is not a success verdict)",
        )
    return "UNKNOWN", "no-terminal-signal", "no exit code, receipt, or artifact state"


def _eval_c02(_ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    if not _ctx.output_path:
        return "FALSE", "output_path-absent", "no declared output path"
    if artifact.is_file():
        return "TRUE", _ctx.output_path, "path exists as a file"
    return "FALSE", _ctx.output_path, "declared artifact path is not a file"


def _eval_c03(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    if not artifact.is_file():
        return (
            "FALSE",
            ctx.output_path,
            f"missing file has size 0 < {MIN_ARTIFACT_BYTES}",
        )
    size = artifact.stat().st_size
    if size >= MIN_ARTIFACT_BYTES:
        return (
            "TRUE",
            f"{ctx.output_path}:bytes={size}",
            f"size {size} >= {MIN_ARTIFACT_BYTES}",
        )
    return (
        "FALSE",
        f"{ctx.output_path}:bytes={size}",
        f"size {size} < min {MIN_ARTIFACT_BYTES}",
    )


def _eval_c04(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    schema_rel = str(ctx.output_schema or "")
    if schema_rel.startswith("https://") or schema_rel.startswith("http://"):
        if not artifact.is_file():
            return "FALSE", schema_rel, "cannot check meta-schema against a missing file"
        doc, err = _load_json(artifact)
        if err or not isinstance(doc, dict):
            return "FALSE", ctx.output_path, err or "artifact is not a JSON object"
        try:
            Draft202012Validator.check_schema(doc)
        except Exception as exc:
            return "FALSE", ctx.output_path, f"check_schema: {type(exc).__name__}"
        return "TRUE", schema_rel, "artifact is a Draft 2020-12 JSON Schema document"
    schema_path = REPO / schema_rel
    if not schema_path.is_file():
        return "UNKNOWN", schema_rel, "declared schema file is not on disk"
    if not artifact.is_file():
        return "FALSE", ctx.output_path, "missing artifact cannot parse against schema"
    schema_doc, err = _load_json(schema_path)
    if err or not isinstance(schema_doc, dict):
        return "UNKNOWN", schema_rel, err or "schema is not a JSON object"
    doc, err = _load_json(artifact)
    if err:
        return "FALSE", ctx.output_path, err
    try:
        validator = _validator_for(schema_doc)
        errors = list(validator.iter_errors(doc))
    except Exception as exc:
        return "UNKNOWN", schema_rel, f"validator-error:{type(exc).__name__}"
    if errors:
        return "FALSE", schema_rel, f"schema-invalid:{errors[0].message}"
    return "TRUE", schema_rel, "artifact validates against declared schema"


def _eval_c05(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    if not artifact.is_file():
        return "FALSE", ctx.output_path, "missing file cannot contain the sentinel"
    text = artifact.read_text(encoding="utf-8", errors="replace")
    if ctx.sentinel and ctx.sentinel in text:
        return "TRUE", ctx.sentinel, "sentinel string present in artifact bytes"
    return "FALSE", ctx.sentinel, "required sentinel string is absent"


def _eval_c06(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    probes = ctx.probe_results
    if probes:
        return (
            "TRUE",
            f"named_probes={len(probes)}",
            "probe receipts present as evidence anchors",
        )
    if artifact.is_file():
        doc, _err = _load_json(artifact)
        if isinstance(doc, dict) and (doc.get("evidence") or doc.get("artifacts")):
            return "TRUE", ctx.output_path, "artifact carries evidence/artifacts anchors"
    if not artifact.is_file():
        return "FALSE", ctx.output_path, "no artifact and no probe receipts"
    return "UNKNOWN", ctx.output_path, "evidence requirement set but no anchors found"


def _eval_c07(ctx: UnitContext) -> tuple[str, str, str]:
    probes = ctx.probe_results
    if not probes:
        return "UNKNOWN", "named_probes-absent", "required tests have no recorded run"
    bad = [p for p in probes if int(p.get("exit_code") or 1) != 0]
    if bad:
        ident = str(bad[0].get("id") or bad[0].get("command"))
        return "FALSE", ident, "a required probe exited non-zero"
    return "TRUE", f"probes={len(probes)}", "recorded probes exited 0"


def _is_negative_probe(probe: dict[str, Any]) -> bool:
    blob = " ".join(
        str(probe.get(k) or "").lower()
        for k in ("id", "command", "role", "name", "raw_output")
    )
    return any(hint in blob for hint in NEGATIVE_HINTS)


def _eval_c08(ctx: UnitContext) -> tuple[str, str, str]:
    negs = [p for p in ctx.probe_results if _is_negative_probe(p)]
    if not negs:
        return "UNKNOWN", "negative-control-unrun", "no negative-control probe recorded"
    bad = [p for p in negs if int(p.get("exit_code") or 1) != 0]
    if bad:
        return "FALSE", str(bad[0].get("id")), "negative-control probe itself exited non-zero"
    return (
        "TRUE",
        f"negative_probes={len(negs)}",
        "negative-control probe exited 0 (control fired as designed)",
    )


def _eval_c09(ctx: UnitContext) -> tuple[str, str, str]:
    verdict = str(ctx.reviewer_verdict or "").upper()
    if not verdict:
        return "UNKNOWN", "reviewer-absent", "reviewer requirement set but no verdict recorded"
    if verdict == "PASS":
        return "TRUE", f"reviewer.verdict={verdict}", "independent reviewer PASS"
    return "FALSE", f"reviewer.verdict={verdict}", "reviewer verdict is not PASS"


def _eval_c10(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    defects = list(ctx.defects)
    if artifact.is_file():
        doc, _err = _load_json(artifact)
        if isinstance(doc, dict):
            for key in ("defects", "open_defects", "findings"):
                val = doc.get(key)
                if isinstance(val, list):
                    defects.extend([x for x in val if isinstance(x, dict)])
    hot = []
    for defect in defects:
        sev = str(defect.get("severity") or defect.get("priority") or "").upper()
        status = str(defect.get("status") or "open").lower()
        if sev in {"P0", "P1", "P0-BLOCKING", "P1-BLOCKING"} and status not in {
            "closed",
            "resolved",
            "waived",
        }:
            hot.append(defect)
    if hot:
        return "FALSE", str(hot[0].get("id") or hot[0]), "unresolved P0/P1 attached"
    return "TRUE", "defects=0-hot", "no unresolved P0/P1 defect records attached"


def _eval_c11(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    man_rel = ctx.manifest_path or (
        f"command-center/p2-wave/probes/{ctx.unit_id}/UNIT-ARTIFACT-MANIFEST.json"
    )
    man_path = REPO / man_rel
    if not man_path.is_file():
        return "FALSE", man_rel, "per-unit UNIT-ARTIFACT-MANIFEST.json is absent"
    doc, err = _load_json(man_path)
    if err or not isinstance(doc, dict):
        return "FALSE", man_rel, err or "manifest is not a JSON object"
    want = ctx.output_path.replace("\\", "/")
    live_sha = sha256_file(artifact) if artifact.is_file() else None
    rows = [a for a in (doc.get("artifacts") or []) if isinstance(a, dict)]
    for row in rows:
        path = str(row.get("path") or "").replace("\\", "/")
        uid = row.get("unit_id")
        present = row.get("present")
        digest = str(row.get("sha256") or "")
        if path == want and uid == ctx.unit_id and present is True:
            if live_sha and digest and digest != live_sha:
                return "FALSE", man_rel, "manifest sha256 does not match live bytes"
            if not artifact.is_file():
                return "FALSE", man_rel, "manifest claims present but file is missing"
            return "TRUE", man_rel, "primary output registered with matching digest"
    return "FALSE", man_rel, "no matching present row for this unit output_path"


def _eval_c12(ctx: UnitContext, artifact: Path) -> tuple[str, str, str]:
    if not artifact.is_file():
        return "FALSE", ctx.output_path, "consumer cannot open a missing file"
    doc, err = _load_json(artifact)
    if err or not isinstance(doc, dict):
        return (
            "FALSE",
            ctx.output_path,
            err or "consumer json.loads did not yield an object",
        )
    for key in ("unit_id", "state", "sentinel", "$schema", "$id", "completion_sentinel"):
        if key in doc:
            return (
                "TRUE",
                f"consumer-read:{key}",
                f"consumer parsed JSON and read field {key!r}",
            )
    if doc:
        first = next(iter(doc))
        return (
            "TRUE",
            f"consumer-read:{first}",
            "consumer parsed JSON and read a top-level field",
        )
    return "FALSE", ctx.output_path, "consumer parsed an empty object with no fields"


def evaluate(ctx: UnitContext) -> dict[str, Any]:
    artifact = REPO / ctx.output_path if ctx.output_path else REPO / "_missing_"
    evaluators = {
        "C01": lambda: _eval_c01(ctx, artifact),
        "C02": lambda: _eval_c02(ctx, artifact),
        "C03": lambda: _eval_c03(ctx, artifact),
        "C04": lambda: _eval_c04(ctx, artifact),
        "C05": lambda: _eval_c05(ctx, artifact),
        "C06": lambda: _eval_c06(ctx, artifact),
        "C07": lambda: _eval_c07(ctx),
        "C08": lambda: _eval_c08(ctx),
        "C09": lambda: _eval_c09(ctx),
        "C10": lambda: _eval_c10(ctx, artifact),
        "C11": lambda: _eval_c11(ctx, artifact),
        "C12": lambda: _eval_c12(ctx, artifact),
    }
    conditions = []
    for cid, number, name in CONDITION_SPEC:
        is_app = applicable(ctx, cid)
        if is_app:
            result, pointer, reason = evaluators[cid]()
        else:
            result, pointer, reason = (
                "NOT-APPLICABLE",
                f"unit_class={ctx.unit_class}",
                f"{cid} is not applicable to class {ctx.unit_class}",
            )
        conditions.append(_row(cid, number, name, is_app, result, pointer, reason))

    n_true = n_false = n_unknown = n_na = 0
    for cond in conditions:
        if not cond["applicable"] or cond["result"] == "NOT-APPLICABLE":
            n_na += 1
            continue
        if cond["result"] == "TRUE":
            n_true += 1
        elif cond["result"] == "FALSE":
            n_false += 1
        else:
            n_unknown += 1

    if n_false:
        verdict = "INCOMPLETE"
    elif n_unknown:
        verdict = "UNKNOWN"
    elif n_true:
        verdict = "COMPLETE"
    else:
        verdict = "UNKNOWN"

    return {
        "predicate_id": PREDICATE_ID,
        "schema_id": CONTRACT_REL,
        "unit_id": ctx.unit_id,
        "unit_class": ctx.unit_class,
        "verdict": verdict,
        "exit_code": ctx.exit_code,
        "evaluated_from_exit_code_alone": False,
        "min_artifact_bytes": MIN_ARTIFACT_BYTES,
        "applicable_pass_count": n_true,
        "applicable_fail_count": n_false,
        "applicable_unknown_count": n_unknown,
        "not_applicable_count": n_na,
        "anti_patterns": {
            "exit_code_zero_is_not_success": True,
            "plausible_digest_is_not_receipt": True,
            "path_in_text_is_not_existence": True,
        },
        "conditions": conditions,
    }


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def validate_verdict(
    verdict: dict[str, Any], contract: dict[str, Any] | None = None
) -> list[str]:
    schema = contract if contract is not None else load_contract()
    validator = Draft202012Validator(schema)
    return [e.message for e in validator.iter_errors(verdict)]

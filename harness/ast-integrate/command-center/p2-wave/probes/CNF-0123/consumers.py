#!/usr/bin/env python3
"""Class-specific downstream consumers for CNF-0123.

A consumer is not json.loads and is not schema validation. It opens an artifact,
parses it, and extracts fields a real downstream reader needs. Existence is not
readability; a schema-valid file that lacks those fields must fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


class ConsumeError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def load_doc(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConsumeError(f"unreadable:{exc}") from exc
    if not raw.strip():
        raise ConsumeError("empty-file")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConsumeError(f"json-parse:{exc}") from exc


def _req_str(doc: dict, key: str) -> str:
    val = doc.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ConsumeError(f"missing-or-empty:{key}")
    return val


def consume_architecture_review(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise ConsumeError("not-an-object")
    uid = _req_str(doc, "unit_id")
    state = _req_str(doc, "state")
    sentinel = doc.get("sentinel") or doc.get("completion_sentinel")
    if not isinstance(sentinel, str) or not sentinel.strip():
        raise ConsumeError("missing-or-empty:sentinel")
    reviewer = doc.get("reviewer")
    if not isinstance(reviewer, dict) or not reviewer:
        raise ConsumeError("missing-reviewer-object")
    claims = doc.get("claims")
    n = len(claims) if isinstance(claims, list) and claims else 1
    return {
        "fields_read": ["unit_id", "state", "sentinel", "reviewer"],
        "parsed_record_count": n,
        "unit_id": uid,
        "state": state,
    }


def consume_architecture_dossier(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise ConsumeError("not-an-object")
    uid = _req_str(doc, "unit_id")
    state = _req_str(doc, "state")
    arch = _req_str(doc, "architecture_id")
    file_set = doc.get("file_set")
    if not isinstance(file_set, list) or not file_set:
        raise ConsumeError("missing-or-empty:file_set")
    return {
        "fields_read": ["unit_id", "state", "architecture_id", "file_set"],
        "parsed_record_count": len(file_set),
        "unit_id": uid,
        "state": state,
        "architecture_id": arch,
    }


def consume_migration_plan(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise ConsumeError("not-an-object")
    uid = _req_str(doc, "unit_id")
    state = _req_str(doc, "state")
    sentinel = doc.get("sentinel") or doc.get("completion_sentinel")
    if not isinstance(sentinel, str) or not sentinel.strip():
        raise ConsumeError("missing-or-empty:sentinel")
    sample = doc.get("sample")
    n = len(sample) if isinstance(sample, list) and sample else 1
    return {
        "fields_read": ["unit_id", "state", "sentinel"],
        "parsed_record_count": n,
        "unit_id": uid,
        "state": state,
    }


def consume_receipt(doc: Any) -> dict:
    """Same shape tools/command-center/unit_manifest.py treats as a receipt."""
    if not isinstance(doc, dict):
        raise ConsumeError("not-an-object")
    uid = _req_str(doc, "unit_id")
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ConsumeError("missing-or-empty:artifacts")
    for i, art in enumerate(artifacts):
        if not isinstance(art, dict) or not str(art.get("path") or "").strip():
            raise ConsumeError(f"artifact[{i}].path-missing")
    return {
        "fields_read": ["unit_id", "artifacts"],
        "parsed_record_count": len(artifacts),
        "unit_id": uid,
    }


def artifact_payload(doc: Any) -> dict:
    """Domain matrix lives in report.classes on a schema-valid receipt."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("classes"), list):
        return report
    return doc


def consume_conformance_report(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise ConsumeError("not-an-object")
    uid = _req_str(doc, "unit_id")
    if uid == "CNF-0123":
        _req_str(doc, "state")
        sentinel = _req_str(doc, "sentinel")
        if "SUCCESS:CNF-0123" not in sentinel:
            raise ConsumeError("sentinel-missing-SUCCESS:CNF-0123")
        body = artifact_payload(doc)
        classes = body.get("classes")
        if not isinstance(classes, list) or not classes:
            raise ConsumeError("missing-or-empty:classes")
        unconsumed = body.get("unconsumed_classes")
        if not isinstance(unconsumed, list):
            raise ConsumeError("missing:unconsumed_classes")
        for i, row in enumerate(classes):
            if not isinstance(row, dict) or not row.get("class_id"):
                raise ConsumeError(f"classes[{i}].class_id-missing")
            finding = row.get("finding")
            exit_code = row.get("exit_code")
            if finding in ("unconsumed", "no-produced-sample"):
                if exit_code is not None:
                    raise ConsumeError(f"classes[{i}].{finding}-has-exit-code")
            elif exit_code is None:
                raise ConsumeError(f"classes[{i}].missing-exit-code")
        ctrl = body.get("corruption_control")
        if not isinstance(ctrl, dict) or ctrl.get("failed") is not True:
            raise ConsumeError("corruption_control.failed-not-true")
        return {
            "fields_read": [
                "unit_id",
                "sentinel",
                "classes",
                "unconsumed_classes",
                "corruption_control",
            ],
            "parsed_record_count": len(classes),
            "unit_id": uid,
        }
    artifacts = doc.get("artifacts")
    classes = doc.get("classes")
    if not isinstance(classes, list) or not classes:
        body = artifact_payload(doc)
        classes = body.get("classes")
    if isinstance(classes, list) and classes:
        n = len(classes)
        fields = ["unit_id", "classes"]
    elif isinstance(artifacts, list) and artifacts:
        n = len(artifacts)
        fields = ["unit_id", "artifacts"]
    else:
        raise ConsumeError("missing-classes-or-artifacts")
    return {
        "fields_read": fields,
        "parsed_record_count": n,
        "unit_id": uid,
    }


def consume_payload_records(doc: Any) -> dict:
    """Requires records[].payload.value — not implied by the class schema."""
    if not isinstance(doc, dict):
        raise ConsumeError("not-an-object")
    _req_str(doc, "unit_id")
    records = doc.get("records")
    if not isinstance(records, list) or not records:
        raise ConsumeError("missing-or-empty:records")
    values: list[Any] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ConsumeError(f"records[{i}]-not-object")
        payload = rec.get("payload")
        if not isinstance(payload, dict) or "value" not in payload:
            raise ConsumeError(f"records[{i}].payload.value-missing")
        values.append(payload["value"])
    return {
        "fields_read": ["unit_id", "records[].payload.value"],
        "parsed_record_count": len(values),
        "values": values,
    }


CONSUMERS: dict[str, Callable[[Any], dict]] = {
    "architecture-review": consume_architecture_review,
    "architecture-dossier": consume_architecture_dossier,
    "migration-plan": consume_migration_plan,
    "receipt": consume_receipt,
    "conformance-report": consume_conformance_report,
    "payload-records": consume_payload_records,
}


def consume_path(class_id: str, path: str | Path) -> dict:
    fn = CONSUMERS.get(class_id)
    if fn is None:
        raise ConsumeError(f"no-consumer-for-class:{class_id}")
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = REPO / resolved
    result = fn(load_doc(resolved))
    result["class_id"] = class_id
    result["path"] = resolved.as_posix()
    result["ok"] = True
    return result


def consumer_command(class_id: str, rel_path: str) -> str:
    script = "command-center/p2-wave/probes/CNF-0123/consumers.py"
    return (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        f"{script} --class {class_id} --path {rel_path}"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    class_id = ""
    rel = ""
    i = 0
    while i < len(args):
        if args[i] == "--class" and i + 1 < len(args):
            class_id = args[i + 1]
            i += 2
            continue
        if args[i] == "--path" and i + 1 < len(args):
            rel = args[i + 1]
            i += 2
            continue
        print(f"FAILED:CNF-0123-consumer unknown-arg {args[i]}", file=sys.stderr)
        return 2
    if not class_id or not rel:
        print(
            "FAILED:CNF-0123-consumer usage --class <id> --path <repo-rel>",
            file=sys.stderr,
        )
        return 2
    path = Path(rel)
    if not path.is_absolute():
        path = REPO / rel
    try:
        result = consume_path(class_id, path)
    except ConsumeError as exc:
        print(json.dumps({"ok": False, "class_id": class_id, "error": exc.message}))
        print(f"FAILED:CNF-0123-consumer {class_id} {exc.message}")
        return 1
    print(json.dumps(result, sort_keys=True))
    print(
        f"SUCCESS:CNF-0123-consumer {class_id} records={result['parsed_record_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

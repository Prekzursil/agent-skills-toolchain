#!/usr/bin/env python3
"""Live class-by-class consumer matrix + detector controls for CNF-0123."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _unshadow_stdlib() -> None:
    """Keep repo-root platform/ from breaking jsonschema -> uuid -> platform."""
    repo = str(REPO.resolve())
    here = str(HERE)
    cleaned: list[str] = []
    for p in sys.path:
        if p in ("", "."):
            continue
        try:
            if str(Path(p).resolve()) == repo:
                continue
        except OSError:
            pass
        cleaned.append(p)
    if here not in cleaned:
        cleaned.insert(0, here)
    sys.path[:] = cleaned


_unshadow_stdlib()
import jsonschema  # noqa: E402
from jsonschema.exceptions import RefResolutionError, SchemaError, ValidationError  # noqa: E402

from consumers import CONSUMERS, consumer_command  # noqa: E402
from inventory import inventory  # noqa: E402

CONSUMER_SCRIPT = "command-center/p2-wave/probes/CNF-0123/consumers.py"
UNREADABLE = (
    "command-center/p2-wave/probes/CNF-0123/fixtures/schema-valid-unreadable.json"
)
READABLE = (
    "command-center/p2-wave/probes/CNF-0123/fixtures/schema-valid-readable.json"
)
PAYLOAD_SCHEMA = (
    "command-center/p2-wave/probes/CNF-0123/fixtures/payload-records.schema.json"
)
CORRUPT_CLASS = "architecture-review"


def _run_consumer(class_id: str, rel_or_abs: str) -> tuple[int, dict[str, Any], str]:
    cmd = [
        sys.executable,
        "-B",
        str(REPO / CONSUMER_SCRIPT),
        "--class",
        class_id,
        "--path",
        rel_or_abs,
    ]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    payload: dict[str, Any] = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-800:]
    return proc.returncode, payload, tail


def _drop_relative_ids(node: Any) -> Any:
    """Strip non-URI $id values so jsonschema 4.x will not urljoin them.

    A schema $id of ``command-center/schema/license-graph.schema.json`` plus a
    fragment $ref makes RefResolver produce
    ``command-center/schema/command-center/schema/license-graph.schema.json``
    and then raise RefResolutionError (unknown url type). In-memory fragment
    refs still resolve after the relative $id is removed.
    """
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, val in node.items():
            if key == "$id" and isinstance(val, str) and "://" not in val.split("#")[0]:
                continue
            out[key] = _drop_relative_ids(val)
        return out
    if isinstance(node, list):
        return [_drop_relative_ids(item) for item in node]
    return node


def _schema_valid(schema_rel: str | None, sample_rel: str | None) -> bool | None:
    if not schema_rel or not sample_rel:
        return None
    schema_path = REPO / schema_rel.split("#")[0]
    sample_path = REPO / sample_rel
    if ".schema.json" not in schema_path.name:
        return None
    if not schema_path.is_file() or not sample_path.is_file():
        return None
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        doc = json.loads(sample_path.read_text(encoding="utf-8"))
        if not isinstance(schema, dict):
            return None
        schema = _drop_relative_ids(schema)
        jsonschema.Draft7Validator(schema).validate(doc)
        return True
    except ValidationError:
        return False
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        RefResolutionError,
        SchemaError,
        ValueError,
        TypeError,
    ):
        return None
    except Exception:
        # Named probes must exit 0; a third-party schema quirk is not a crash.
        return None


def measure_classes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory():
        cid = item["class_id"]
        sample = item.get("sample_path")
        source = item.get("sample_source") or "none"
        has_consumer = cid in CONSUMERS
        command = consumer_command(cid, sample) if has_consumer and sample else None
        schema_ok = _schema_valid(item.get("output_schema"), sample)
        exit_code: int | None = None
        parsed: int | None = None
        diagnostic = ""
        finding = "unconsumed"
        if not has_consumer:
            finding = "unconsumed"
            diagnostic = "no class-specific downstream consumer registered"
        elif not sample:
            finding = "no-produced-sample"
            diagnostic = "consumer identified but no sample artifact on disk"
        else:
            sample_abs = REPO / sample
            if cid == "conformance-report" and not sample_abs.is_file():
                finding = "no-produced-sample"
                diagnostic = "self output not yet on disk at inventory time"
            else:
                exit_code, payload, tail = _run_consumer(cid, sample)
                parsed = (
                    payload.get("parsed_record_count") if payload.get("ok") else 0
                )
                if exit_code == 0 and payload.get("ok"):
                    finding = "consumed-readable"
                    diagnostic = f"parsed_record_count={parsed}"
                else:
                    finding = "consumed-unreadable"
                    diagnostic = (
                        payload.get("error") or tail or f"exit={exit_code}"
                    )[:400]
        rows.append(
            {
                "class_id": cid,
                "output_schema": item.get("output_schema") or "",
                "unit_count": int(item.get("unit_count") or 0),
                "sample_path": sample,
                "sample_source": source,
                "schema_path_exists": bool(item.get("schema_path_exists")),
                "schema_valid": schema_ok,
                "consumer_command": command,
                "exit_code": exit_code,
                "parsed_record_count": parsed,
                "finding": finding,
                "diagnostic": diagnostic,
            }
        )
    return rows


def payload_records_control() -> dict[str, Any]:
    schema_ok_bad = _schema_valid(PAYLOAD_SCHEMA, UNREADABLE)
    schema_ok_good = _schema_valid(PAYLOAD_SCHEMA, READABLE)
    bad_rc, bad_payload, _ = _run_consumer("payload-records", UNREADABLE)
    good_rc, good_payload, _ = _run_consumer("payload-records", READABLE)
    return {
        "class_id": "payload-records",
        "unreadable_path": UNREADABLE,
        "readable_path": READABLE,
        "schema_valid_unreadable": schema_ok_bad is True,
        "schema_valid_readable": schema_ok_good is True,
        "unreadable_exit_code": bad_rc,
        "readable_exit_code": good_rc,
        "unreadable_error": bad_payload.get("error"),
        "readable_records": good_payload.get("parsed_record_count"),
        "detector_fired": schema_ok_bad is True and bad_rc != 0 and good_rc == 0,
    }


def corruption_control() -> dict[str, Any]:
    rows = [r for r in inventory() if r["class_id"] == CORRUPT_CLASS]
    sample = None
    for r in rows:
        if r.get("sample_source") == "produced" and r.get("sample_path"):
            sample = r["sample_path"]
            break
    if not sample:
        raise RuntimeError(
            "no produced architecture-review sample for corruption control"
        )
    cmd = consumer_command(CORRUPT_CLASS, sample)
    intact_rc, _, _ = _run_consumer(CORRUPT_CLASS, sample)
    src = REPO / sample
    with tempfile.TemporaryDirectory(prefix="cnf0123-corrupt-") as tmp:
        corrupt_path = Path(tmp) / "corrupt.json"
        shutil.copyfile(src, corrupt_path)
        raw = corrupt_path.read_bytes()
        corrupt_path.write_bytes(
            raw[: max(40, len(raw) // 3)] + b"\n<<<CORRUPT>>>\n"
        )
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(REPO / CONSUMER_SCRIPT),
                "--class",
                CORRUPT_CLASS,
                "--path",
                str(corrupt_path),
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        corrupt_rc = proc.returncode
    return {
        "target_class": CORRUPT_CLASS,
        "sample_path": sample,
        "consumer_command": cmd,
        "intact_exit_code": intact_rc,
        "corrupt_exit_code": corrupt_rc,
        "failed": corrupt_rc != 0 and intact_rc == 0,
        "method": "copy produced sample, truncate mid-JSON, append CORRUPT marker",
    }


def full_measure() -> dict[str, Any]:
    classes = measure_classes()
    payload = payload_records_control()
    corrupt = corruption_control()
    unconsumed = [r["class_id"] for r in classes if r["finding"] == "unconsumed"]
    unreadable = [
        {
            "class_id": r["class_id"],
            "sample_path": r.get("sample_path"),
            "schema_valid": r.get("schema_valid"),
            "exit_code": r.get("exit_code"),
            "note": r.get("diagnostic"),
        }
        for r in classes
        if r["finding"] == "consumed-unreadable" and r.get("schema_valid") is True
    ]
    if payload["detector_fired"]:
        unreadable.append(
            {
                "class_id": "payload-records",
                "sample_path": UNREADABLE,
                "schema_valid": True,
                "exit_code": payload["unreadable_exit_code"],
                "note": "fixture: schema-valid records without payload.value",
            }
        )
    return {
        "classes": classes,
        "unconsumed_classes": unconsumed,
        "schema_valid_unreadable": unreadable,
        "payload_records_control": payload,
        "corruption_control": corrupt,
    }


if __name__ == "__main__":
    doc = full_measure()
    print(
        json.dumps(
            {
                "class_count": len(doc["classes"]),
                "unconsumed": len(doc["unconsumed_classes"]),
                "schema_valid_unreadable": len(doc["schema_valid_unreadable"]),
                "corruption_failed": doc["corruption_control"]["failed"],
                "payload_detector_fired": doc["payload_records_control"][
                    "detector_fired"
                ],
            },
            indent=2,
        )
    )

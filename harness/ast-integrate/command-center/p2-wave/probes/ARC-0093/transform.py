#!/usr/bin/env python3
"""Executable migration engine for ARC-0093.

A versioned JSON object written under version N is either still valid under
N+1, or it is transformed by a declared step list. Records the engine cannot
transform are QUARANTINED and REPORTED. They are never silently dropped.

Canonical byte domain (canonical-json-v1): UTF-8, sort_keys=True, indent=2,
ensure_ascii=True, trailing newline, LF. Round-trip identity is measured in
that encoding, not in the source file's incidental whitespace.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

TRANSFORMED = "TRANSFORMED"
QUARANTINED = "QUARANTINED"

FROM_VERSION = 1
TO_VERSION = 2
FORMAT_FAMILY = "ast-integrate-json-v2"
CANONICAL_ENCODING = "canonical-json-v1"

FORWARD_STEPS: list[dict[str, Any]] = [
    {"op": "set", "path": "schema_version", "value": TO_VERSION},
    {"op": "add", "path": "format_family", "value": FORMAT_FAMILY},
]
REVERSE_STEPS: list[dict[str, Any]] = [
    {"op": "remove", "path": "format_family"},
    {"op": "set", "path": "schema_version", "value": FROM_VERSION},
]

REAL_ARTIFACTS: tuple[str, ...] = (
    "command-center/p2-wave/probes/ARC-0010/registry.json",
    "command-center/p2-wave/probes/ARC-0012/fixtures/complete/registry.json",
    "command-center/p2-wave/probes/ARC-0026/fixtures/index.json",
)


def canonical_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def still_validates_n_plus_1(obj: Any) -> bool:
    """Strict N+1: schema_version must already be TO_VERSION with format_family."""
    return (
        isinstance(obj, dict)
        and obj.get("schema_version") == TO_VERSION
        and obj.get("format_family") == FORMAT_FAMILY
    )


@dataclass
class Outcome:
    status: str
    path: str
    reason: str | None
    original: Any = None
    output: Any = None
    original_canonical_sha256: str | None = None
    output_canonical_sha256: str | None = None
    quarantine_raw: bytes | None = None
    report: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "path": self.path,
            "reason": self.reason,
            "original_canonical_sha256": self.original_canonical_sha256,
            "output_canonical_sha256": self.output_canonical_sha256,
            "quarantine_bytes": (
                len(self.quarantine_raw) if self.quarantine_raw is not None else 0
            ),
            "report": self.report,
        }


def _quarantine(path: str, raw: bytes, reason: str, original: Any = None) -> Outcome:
    report = {
        "action": "QUARANTINE",
        "path": path,
        "reason": reason,
        "silent_drop": False,
        "original_sha256": sha256_bytes(raw),
        "original_bytes": len(raw),
    }
    original_sha = None
    if original is not None and isinstance(original, dict):
        original_sha = sha256_bytes(canonical_bytes(original))
    return Outcome(
        status=QUARANTINED,
        path=path,
        reason=reason,
        original=original,
        original_canonical_sha256=original_sha,
        quarantine_raw=raw,
        report=report,
    )


def _apply_steps(obj: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any] | str:
    """Return a new object, or a reason string if a step cannot run."""
    out = copy.deepcopy(obj)
    for i, step in enumerate(steps):
        op = step.get("op")
        path = step.get("path")
        if not isinstance(op, str) or not isinstance(path, str) or not path:
            return f"malformed-step:{i}"
        if "/" in path or path.startswith("#"):
            return f"nested-path-unsupported:{path}"
        if op == "set":
            if path not in out:
                return f"set-missing:{path}"
            out[path] = copy.deepcopy(step.get("value"))
        elif op == "add":
            if path in out:
                return f"add-exists:{path}"
            out[path] = copy.deepcopy(step.get("value"))
        elif op == "remove":
            if path not in out:
                return f"remove-missing:{path}"
            del out[path]
        else:
            return f"unknown-op:{op}"
    return out


def apply_obj(
    obj: Any,
    *,
    path: str = "<memory>",
    steps: list[dict[str, Any]] | None = None,
    from_version: int = FROM_VERSION,
    source_raw: bytes | None = None,
) -> Outcome:
    if source_raw is not None:
        raw = source_raw
    elif isinstance(obj, dict):
        raw = canonical_bytes(obj)
    else:
        raw = json.dumps(obj).encode("utf-8")
    if not isinstance(obj, dict):
        return _quarantine(path, raw, "not-an-object", original=obj)
    if "schema_version" not in obj:
        return _quarantine(path, raw, "schema_version-absent", original=obj)
    if obj.get("schema_version") != from_version:
        return _quarantine(
            path,
            raw,
            f"schema_version-mismatch:have={obj.get('schema_version')}:want={from_version}",
            original=obj,
        )
    applied = _apply_steps(obj, steps if steps is not None else FORWARD_STEPS)
    if isinstance(applied, str):
        return _quarantine(path, raw, f"transform-failed:{applied}", original=obj)
    out_raw = canonical_bytes(applied)
    return Outcome(
        status=TRANSFORMED,
        path=path,
        reason=None,
        original=copy.deepcopy(obj),
        output=applied,
        original_canonical_sha256=sha256_bytes(canonical_bytes(obj)),
        output_canonical_sha256=sha256_bytes(out_raw),
        report={
            "action": "TRANSFORM",
            "path": path,
            "from_version": from_version,
            "to_version": applied.get("schema_version"),
            "silent_drop": False,
        },
    )


def apply_bytes(
    raw: bytes,
    *,
    path: str = "<bytes>",
    steps: list[dict[str, Any]] | None = None,
    from_version: int = FROM_VERSION,
) -> Outcome:
    try:
        text = raw.decode("utf-8")
        obj = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _quarantine(path, raw, f"unparseable:{type(exc).__name__}")
    if not isinstance(obj, dict):
        return _quarantine(path, raw, "not-an-object", original=obj)
    return apply_obj(
        obj, path=path, steps=steps, from_version=from_version, source_raw=raw
    )


def reverse_obj(obj: Any, *, path: str = "<memory>") -> Outcome:
    return apply_obj(obj, path=path, steps=REVERSE_STEPS, from_version=TO_VERSION)


def round_trip(obj: Any, *, path: str = "<memory>") -> dict[str, Any]:
    fwd = apply_obj(obj, path=path)
    if fwd.status != TRANSFORMED:
        return {
            "path": path,
            "pass": False,
            "byte_recovered": False,
            "forward": fwd.as_dict(),
        }
    rev = reverse_obj(fwd.output, path=path)
    if rev.status != TRANSFORMED:
        return {
            "path": path,
            "pass": False,
            "byte_recovered": False,
            "forward": fwd.as_dict(),
            "reverse": rev.as_dict(),
        }
    original_c = canonical_bytes(obj)
    recovered_c = canonical_bytes(rev.output)
    recovered = original_c == recovered_c
    return {
        "path": path,
        "pass": recovered,
        "byte_recovered": recovered,
        "original_canonical_sha256": sha256_bytes(original_c),
        "forward_canonical_sha256": fwd.output_canonical_sha256,
        "recovered_canonical_sha256": sha256_bytes(recovered_c),
        "n_plus_1_valid_before": still_validates_n_plus_1(obj),
        "n_plus_1_valid_after": still_validates_n_plus_1(fwd.output),
        "forward": fwd.as_dict(),
        "reverse": rev.as_dict(),
    }


def process_many(
    records: list[tuple[str, bytes]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Process a batch. Accounting identity: in == transformed + quarantined.

    dry_run still executes the transform in memory; it does not write. A
    migration that never ran this function must record dry_run.executed=false
    and evidence NOT-CHECKED.
    """
    outcomes: list[Outcome] = []
    for path, raw in records:
        outcomes.append(apply_bytes(raw, path=path))
    transformed = [o for o in outcomes if o.status == TRANSFORMED]
    quarantined = [o for o in outcomes if o.status == QUARANTINED]
    dropped = len(records) - len(outcomes)
    return {
        "executed": True,
        "dry_run": dry_run,
        "records_in": len(records),
        "would_transform": len(transformed),
        "would_quarantine": len(quarantined),
        "would_drop": dropped,
        "transformed": len(transformed),
        "quarantined": len(quarantined),
        "dropped": dropped,
        "accounting_holds": dropped == 0 and len(transformed) + len(quarantined) == len(records),
        "outcomes": [o.as_dict() for o in outcomes],
        "quarantine_reports": [o.report for o in quarantined],
    }


def reversible_statement() -> str:
    return (
        "A migration is REVERSIBLE when every forward step has a declared inverse, "
        "no step is lossy (remove without a prior copy is irreversible unless the "
        "migration is explicitly declared IRREVERSIBLE), and "
        "canonical-json-v1(reverse(forward(doc))) equals canonical-json-v1(doc) "
        "for every TRANSFORMED record. This record's forward set/add pair inverts "
        "by remove/set and is therefore REVERSIBLE."
    )


def migration_record_instance(*, dry_run: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "from_version": FROM_VERSION,
        "to_version": TO_VERSION,
        "transform": {
            "id": "schema_version-1-to-2-format_family",
            "engine": "command-center/p2-wave/probes/ARC-0093/transform.py",
            "encoding": CANONICAL_ENCODING,
            "steps": FORWARD_STEPS,
        },
        "reversibility": {
            "status": "REVERSIBLE",
            "statement": reversible_statement(),
            "byte_recovery_encoding": CANONICAL_ENCODING,
            "reverse_steps": REVERSE_STEPS,
        },
        "dry_run": {
            "executed": bool(dry_run.get("executed")),
            "records_in": int(dry_run.get("records_in") or 0),
            "would_transform": int(dry_run.get("would_transform") or 0),
            "would_quarantine": int(dry_run.get("would_quarantine") or 0),
            "would_drop": int(dry_run.get("would_drop") or 0),
            "evidence_status": (
                "CHECKED" if dry_run.get("executed") else "NOT-CHECKED"
            ),
        },
        "forward_compatibility": {
            "rule": (
                "An N+1 reader MUST either accept an N artifact because it still "
                "validates under the N+1 schema, or refuse it and require this "
                "migration record. Silent reinterpretation of N as N+1 is forbidden."
            ),
            "n_still_validates_under_n_plus_1": False,
            "therefore": "mechanically-transformable",
        },
        "backward_compatibility": {
            "rule": (
                "An N reader MUST refuse an N+1 artifact until the declared reverse "
                "runs. Unknown required N+1 fields must not be ignored."
            ),
            "n_plus_1_validates_under_n": False,
            "return_path": "declared-reverse",
        },
        "transformation_obligation": {
            "rule": (
                "An artifact written under version N must either still validate "
                "under version N+1 or be mechanically transformable to it. If "
                "neither holds, the change is not a version bump; it is a break "
                "and must not ship."
            ),
            "this_pair": "N does not still validate under strict N+1; transform is required and executed",
        },
        "untransformable_policy": {
            "action": "QUARANTINE",
            "report": True,
            "silent_drop": False,
            "rule": (
                "A record the transform cannot handle is copied into quarantine "
                "with original bytes and a reason, and is listed in the dry-run / "
                "apply report. It is never omitted from the accounting identity "
                "records_in == transformed + quarantined."
            ),
        },
        "evidence": evidence,
    }

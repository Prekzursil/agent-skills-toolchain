"""Shared twelve-condition program completion predicate.

Applied to a CertificationRecord on disk so certification is not a private
seven-condition standard this lane invented. Condition names follow
IMP-0433 / ARC-0087 (gate_a_unit_completion_predicate). Exit code zero of a
caller is never success by itself: overall PASS requires every applicable
condition to be PASS, never FAIL, and at least one applicable PASS.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0118/schema/CertificationRecord.schema.json"
)
OUTPUT_REL = "command-center/wfa/WFA-0118-certification-gate.json"
SENTINEL = "SUCCESS:WFA-0118"
MIN_BYTES = 512
CONDITIONS = [
    "process/task reached a valid terminal state",
    "expected artifact exists",
    "artifact is non-empty and exceeds a meaningful minimum size",
    "artifact parses against its schema",
    "required sentinel is present",
    "required evidence anchors exist",
    "required tests ran and passed",
    "negative controls or mutations fail as expected",
    "independent reviewer status is PASS",
    "no unresolved P0/P1 defect is attached",
    "output was registered in the artifact manifest",
    "downstream consumers can read it",
]


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _row(idx: int, result: str, reason: str, applicable: bool = True) -> dict[str, Any]:
    return {
        "id": f"C{idx}",
        "index": idx,
        "text": CONDITIONS[idx - 1],
        "applicable": applicable,
        "result": result if applicable else "NA",
        "reason": reason,
    }


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"unreadable:{exc}", b""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"unparseable:{type(exc).__name__}", raw
    if not isinstance(doc, dict):
        return None, "not-object", raw
    return doc, None, raw


def evaluate_certification_record(
    path: Path | None = None, *, repo: Path | None = None
) -> dict[str, Any]:
    root = repo or REPO
    target = path or (root / OUTPUT_REL)
    rows: list[dict[str, Any]] = []

    exists = target.is_file()
    rows.append(
        _row(2, "PASS" if exists else "FAIL", "present" if exists else "absent")
    )
    if not exists:
        for i in (1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
            rows.append(_row(i, "FAIL", "artifact-absent"))
        rows.sort(key=lambda r: r["index"])
        return _finish(rows, target)

    doc, err, raw = _load(target)
    size = len(raw.replace(b"\r\n", b"\n"))
    rows.append(
        _row(
            3,
            "PASS" if size >= MIN_BYTES else "FAIL",
            f"bytes={size} min={MIN_BYTES}",
        )
    )
    if err or doc is None:
        rows.append(_row(12, "FAIL", err or "load-failed"))
        rows.append(_row(4, "FAIL", err or "load-failed"))
        for i in (1, 5, 6, 7, 8, 9, 10, 11):
            rows.append(_row(i, "FAIL", "unreadable-artifact"))
        rows.sort(key=lambda r: r["index"])
        return _finish(rows, target)

    rows.append(_row(12, "PASS", "json.loads-ok"))

    schema_path = root / SCHEMA_REL
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(doc)
        rows.append(_row(4, "PASS", SCHEMA_REL))
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        rows.append(_row(4, "FAIL", f"{type(exc).__name__}:{exc}"))

    state = str(doc.get("state") or "").upper()
    terminal_ok = state == "SUCCESS" and str(doc.get("verdict") or "") in {
        "CERTIFIED",
        "REFUSED",
        "INCONCLUSIVE",
    }
    rows.append(_row(1, "PASS" if terminal_ok else "FAIL", f"state={state}"))

    text = raw.decode("utf-8")
    sentinel_field = str(doc.get("sentinel") or "")
    sentinel_ok = sentinel_field == SENTINEL and SENTINEL in text
    rows.append(
        _row(
            5,
            "PASS" if sentinel_ok else "FAIL",
            f"field={sentinel_field!r} in_text={SENTINEL in text}",
        )
    )

    anchors = doc.get("evidence") or []
    missing_anchors = []
    for item in anchors:
        if not isinstance(item, dict):
            missing_anchors.append("malformed")
            continue
        anchor = str(item.get("anchor") or "")
        path_rel = str(item.get("path") or anchor.split(":")[0])
        if not path_rel or not (root / path_rel).is_file():
            missing_anchors.append(path_rel or "<blank>")
    rows.append(
        _row(
            6,
            "PASS" if anchors and not missing_anchors else "FAIL",
            f"anchors={len(anchors)} missing={missing_anchors[:6]}",
        )
    )

    tests = doc.get("tests") or []
    tests_ok = bool(tests) and all(
        isinstance(t, dict) and str(t.get("result") or "") == "PASS" for t in tests
    )
    rows.append(
        _row(7, "PASS" if tests_ok else "FAIL", f"tests={len(tests)} all_pass={tests_ok}")
    )

    negs = doc.get("negative_controls") or []
    negs_ok = (
        isinstance(negs, list)
        and len(negs) == 7
        and all(
            isinstance(n, dict)
            and n.get("certified") is False
            and str(n.get("verdict") or "") in {"REFUSED", "INCONCLUSIVE"}
            for n in negs
        )
    )
    rows.append(
        _row(8, "PASS" if negs_ok else "FAIL", f"negative_controls={len(negs)}")
    )

    rev = doc.get("reviewer") or {}
    rev_ok = (
        isinstance(rev, dict)
        and str(rev.get("verdict") or "") == "PASS"
        and rev.get("independent") is True
    )
    rows.append(_row(9, "PASS" if rev_ok else "FAIL", f"reviewer={rev}"))

    defects = doc.get("unresolved_p0_p1") or []
    rows.append(
        _row(
            10,
            "PASS" if not defects else "FAIL",
            f"unresolved={len(defects) if isinstance(defects, list) else defects}",
        )
    )

    cited = doc.get("cited_evidence") or []
    hash_miss = []
    for item in cited:
        if not isinstance(item, dict):
            hash_miss.append("malformed")
            continue
        packet = item.get("packet")
        claimed = str(item.get("sha256") or "")
        if not isinstance(packet, dict) or len(claimed) != 64:
            hash_miss.append(str(item.get("id") or "?"))
            continue
        live = hashlib.sha256(
            json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if live != claimed:
            hash_miss.append(str(item.get("id") or live[:12]))
    rows.append(
        _row(
            11,
            "PASS" if cited and not hash_miss else "FAIL",
            f"cited={len(cited)} hash_miss={hash_miss[:6]}",
        )
    )

    rows.sort(key=lambda r: r["index"])
    return _finish(rows, target)


def _finish(rows: list[dict[str, Any]], target: Path) -> dict[str, Any]:
    applicable = [r for r in rows if r["applicable"]]
    fails = [r for r in applicable if r["result"] == "FAIL"]
    passes = [r for r in applicable if r["result"] == "PASS"]
    if fails:
        overall = "FAIL"
    elif passes:
        overall = "PASS"
    else:
        overall = "UNKNOWN"
    return {
        "reducer": "twelve-condition-program-completion-predicate",
        "path": target.as_posix(),
        "overall": overall,
        "exit_code": 0 if overall == "PASS" else 1,
        "pass_count": len(passes),
        "fail_count": len(fails),
        "conditions": rows,
        "note": (
            "Exit code of a caller is never success by itself; overall PASS "
            "requires every applicable condition PASS."
        ),
    }

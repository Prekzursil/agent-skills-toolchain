#!/usr/bin/env python3
"""Production fan-in reducer: sequential short-circuit over the 12 conditions.

This is the runner-side completion predicate used at fan-in. Exit code zero is
never success. A digest string is not a receipt. A path in text is not proof
the file exists. First failing condition id is returned; PASS only if all 12
hold.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spec import (
    BLOCKING_SEVERITIES,
    CONDITION_IDS,
    OPEN_DEFECT_STATUSES,
    TERMINAL_STATES,
)

PASS = "PASS"
FAIL = "FAIL"


def _fail(cid: str, reason: str) -> dict[str, Any]:
    return {
        "verdict": FAIL,
        "failing_condition_id": cid,
        "reason": reason,
        "evaluator": "runner-fanin",
    }


def _pass() -> dict[str, Any]:
    return {
        "verdict": PASS,
        "failing_condition_id": None,
        "reason": "all 12 conditions held",
        "evaluator": "runner-fanin",
    }


def evaluate_receipt(receipt: Any, repo: Path) -> dict[str, Any]:
    """Fan-in: walk C1..C12 and return on the first failure."""
    if not isinstance(receipt, dict):
        return _fail("C1", "receipt is not an object; no valid terminal state")

    state = receipt.get("state")
    if not isinstance(state, str) or state not in TERMINAL_STATES:
        return _fail("C1", f"state {state!r} is not a valid terminal")

    # C2: live existence. Exit 0 and a quoted digest do not substitute.
    art_rel = receipt.get("artifact_path")
    digest = receipt.get("sha256")
    if not isinstance(art_rel, str) or not art_rel.strip():
        extra = f" digest={digest!r}" if isinstance(digest, str) and digest else ""
        return _fail("C2", "artifact_path missing; a digest is not a receipt" + extra)
    art_path = repo / art_rel.replace("\\", "/")
    if not art_path.is_file():
        exit_code = receipt.get("process_exit_code")
        return _fail(
            "C2",
            f"artifact absent on disk at {art_rel}; process_exit_code={exit_code!r} "
            "is never success by itself",
        )

    # C3: size floor must be a positive int or the check is unfalsifiable.
    floor = receipt.get("min_bytes_threshold")
    if not isinstance(floor, int) or isinstance(floor, bool) or floor < 1:
        return _fail("C3", f"min_bytes_threshold {floor!r} is not a positive int")
    try:
        nbytes = art_path.stat().st_size
    except OSError as exc:
        return _fail("C3", f"stat failed: {exc}")
    if nbytes < 1:
        return _fail("C3", "artifact is empty")
    if nbytes < floor:
        return _fail("C3", f"artifact {nbytes}B below min_bytes_threshold {floor}")

    # C4: parse the file; required keys from the declared schema.
    try:
        raw = art_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _fail("C4", f"artifact does not parse as JSON: {type(exc).__name__}")
    if not isinstance(parsed, dict):
        return _fail("C4", f"artifact JSON is {type(parsed).__name__}, not an object")
    schema_rel = receipt.get("schema_path")
    if not isinstance(schema_rel, str) or not schema_rel.strip():
        return _fail("C4", "schema_path missing; cannot parse against a schema")
    schema_path = repo / schema_rel.replace("\\", "/")
    if not schema_path.is_file():
        return _fail("C4", f"schema file absent {schema_rel}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _fail("C4", f"schema unreadable: {type(exc).__name__}")
    required = schema.get("required") if isinstance(schema, dict) else None
    if not isinstance(required, list) or not required:
        return _fail("C4", "schema has no required key list")
    missing = [k for k in required if not isinstance(k, str) or k not in parsed]
    if missing:
        return _fail("C4", f"schema required keys missing: {missing}")

    # C5: sentinel is the artifact field, not a substring mention in prose.
    want = receipt.get("required_sentinel")
    if not isinstance(want, str) or not want.strip():
        return _fail("C5", "required_sentinel missing on the receipt")
    got = parsed.get("sentinel")
    if got != want:
        return _fail("C5", f"artifact sentinel {got!r} != required {want!r}")

    # C6: two evidence rows with two distinct probe fingerprints.
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return _fail("C6", "need at least two evidence anchors")
    fingerprints: list[str] = []
    for item in evidence:
        if not isinstance(item, dict) or not str(item.get("claim") or "").strip():
            return _fail("C6", "evidence item missing claim")
        probes = item.get("probes")
        if not isinstance(probes, list) or not probes:
            return _fail("C6", "evidence item has no probes")
        for probe in probes:
            if not isinstance(probe, dict):
                return _fail("C6", "probe is not an object")
            fp = probe.get("fingerprint")
            if not isinstance(fp, str) or not fp.strip():
                return _fail("C6", "probe fingerprint missing")
            fingerprints.append(fp)
    if len(set(fingerprints)) < 2:
        return _fail("C6", "evidence probes share one fingerprint (same-probe-rerun)")

    # C7
    tests = receipt.get("tests")
    if not isinstance(tests, list) or not tests:
        return _fail("C7", "tests list empty or missing")
    for test in tests:
        if not isinstance(test, dict) or test.get("result") != "PASS":
            return _fail("C7", f"test did not PASS: {test!r}")

    # C8
    controls = receipt.get("negative_controls")
    if not isinstance(controls, list) or not controls:
        return _fail("C8", "negative_controls missing")
    for ctl in controls:
        if not isinstance(ctl, dict):
            return _fail("C8", "control is not an object")
        if ctl.get("fired_on_bad_state") is not True:
            return _fail("C8", "control did not fire on the known-broken state")
        if ctl.get("silent_on_good_state") is not True:
            return _fail("C8", "control is not silent on the good state")

    # C9
    reviewer = receipt.get("reviewer")
    if not isinstance(reviewer, dict):
        return _fail("C9", "reviewer record missing")
    rid = reviewer.get("reviewer_id")
    if not isinstance(rid, str) or not rid.strip():
        return _fail("C9", "reviewer_id missing")
    if reviewer.get("verdict") != "PASS":
        return _fail("C9", f"reviewer verdict {reviewer.get('verdict')!r} is not PASS")
    if reviewer.get("independent") is not True:
        return _fail("C9", "reviewer is not independent")

    # C10
    defects = receipt.get("defects")
    if defects is None:
        defects = []
    if not isinstance(defects, list):
        return _fail("C10", "defects is not a list")
    for defect in defects:
        if not isinstance(defect, dict):
            return _fail("C10", "defect is not an object")
        sev = str(defect.get("severity") or "")
        st = str(defect.get("status") or "")
        if sev in BLOCKING_SEVERITIES and st in OPEN_DEFECT_STATUSES:
            return _fail("C10", f"unresolved {sev} defect {defect.get('id')}")

    # C11: open the named manifest; a boolean flag is not registration.
    man_rel = receipt.get("manifest_path")
    if not isinstance(man_rel, str) or not man_rel.strip():
        return _fail("C11", "manifest_path missing")
    man_path = repo / man_rel.replace("\\", "/")
    if not man_path.is_file():
        return _fail("C11", f"manifest file absent {man_rel}")
    try:
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _fail("C11", f"manifest unreadable: {type(exc).__name__}")
    rows = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(rows, list):
        return _fail("C11", "manifest has no artifacts list")
    want_path = art_rel.replace("\\", "/")
    hit = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "").replace("\\", "/")
        if path == want_path and row.get("present") is True:
            hit = True
            break
    if not hit:
        return _fail("C11", f"no present=true row for {want_path}")

    # C12: a consumer that was not executed is decorative.
    consumers = receipt.get("downstream_consumers")
    if not isinstance(consumers, list) or not consumers:
        return _fail("C12", "downstream_consumers missing")
    readable = False
    for cons in consumers:
        if not isinstance(cons, dict):
            continue
        if cons.get("executed") is True and cons.get("read_ok") is True:
            readable = True
            break
    if not readable:
        return _fail("C12", "no downstream consumer both executed and read_ok")

    # Keep CONDITION_IDS referenced so a truncated reducer is obvious.
    assert len(CONDITION_IDS) == 12
    return _pass()

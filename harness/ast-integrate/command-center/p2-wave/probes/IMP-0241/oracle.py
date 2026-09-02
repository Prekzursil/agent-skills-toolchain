#!/usr/bin/env python3
"""Shared completion predicate (IMP-0226 / CC-0003 surface used by IMP-0241).

`judge` is the ONE reducer go/no-go may call. Exit code zero alone is
structurally incapable of returning COMPLETE: condition 2 reads the artifact
on disk, and COMPLETE requires every applicable condition TRUE.
NOT-CHECKED blocks as hard as FALSE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONDITION_SPECS: tuple[dict[str, str], ...] = (
    {"id": "c1", "text": "process/task reached a valid terminal state"},
    {"id": "c2", "text": "expected artifact exists"},
    {"id": "c3", "text": "artifact is non-empty and exceeds a meaningful minimum size"},
    {"id": "c4", "text": "artifact parses against its schema"},
    {"id": "c5", "text": "required sentinel is present"},
    {"id": "c6", "text": "required evidence anchors exist"},
    {"id": "c7", "text": "required tests ran and passed"},
    {"id": "c8", "text": "negative controls or mutations fail as expected"},
    {"id": "c9", "text": "independent reviewer status is PASS"},
    {"id": "c10", "text": "no unresolved P0/P1 defect is attached"},
    {"id": "c11", "text": "output was registered in the artifact manifest"},
    {"id": "c12", "text": "downstream consumers can read it"},
)

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT", "INCOMPLETE"})
MIN_BYTES = 128


def _row(cid: str, outcome: str, basis: str) -> dict[str, str]:
    return {"id": cid, "outcome": outcome, "basis": basis}


def _artifact_path(evidence: dict[str, Any]) -> Path | None:
    raw = evidence.get("artifact_path") or evidence.get("output_path")
    if not raw or not isinstance(raw, str):
        return None
    path = Path(raw)
    repo = evidence.get("repo")
    if not path.is_absolute() and repo:
        path = Path(repo) / raw
    return path


def _eval_c1(evidence: dict[str, Any]) -> dict[str, str]:
    state = str(evidence.get("state") or evidence.get("terminal_state") or "").upper()
    if not state:
        return _row("c1", "NOT-CHECKED", "no terminal state supplied")
    if state in NOT_DELIVERING:
        return _row("c1", "FALSE", f"state={state} is terminal but not a completion")
    if state in {"SUCCESS", "DELIVERED", "COMPLETE", "GO"}:
        return _row("c1", "TRUE", f"state={state}")
    return _row("c1", "FALSE", f"state={state} is not a valid completion terminal")


def _eval_c2(evidence: dict[str, Any]) -> dict[str, str]:
    path = _artifact_path(evidence)
    if path is None:
        return _row("c2", "NOT-CHECKED", "no artifact_path in evidence")
    if path.is_file():
        return _row("c2", "TRUE", f"artifact exists path={path.as_posix()}")
    return _row("c2", "FALSE", f"artifact missing path={path.as_posix()}")


def _eval_c3(evidence: dict[str, Any]) -> dict[str, str]:
    path = _artifact_path(evidence)
    if path is None or not path.is_file():
        return _row("c3", "FALSE", "artifact missing; size cannot be measured")
    size = path.stat().st_size
    floor = int(evidence.get("min_bytes_threshold") or MIN_BYTES)
    if size >= floor:
        return _row("c3", "TRUE", f"bytes={size} floor={floor}")
    return _row("c3", "FALSE", f"bytes={size} below floor={floor}")


def _eval_c4(evidence: dict[str, Any]) -> dict[str, str]:
    path = _artifact_path(evidence)
    if path is None or not path.is_file():
        return _row("c4", "FALSE", "artifact missing; cannot parse")
    try:
        text = path.read_text(encoding="utf-8")
        json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _row("c4", "FALSE", f"unparseable:{type(exc).__name__}")
    return _row("c4", "TRUE", "artifact parses as JSON")


def _eval_c5(evidence: dict[str, Any]) -> dict[str, str]:
    sentinel = evidence.get("expected_sentinel")
    path = _artifact_path(evidence)
    if not sentinel:
        return _row("c5", "NOT-CHECKED", "no expected_sentinel")
    if path is None or not path.is_file():
        return _row("c5", "FALSE", "artifact missing; sentinel cannot be read")
    text = path.read_text(encoding="utf-8")
    if str(sentinel) in text:
        return _row("c5", "TRUE", f"sentinel present:{sentinel}")
    return _row("c5", "FALSE", "sentinel-absent")


def _eval_c6(evidence: dict[str, Any]) -> dict[str, str]:
    items = evidence.get("evidence")
    if not isinstance(items, list) or not items:
        return _row("c6", "NOT-CHECKED", "no evidence anchors supplied")
    anchored = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        probes = item.get("probes") or []
        roles = {str(p.get("role")) for p in probes if isinstance(p, dict)}
        if item.get("anchor") and "source" in roles and "verifier" in roles:
            anchored += 1
    if anchored >= 1:
        return _row("c6", "TRUE", f"{anchored} source/verifier-paired anchor(s)")
    return _row("c6", "FALSE", "anchors lack independent source/verifier pair")


def _eval_c7(evidence: dict[str, Any]) -> dict[str, str]:
    tests = evidence.get("tests")
    if not isinstance(tests, list) or not tests:
        return _row("c7", "NOT-CHECKED", "no tests recorded")
    failed = [t for t in tests if isinstance(t, dict) and str(t.get("result") or "").upper() != "PASS"]
    if failed:
        return _row("c7", "FALSE", f"{len(failed)} test(s) not PASS")
    return _row("c7", "TRUE", f"{len(tests)} test(s) PASS")


def _eval_c8(evidence: dict[str, Any]) -> dict[str, str]:
    controls = evidence.get("negative_controls")
    if not isinstance(controls, list) or not controls:
        return _row("c8", "NOT-CHECKED", "no negative controls recorded")
    bad = [
        c
        for c in controls
        if isinstance(c, dict)
        and not (c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True)
    ]
    if bad:
        return _row("c8", "FALSE", f"{len(bad)} control(s) did not fire on bad and stay silent on good")
    return _row("c8", "TRUE", f"{len(controls)} both-states control(s)")


def _eval_c9(evidence: dict[str, Any]) -> dict[str, str]:
    rev = evidence.get("reviewer")
    if not isinstance(rev, dict):
        return _row("c9", "NOT-CHECKED", "no reviewer record")
    if rev.get("verdict") == "PASS" and rev.get("independent") is True:
        return _row("c9", "TRUE", f"independent reviewer {rev.get('reviewer_id')} PASS")
    return _row("c9", "FALSE", "reviewer is not independent PASS")


def _eval_c10(evidence: dict[str, Any]) -> dict[str, str]:
    defects = evidence.get("defects")
    if defects is None:
        return _row("c10", "NOT-CHECKED", "defects field absent")
    if not isinstance(defects, list):
        return _row("c10", "FALSE", "defects is not a list")
    open_p = [
        d
        for d in defects
        if isinstance(d, dict)
        and str(d.get("severity") or "").upper() in {"P0", "P1"}
        and str(d.get("status") or "").upper() not in {"CLOSED", "RESOLVED"}
    ]
    if open_p:
        return _row("c10", "FALSE", f"{len(open_p)} open P0/P1 defect(s)")
    return _row("c10", "TRUE", f"{len(defects)} defect(s) recorded, none open at P0/P1")


def _eval_c11(evidence: dict[str, Any]) -> dict[str, str]:
    reg = evidence.get("manifest_registration")
    if not isinstance(reg, dict):
        return _row("c11", "NOT-CHECKED", "manifest_registration absent")
    if reg.get("registered") is True and reg.get("manifest_path"):
        return _row("c11", "TRUE", f"registered at {reg.get('manifest_path')}")
    return _row("c11", "FALSE", "manifest_registration.registered is not true")


def _eval_c12(evidence: dict[str, Any]) -> dict[str, str]:
    consumers = evidence.get("downstream_consumers")
    if not isinstance(consumers, list) or not consumers:
        return _row("c12", "NOT-CHECKED", "no downstream consumers recorded")
    ok = [
        c
        for c in consumers
        if isinstance(c, dict) and c.get("read_ok") is True and c.get("executed") is True
    ]
    if ok:
        return _row("c12", "TRUE", f"{len(ok)} consumer(s) executed and read the artifact")
    return _row("c12", "FALSE", "no consumer executed and read the artifact")


_EVALUATORS = (
    _eval_c1,
    _eval_c2,
    _eval_c3,
    _eval_c4,
    _eval_c5,
    _eval_c6,
    _eval_c7,
    _eval_c8,
    _eval_c9,
    _eval_c10,
    _eval_c11,
    _eval_c12,
)


def judge(evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Typed completion verdict. Never COMPLETE from exit_code alone."""
    ev = dict(evidence or {})
    conditions = [fn(ev) for fn in _EVALUATORS]
    # Anti-pattern 10646: exit code zero is not success. COMPLETE is the
    # conjunction of TRUE rows; c2/c3/c4 read the file, so an exit_code=0
    # envelope with a missing artifact cannot become COMPLETE.
    outcomes = [c["outcome"] for c in conditions]
    blocked = any(o in {"FALSE", "NOT-CHECKED"} for o in outcomes)
    result = "INCOMPLETE" if blocked else "COMPLETE"
    return {
        "result": result,
        "exit_code": ev.get("exit_code"),
        "conditions": conditions,
        "true": outcomes.count("TRUE"),
        "false": outcomes.count("FALSE"),
        "not_checked": outcomes.count("NOT-CHECKED"),
        "reducer": "oracle.judge",
        "anti_patterns": {
            "exit_zero_alone_never_complete": True,
            "digest_without_file_never_receipt": True,
            "path_in_text_is_not_existence": True,
        },
    }

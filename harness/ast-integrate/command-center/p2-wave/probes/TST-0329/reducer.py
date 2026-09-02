"""Twelve-condition completion reducer under test for TST-0329.

CC-0003's production module (platform/lib/completion_predicate.py) is absent
on this worktree. This reducer is the spec-derived 12-condition conjunction
the catalog names as the shared predicate: every applicable condition must
be SATISFIED; exit_code==0 is recorded and never treated as success.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from conditions import (
    ARTIFACT_REL,
    CONDITION_IDS,
    CONDITION_TEXT,
    MIN_BYTES,
    OPEN_BLOCKER,
    SCHEMA_REL,
    SENTINEL,
    SUCCESS_TERMINALS,
    VALID_TERMINALS,
)

UNSAT = "UNSATISFIED"
SAT = "SATISFIED"
NA = "INAPPLICABLE"

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _schema_ok(data: Any, schema: dict[str, Any]) -> bool:
    if schema.get("type") == "object" and not isinstance(data, dict):
        return False
    required = schema.get("required") or []
    if isinstance(data, dict):
        for key in required:
            if key not in data:
                return False
    props = schema.get("properties") or {}
    if not isinstance(data, dict):
        return True
    for key, spec in props.items():
        if key not in data:
            continue
        want = spec.get("type")
        val = data[key]
        if want == "string" and not isinstance(val, str):
            return False
        if want == "object" and not isinstance(val, dict):
            return False
        if want == "array" and not isinstance(val, list):
            return False
        if want == "integer" and type(val) is not int:
            return False
        if "const" in spec and val != spec["const"]:
            return False
        if "enum" in spec and val not in spec["enum"]:
            return False
        if "pattern" in spec and isinstance(val, str):
            if re.search(spec["pattern"], val) is None:
                return False
    if schema.get("additionalProperties") is False:
        extra = set(data) - set(props)
        if extra:
            return False
    return True


def _row(cid: str, result: str, reason: str) -> dict[str, str]:
    return {
        "id": cid,
        "text": CONDITION_TEXT[cid],
        "result": result,
        "reason": reason,
    }


def eval_c1(obs: dict[str, Any], _root: Path) -> dict[str, str]:
    state = str(obs.get("terminal_state") or "").upper()
    if state not in VALID_TERMINALS:
        return _row("C1", UNSAT, f"non-terminal state {state!r}")
    if state not in SUCCESS_TERMINALS:
        return _row("C1", UNSAT, f"terminal but not a success state {state!r}")
    return _row("C1", SAT, f"terminal_state={state}")


def eval_c2(obs: dict[str, Any], root: Path) -> dict[str, str]:
    rel = str(obs.get("artifact_rel") or ARTIFACT_REL)
    path = root / rel
    # Exit code is recorded and must not short-circuit this check.
    exit_code = obs.get("exit_code")
    if not path.is_file():
        return _row(
            "C2",
            UNSAT,
            f"missing {rel} (exit_code={exit_code!r}; zero is never success)",
        )
    return _row("C2", SAT, f"exists {rel} bytes={path.stat().st_size}")


def eval_c3(obs: dict[str, Any], root: Path) -> dict[str, str]:
    rel = str(obs.get("artifact_rel") or ARTIFACT_REL)
    path = root / rel
    floor = int(obs.get("min_bytes") or MIN_BYTES)
    if not path.is_file():
        return _row("C3", NA, "artifact absent; size not judged")
    n = path.stat().st_size
    if n <= 0:
        return _row("C3", UNSAT, "artifact empty")
    if n < floor:
        return _row("C3", UNSAT, f"bytes={n} < min_bytes={floor}")
    return _row("C3", SAT, f"bytes={n} >= {floor}")


def eval_c4(obs: dict[str, Any], root: Path) -> dict[str, str]:
    rel = str(obs.get("artifact_rel") or ARTIFACT_REL)
    schema_rel = str(obs.get("schema_rel") or SCHEMA_REL)
    path = root / rel
    schema_path = root / schema_rel
    if not path.is_file():
        return _row("C4", NA, "artifact absent; schema not judged")
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _row("C4", UNSAT, f"json parse {type(exc).__name__}")
    if not schema_path.is_file():
        return _row("C4", UNSAT, f"schema missing {schema_rel}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _row("C4", UNSAT, f"schema unreadable {type(exc).__name__}")
    if not _schema_ok(data, schema):
        return _row("C4", UNSAT, "schema validation failed")
    return _row("C4", SAT, "json + schema ok")


def eval_c5(obs: dict[str, Any], root: Path) -> dict[str, str]:
    rel = str(obs.get("artifact_rel") or ARTIFACT_REL)
    path = root / rel
    sentinel = str(obs.get("sentinel") or SENTINEL)
    if not path.is_file():
        return _row("C5", NA, "artifact absent; sentinel not judged")
    text = path.read_text(encoding="utf-8", errors="replace")
    if sentinel not in text:
        return _row("C5", UNSAT, f"sentinel {sentinel!r} not in artifact bytes")
    return _row("C5", SAT, "sentinel present in artifact")


def eval_c6(obs: dict[str, Any], root: Path) -> dict[str, str]:
    rels = obs.get("evidence_rels") or []
    if not isinstance(rels, list) or not rels:
        return _row("C6", UNSAT, "no evidence anchors declared")
    missing = [r for r in rels if not (root / str(r)).is_file()]
    if missing:
        return _row("C6", UNSAT, f"missing anchors {missing}")
    return _row("C6", SAT, f"{len(rels)} anchors on disk")


def eval_c7(obs: dict[str, Any], _root: Path) -> dict[str, str]:
    tests = obs.get("tests") or []
    if not isinstance(tests, list) or not tests:
        return _row("C7", UNSAT, "no tests recorded")
    failed = [
        t.get("id")
        for t in tests
        if not isinstance(t, dict) or str(t.get("result") or "").upper() != "PASS"
    ]
    if failed:
        return _row("C7", UNSAT, f"tests not PASS: {failed}")
    return _row("C7", SAT, f"{len(tests)} tests PASS")


def eval_c8(obs: dict[str, Any], _root: Path) -> dict[str, str]:
    controls = obs.get("negative_controls") or []
    if not isinstance(controls, list) or not controls:
        return _row("C8", UNSAT, "no negative controls recorded")
    for c in controls:
        if not isinstance(c, dict):
            return _row("C8", UNSAT, "malformed control")
        if c.get("fired_on_bad") is not True:
            return _row("C8", UNSAT, f"{c.get('id')} silent on bad state")
        if c.get("silent_on_good") is not True:
            return _row("C8", UNSAT, f"{c.get('id')} fired on good state")
    return _row("C8", SAT, f"{len(controls)} controls two-sided")


def eval_c9(obs: dict[str, Any], _root: Path) -> dict[str, str]:
    rev = obs.get("reviewer") or {}
    if not isinstance(rev, dict):
        return _row("C9", UNSAT, "reviewer missing")
    verdict = str(rev.get("verdict") or "").upper()
    if verdict != "PASS":
        return _row("C9", UNSAT, f"reviewer.verdict={verdict!r}")
    if rev.get("independent") is not True:
        return _row("C9", UNSAT, "reviewer is not independent")
    return _row("C9", SAT, "independent reviewer PASS")


def eval_c10(obs: dict[str, Any], _root: Path) -> dict[str, str]:
    defects = obs.get("defects") or []
    if not isinstance(defects, list):
        return _row("C10", UNSAT, "defects field malformed")
    open_blockers = []
    for d in defects:
        if not isinstance(d, dict):
            continue
        sev = str(d.get("severity") or "").upper()
        status = str(d.get("status") or "").lower()
        if sev in OPEN_BLOCKER and status in {"open", "unresolved", "new"}:
            open_blockers.append(d.get("id") or sev)
    if open_blockers:
        return _row("C10", UNSAT, f"open P0/P1 {open_blockers}")
    return _row("C10", SAT, "no open P0/P1")


def eval_c11(obs: dict[str, Any], root: Path) -> dict[str, str]:
    man_rel = str(obs.get("manifest_rel") or "UNIT-ARTIFACT-MANIFEST.json")
    art_rel = str(obs.get("artifact_rel") or ARTIFACT_REL)
    man_path = root / man_rel
    if not man_path.is_file():
        return _row("C11", UNSAT, f"manifest missing {man_rel}")
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _row("C11", UNSAT, f"manifest unparseable {type(exc).__name__}")
    rows = man.get("artifacts") if isinstance(man, dict) else None
    if not isinstance(rows, list):
        return _row("C11", UNSAT, "manifest has no artifacts list")
    match = None
    for row in rows:
        if isinstance(row, dict) and str(row.get("path") or "") == art_rel:
            match = row
            break
    if match is None:
        return _row("C11", UNSAT, f"{art_rel} not registered")
    digest = str(match.get("sha256") or "")
    if not HEX64.match(digest):
        return _row("C11", UNSAT, "registered digest is not sha256 hex")
    live = root / art_rel
    if live.is_file():
        actual = sha256_bytes(live.read_bytes())
        if actual != digest.lower():
            return _row("C11", UNSAT, "manifest sha256 != live artifact")
    return _row("C11", SAT, f"registered {art_rel}")


def eval_c12(obs: dict[str, Any], root: Path) -> dict[str, str]:
    rel = str(obs.get("artifact_rel") or ARTIFACT_REL)
    path = root / rel
    if not path.is_file():
        return _row("C12", NA, "artifact absent; consumer not judged")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _row("C12", UNSAT, f"consumer cannot parse {type(exc).__name__}")
    export = data.get("export") if isinstance(data, dict) else None
    handle = export.get("for_consumer") if isinstance(export, dict) else None
    if not isinstance(handle, str) or not handle.startswith("consumer:"):
        return _row("C12", UNSAT, "downstream handle unreadable")
    if len(handle) < 12:
        return _row("C12", UNSAT, "downstream handle too short")
    return _row("C12", SAT, f"consumer read {handle}")


EVALUATORS = {
    "C1": eval_c1,
    "C2": eval_c2,
    "C3": eval_c3,
    "C4": eval_c4,
    "C5": eval_c5,
    "C6": eval_c6,
    "C7": eval_c7,
    "C8": eval_c8,
    "C9": eval_c9,
    "C10": eval_c10,
    "C11": eval_c11,
    "C12": eval_c12,
}


def evaluate_conditions(
    obs: dict[str, Any],
    root: Path,
    *,
    skip: frozenset[str] | None = None,
) -> list[dict[str, str]]:
    skipped = skip or frozenset()
    rows = []
    for cid in CONDITION_IDS:
        if cid in skipped:
            rows.append(_row(cid, SAT, f"SKIPPED by hole-detector control ({cid})"))
            continue
        rows.append(EVALUATORS[cid](obs, root))
    return rows


def reduce_completion(
    obs: dict[str, Any],
    root: Path,
    *,
    skip: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Conjunction over applicable conditions. Exit 0 never implies complete."""
    conditions = evaluate_conditions(obs, root, skip=skip)
    failing = [c["id"] for c in conditions if c["result"] == UNSAT]
    applicable_pass = [
        c for c in conditions if c["result"] in {SAT, NA}
    ]
    complete = len(failing) == 0 and any(c["result"] == SAT for c in conditions)
    # All-NA would be vacuous; require at least the non-artifact conditions SAT.
    if skip:
        # skipped rows are marked SAT; complete still means no UNSAT
        complete = len(failing) == 0
    return {
        "complete": complete,
        "verdict": "TRUE" if complete else "FALSE",
        "exit_code": obs.get("exit_code"),
        "exit_code_never_success": True,
        "failing_condition_ids": failing,
        "conditions": conditions,
        "applicable_non_fail_count": len(applicable_pass),
        "skipped": sorted(skip) if skip else [],
    }

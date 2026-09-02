#!/usr/bin/env python3
"""Clean-room 12-condition completion predicate.

Written from SPEC-FRAGMENT.txt only. Must not import or read any shipped
reducer module. Exit code, digest strings, and path-in-text are never success.
UNKNOWN is distinct from UNSATISFIED and must not fold into SATISFIED.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "SPEC-FRAGMENT.txt"

SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"
UNKNOWN = "UNKNOWN"
INAPPLICABLE = "INAPPLICABLE"

COMPLETE_STATES = frozenset({"SUCCESS", "COMPLETE", "CONFIRMED", "DELIVERED"})
# Terminal but not a completion. Exit-zero is not in this set and never used.
NONCOMPLETE_TERMINAL = frozenset(
    {"BLOCKED", "FAILED", "TIMEOUT", "SEVERED", "INCOMPLETE", "PARTIAL", "ERROR"}
)
PASS_VERDICTS = frozenset({"PASS", "CONFIRMED", "SUCCESS"})
OPEN_STATUSES = frozenset({"OPEN", "UNRESOLVED", "ACTIVE"})
P0P1 = frozenset({"P0", "P1", "CRITICAL", "HIGH"})
MIN_MEANINGFUL_BYTES = 128
SENTINEL_RE = re.compile(r"^SUCCESS:[A-Z]{2,5}-\d{4}$")

CONDITION_TEXT = {
    1: "process/task reached a valid terminal state",
    2: "expected artifact exists",
    3: "artifact is non-empty and exceeds a meaningful minimum size",
    4: "artifact parses against its schema",
    5: "required sentinel is present",
    6: "required evidence anchors exist",
    7: "required tests ran and passed",
    8: "negative controls or mutations fail as expected",
    9: "independent reviewer status is PASS",
    10: "no unresolved P0/P1 defect is attached",
    11: "output was registered in the artifact manifest",
    12: "downstream consumers can read it",
}


def spec_bytes() -> bytes:
    return SPEC_PATH.read_bytes().replace(b"\r\n", b"\n")


def _row(n: int, outcome: str, basis: str) -> dict[str, Any]:
    return {
        "n": n,
        "id": f"C{n}",
        "text": CONDITION_TEXT[n],
        "outcome": outcome,
        "basis": basis,
    }


def _repo(obs: dict[str, Any]) -> Path:
    root = obs.get("repo")
    return Path(root) if root else HERE.parents[3]


def _rel(repo: Path, rel: str) -> Path:
    return (repo / str(rel).replace("\\", "/")).resolve()


def _artifact_paths(obs: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in obs.get("artifacts") or []:
        if isinstance(item, str) and item.strip():
            out.append(item.replace("\\", "/"))
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            out.append(item["path"].replace("\\", "/"))
    return out


def _c1(obs: dict[str, Any]) -> dict[str, Any]:
    # Exit code is recorded but NEVER consulted as success.
    _ = obs.get("exit_code")
    state = str(obs.get("state") or "").strip().upper()
    if not state:
        return _row(1, UNKNOWN, "state field absent (UNKNOWN, not a pass)")
    if state in COMPLETE_STATES:
        return _row(1, SATISFIED, f"state={state} is a completion terminal")
    if state in NONCOMPLETE_TERMINAL:
        return _row(
            1,
            UNSATISFIED,
            f"state={state} is terminal but not a completion",
        )
    return _row(1, UNKNOWN, f"state={state} is not a known terminal")


def _c2(obs: dict[str, Any]) -> dict[str, Any]:
    repo = _repo(obs)
    paths = _artifact_paths(obs)
    if not paths:
        return _row(
            2,
            UNSATISFIED,
            "no artifact path declared; a digest or path-in-text is not a receipt",
        )
    missing = [p for p in paths if not _rel(repo, p).is_file()]
    if missing:
        return _row(
            2,
            UNSATISFIED,
            f"stat-confirmed absent: {missing[:4]}",
        )
    return _row(2, SATISFIED, f"{len(paths)} artifact(s) exist on disk")


def _c3(obs: dict[str, Any]) -> dict[str, Any]:
    repo = _repo(obs)
    paths = _artifact_paths(obs)
    if not paths:
        return _row(3, UNSATISFIED, "no artifact to size")
    bad: list[str] = []
    for p in paths:
        path = _rel(repo, p)
        if not path.is_file():
            bad.append(f"{p}: absent")
            continue
        n = path.stat().st_size
        if n <= 0 or n < MIN_MEANINGFUL_BYTES:
            bad.append(f"{p}: {n}B < {MIN_MEANINGFUL_BYTES}B floor")
    if bad:
        return _row(3, UNSATISFIED, "; ".join(bad[:6]))
    return _row(
        3,
        SATISFIED,
        f"all artifacts >= {MIN_MEANINGFUL_BYTES} B (0-byte and 1-byte fail the floor)",
    )


def _load_schema(repo: Path, rel: str | None) -> dict[str, Any] | None:
    if not rel:
        return None
    path = _rel(repo, rel)
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _c4(obs: dict[str, Any]) -> dict[str, Any]:
    repo = _repo(obs)
    paths = _artifact_paths(obs)
    schema_rel = obs.get("schema_path")
    schema = _load_schema(repo, schema_rel if isinstance(schema_rel, str) else None)
    if schema is None:
        return _row(
            4,
            UNKNOWN,
            "schema missing or unreadable; parse-against-schema is NOT-CHECKED",
        )
    if not paths:
        return _row(4, UNSATISFIED, "no artifact to parse")
    try:
        import jsonschema  # type: ignore
    except ImportError:
        jsonschema = None
    errors: list[str] = []
    for p in paths:
        path = _rel(repo, p)
        if not path.is_file():
            errors.append(f"{p}: absent")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{p}: {type(exc).__name__}")
            continue
        if jsonschema is not None:
            try:
                jsonschema.validate(instance=doc, schema=schema)
            except jsonschema.ValidationError as exc:
                errors.append(f"{p}: {exc.message}")
            except Exception as exc:
                return _row(
                    4,
                    UNKNOWN,
                    f"schema not locally resolvable ({type(exc).__name__}); "
                    "parse-against-schema is NOT-CHECKED, not a pass",
                )
        else:
            required = schema.get("required") or []
            if isinstance(doc, dict):
                missing = [k for k in required if k not in doc]
                if missing:
                    errors.append(f"{p}: missing {missing}")
            elif schema.get("type") == "object":
                errors.append(f"{p}: not an object")
    if errors:
        return _row(4, UNSATISFIED, "; ".join(errors[:6]))
    return _row(4, SATISFIED, f"parses against {schema_rel}")


def _sentinel_present(text: str, sentinel: str) -> bool:
    """Require the sentinel as a whole JSON string value or a whole line.

    A quoted mention inside a longer prose string does not satisfy.
    """
    if text.strip() == sentinel:
        return True
    for line in text.splitlines():
        if line.strip() == sentinel:
            return True
        if line.strip() == json.dumps(sentinel):
            return True
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return False

    def walk(node: Any) -> bool:
        if isinstance(node, str):
            return node == sentinel
        if isinstance(node, dict):
            return any(walk(v) for v in node.values())
        if isinstance(node, list):
            return any(walk(v) for v in node)
        return False

    return walk(doc)


def _c5(obs: dict[str, Any]) -> dict[str, Any]:
    repo = _repo(obs)
    sentinel = str(obs.get("sentinel") or "").strip()
    if not sentinel:
        return _row(5, UNKNOWN, "no required sentinel declared")
    if not SENTINEL_RE.match(sentinel) and not sentinel.startswith("SUCCESS:"):
        # Still evaluate presence of whatever token was declared.
        pass
    paths = _artifact_paths(obs)
    if not paths:
        return _row(5, UNSATISFIED, "no artifact to search for sentinel")
    found = 0
    for p in paths:
        path = _rel(repo, p)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if _sentinel_present(text, sentinel):
            found += 1
    if found:
        return _row(
            5,
            SATISFIED,
            f"sentinel {sentinel!r} present as a whole string/line in {found} artifact(s)",
        )
    return _row(
        5,
        UNSATISFIED,
        f"sentinel {sentinel!r} absent as a whole value (substring mention is not enough)",
    )


def _c6(obs: dict[str, Any]) -> dict[str, Any]:
    repo = _repo(obs)
    anchors = obs.get("evidence")
    if anchors is None:
        return _row(6, UNKNOWN, "evidence anchors not declared")
    paths: list[str] = []
    for item in anchors:
        if isinstance(item, str) and item.strip():
            paths.append(item.split(":")[0].replace("\\", "/"))
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            paths.append(item["path"].split(":")[0].replace("\\", "/"))
    if not paths:
        return _row(6, UNKNOWN, "evidence list empty; anchors NOT-CHECKED")
    missing = [p for p in paths if not _rel(repo, p).is_file()]
    if missing:
        return _row(6, UNSATISFIED, f"anchor files absent: {missing[:4]}")
    return _row(6, SATISFIED, f"{len(paths)} evidence anchor file(s) exist")


def _c7(obs: dict[str, Any]) -> dict[str, Any]:
    tests = obs.get("tests")
    if tests is None:
        return _row(7, UNKNOWN, "tests not declared")
    if not isinstance(tests, list) or not tests:
        return _row(7, UNKNOWN, "no tests recorded (NOT a pass)")
    bad = []
    for t in tests:
        if not isinstance(t, dict):
            bad.append("non-object test row")
            continue
        result = str(t.get("result") or t.get("status") or "").upper()
        tid = t.get("id") or t.get("name") or "?"
        if result != "PASS":
            bad.append(f"{tid}={result or 'MISSING'}")
    if bad:
        return _row(7, UNSATISFIED, f"non-PASS tests: {bad[:6]}")
    return _row(7, SATISFIED, f"{len(tests)} test(s) recorded PASS")


def _c8(obs: dict[str, Any]) -> dict[str, Any]:
    controls = obs.get("negative_controls")
    if controls is None:
        return _row(8, UNKNOWN, "negative controls not declared")
    if not isinstance(controls, list) or not controls:
        return _row(8, UNKNOWN, "no negative controls recorded")
    failed_as_expected = 0
    broken = []
    for c in controls:
        if not isinstance(c, dict):
            broken.append("non-object control")
            continue
        cid = c.get("id") or "?"
        fired = c.get("fired_on_bad")
        silent = c.get("silent_on_good")
        if fired is True and silent is True:
            failed_as_expected += 1
        else:
            broken.append(f"{cid}: fired_on_bad={fired} silent_on_good={silent}")
    if broken:
        return _row(
            8,
            UNSATISFIED,
            "negative control did not fail as expected: " + "; ".join(broken[:6]),
        )
    if failed_as_expected == 0:
        return _row(8, UNSATISFIED, "no both-states negative control passed")
    return _row(
        8,
        SATISFIED,
        f"{failed_as_expected} both-states control(s) fired on bad and silent on good",
    )


def _c9(obs: dict[str, Any]) -> dict[str, Any]:
    reviewer = obs.get("reviewer")
    if reviewer is None:
        return _row(9, UNKNOWN, "reviewer record absent")
    if not isinstance(reviewer, dict):
        return _row(9, UNSATISFIED, "reviewer record is not an object")
    independent = reviewer.get("independent")
    verdict = str(reviewer.get("verdict") or "").upper()
    if independent is not True:
        return _row(9, UNSATISFIED, f"reviewer.independent={independent}")
    if verdict not in PASS_VERDICTS:
        return _row(9, UNSATISFIED, f"reviewer.verdict={verdict or 'MISSING'}")
    rid = reviewer.get("reviewer_id") or reviewer.get("id") or "anonymous"
    return _row(9, SATISFIED, f"independent reviewer {rid} {verdict}")


def _c10(obs: dict[str, Any]) -> dict[str, Any]:
    defects = obs.get("defects")
    if defects is None:
        return _row(10, UNKNOWN, "defects field absent; P0/P1 status NOT-CHECKED")
    if not isinstance(defects, list):
        return _row(10, UNSATISFIED, "defects is not a list")
    open_p = []
    for d in defects:
        if not isinstance(d, dict):
            continue
        sev = str(d.get("severity") or "").upper()
        st = str(d.get("status") or "").upper()
        if sev in P0P1 and st in OPEN_STATUSES:
            open_p.append(f"{d.get('id') or '?'}:{sev}/{st}")
    if open_p:
        return _row(10, UNSATISFIED, f"open P0/P1: {open_p[:6]}")
    return _row(10, SATISFIED, f"{len(defects)} defect(s) recorded, none open at P0/P1")


def _c11(obs: dict[str, Any]) -> dict[str, Any]:
    man = obs.get("manifest")
    if not isinstance(man, dict):
        return _row(11, UNKNOWN, "manifest registration not declared")
    if man.get("registered") is True and man.get("present") is True:
        sha = str(man.get("sha256") or "")
        if len(sha) == 64 and all(c in "0123456789abcdef" for c in sha):
            return _row(
                11,
                SATISFIED,
                f"manifest row present path={man.get('path')} sha256={sha[:12]}…",
            )
        return _row(11, UNSATISFIED, "registered row lacks a hex sha256")
    return _row(
        11,
        UNSATISFIED,
        f"registered={man.get('registered')} present={man.get('present')}",
    )


def _c12(obs: dict[str, Any]) -> dict[str, Any]:
    repo = _repo(obs)
    paths = _artifact_paths(obs)
    required = obs.get("consumer_required_fields") or ["unit_id"]
    if not isinstance(required, list) or not required:
        required = ["unit_id"]
    if not paths:
        return _row(12, UNSATISFIED, "no artifact for a consumer to read")
    read_ok = 0
    errors: list[str] = []
    for p in paths:
        path = _rel(repo, p)
        if not path.is_file():
            errors.append(f"{p}: absent (existence is not readability)")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{p}: consumer parse {type(exc).__name__}")
            continue
        if not isinstance(doc, dict):
            errors.append(f"{p}: consumer expected object")
            continue
        missing = [k for k in required if k not in doc]
        if missing:
            errors.append(f"{p}: consumer missing fields {missing}")
            continue
        read_ok += 1
    if errors:
        return _row(12, UNSATISFIED, "; ".join(errors[:6]))
    if read_ok == 0:
        return _row(12, UNSATISFIED, "consumer read zero artifacts")
    return _row(
        12,
        SATISFIED,
        f"{read_ok} consumer(s) opened, parsed, and extracted {required}",
    )


_CHECKERS = (_c1, _c2, _c3, _c4, _c5, _c6, _c7, _c8, _c9, _c10, _c11, _c12)


def evaluate(obs: dict[str, Any], invert: frozenset[int] | set[int] | None = None) -> dict[str, Any]:
    """Return a typed verdict. invert is test-only (planted-disagreement)."""
    flip = set(invert or ())
    rows = []
    for n, fn in enumerate(_CHECKERS, start=1):
        try:
            row = fn(obs)
        except Exception as exc:
            row = _row(
                n,
                UNKNOWN,
                f"evaluator raised {type(exc).__name__}: {exc}",
            )
        if row["n"] in flip:
            if row["outcome"] == SATISFIED:
                row = dict(row)
                row["outcome"] = UNSATISFIED
                row["basis"] = "PLANTED-INVERT: " + str(row["basis"])
            elif row["outcome"] == UNSATISFIED:
                row = dict(row)
                row["outcome"] = SATISFIED
                row["basis"] = "PLANTED-INVERT: " + str(row["basis"])
        rows.append(row)
    outcomes = [r["outcome"] for r in rows]
    if any(o == UNSATISFIED for o in outcomes):
        verdict = "INCOMPLETE"
    elif any(o == UNKNOWN for o in outcomes):
        verdict = "UNKNOWN"
    else:
        verdict = "COMPLETE"
    failing = [r["id"] for r in rows if r["outcome"] == UNSATISFIED]
    return {
        "implementation": "clean-room",
        "spec": "SPEC-FRAGMENT.txt",
        "verdict": verdict,
        "failing_condition_ids": failing,
        "conditions": rows,
        "anti_patterns": {
            "exit_code_never_success": True,
            "digest_is_not_receipt": True,
            "path_in_text_is_not_existence": True,
        },
    }

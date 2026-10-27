"""Shared twelve-condition completion predicate (IMP-0418 oracle subject).

Every fan-in site in ``fanin_sites`` calls ``judge``. Exit code is recorded
for forensics and is structurally incapable of producing COMPLETE: none of
the twelve conditions is "the process exited 0".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping

DEFAULT_MIN_BYTES = 128
SUCCESS_TERMINALS = frozenset({"SUCCESS", "COMPLETED"})
SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"

CONDITIONS: tuple[tuple[str, str], ...] = (
    ("C01", "process/task reached a valid terminal state"),
    ("C02", "expected artifact exists"),
    ("C03", "artifact is non-empty and exceeds a meaningful minimum size"),
    ("C04", "artifact parses against its schema"),
    ("C05", "required sentinel is present"),
    ("C06", "required evidence anchors exist"),
    ("C07", "required tests ran and passed"),
    ("C08", "negative controls or mutations fail as expected"),
    ("C09", "independent reviewer status is PASS"),
    ("C10", "no unresolved P0/P1 defect is attached"),
    ("C11", "output was registered in the artifact manifest"),
    ("C12", "downstream consumers can read it"),
)

EvalFn = Callable[[Mapping[str, Any], int], tuple[str, str]]


def _c01(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    state = str(record.get("state") or "")
    if state in SUCCESS_TERMINALS:
        return SATISFIED, f"state={state} is a completing terminal"
    return UNSATISFIED, f"state={state!r} is not a completing terminal"


def _c02(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("exists") is True:
        return SATISFIED, "artifact exists flag is true (corpus-measured)"
    return UNSATISFIED, "path in text is not proof: exists is not true"


def _c03(record: Mapping[str, Any], min_bytes: int) -> tuple[str, str]:
    try:
        size = int(record.get("bytes") or 0)
    except (TypeError, ValueError):
        return UNSATISFIED, "bytes is not an integer"
    if size <= 0:
        return UNSATISFIED, f"size={size} is empty"
    if size < min_bytes:
        return UNSATISFIED, f"size={size} < min_bytes={min_bytes}"
    return SATISFIED, f"size={size} >= min_bytes={min_bytes}"


def _c04(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("parses") is True:
        return SATISFIED, "artifact parses against its schema"
    return UNSATISFIED, "artifact does not parse against its schema"


_SENTINEL_TOKEN = re.compile(r"SUCCESS:([A-Z][A-Z0-9]*-[0-9]{4})")

#: The two artifact fields where a completion sentinel is LIVE (a role), not a mention.
_SENTINEL_ROLE_KEYS = ("sentinel", "completion_sentinel")


def evaluate_c05_artifact(text: str, unit_id: str) -> dict[str, Any]:
    """Role-based condition 5 over raw artifact text (TST-0145).

    SATISFIED only when a sentinel ROLE field of the parsed artifact carries
    ``SUCCESS:<unit_id>``. A token that appears only in prose is a mention,
    not a live sentinel (use vs mention), and a role field naming another
    unit is an UNSATISFIED that names the mismatch.
    """
    expected = f"SUCCESS:{unit_id}"
    detail: dict[str, Any] = {"expected": expected}
    try:
        doc = json.loads(text)
    except (TypeError, ValueError):
        doc = None
    if not isinstance(doc, dict):
        detail["parse_ok"] = False
        return {
            "outcome": UNSATISFIED,
            "basis": "artifact is not a JSON object; no sentinel role field is readable",
            "detail": detail,
        }
    roles = {
        key: doc.get(key)
        for key in _SENTINEL_ROLE_KEYS
        if isinstance(doc.get(key), str) and doc.get(key)
    }
    detail["roles"] = roles
    if any(val == expected for val in roles.values()):
        return {
            "outcome": SATISFIED,
            "basis": f"sentinel role field carries {expected} verbatim",
            "detail": detail,
        }
    for key, val in roles.items():
        m = _SENTINEL_TOKEN.search(val)
        if m and m.group(1) != unit_id:
            foreign = m.group(1)
            detail["foreign_unit"] = foreign
            detail["found_sentinel"] = val
            return {
                "outcome": UNSATISFIED,
                "basis": (
                    f"sentinel role {key!r} names a different unit: found "
                    f"SUCCESS:{foreign} ({val!r}), expected {expected}"
                ),
                "detail": detail,
            }
    if expected in (text or ""):
        detail["mention_only"] = True
        return {
            "outcome": UNSATISFIED,
            "basis": (
                f"{expected} appears only as a quoted mention in the artifact "
                "bytes, not in a sentinel role field (use vs mention)"
            ),
            "detail": detail,
        }
    return {
        "outcome": UNSATISFIED,
        "basis": f"no completion sentinel role present; expected {expected}",
        "detail": detail,
    }


def substring_c05_artifact(text: str, unit_id: str) -> dict[str, Any]:
    """The naive substring mutant: fooled by quoted mentions (negative control)."""
    expected = f"SUCCESS:{unit_id}"
    hit = expected in (text or "")
    return {
        "outcome": SATISFIED if hit else UNSATISFIED,
        "basis": f"substring scan: {expected} {'found' if hit else 'absent'} in bytes",
        "detail": {"method": "substring", "expected": expected},
    }


def _c05(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    # Role-based path: when the caller supplies the artifact text, C05 is the
    # live role evaluator, never a self-declared flag.
    art_text = record.get("artifact_text")
    if isinstance(art_text, str):
        live = evaluate_c05_artifact(art_text, str(record.get("unit_id") or ""))
        return live["outcome"], live["basis"]
    sentinel = record.get("sentinel")
    if isinstance(sentinel, str) and sentinel.strip():
        return SATISFIED, f"sentinel present ({len(sentinel)} chars)"
    return UNSATISFIED, "sentinel missing or empty"


def _c06(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    try:
        n = int(record.get("evidence_count") or 0)
    except (TypeError, ValueError):
        n = 0
    if n >= 2:
        return SATISFIED, f"evidence_count={n} >= 2"
    return UNSATISFIED, f"evidence_count={n} < 2"


def _c07(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("tests_passed") is True:
        return SATISFIED, "required tests ran and passed"
    return UNSATISFIED, "required tests missing or not PASS"


def _c08(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("negative_controls_ok") is True:
        return SATISFIED, "negative controls fired on bad and silent on good"
    return UNSATISFIED, "negative controls inert or missing"


def _c09(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("reviewer_pass") is True:
        return SATISFIED, "independent reviewer status is PASS"
    return UNSATISFIED, "reviewer is not an independent PASS"


def _c10(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("open_p0p1") is True:
        return UNSATISFIED, "unresolved P0/P1 defect is attached"
    return SATISFIED, "no unresolved P0/P1 defect is attached"


def _c11(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("manifest_registered") is True:
        return SATISFIED, "output registered in the artifact manifest"
    return UNSATISFIED, "output is not registered in the artifact manifest"


def _c12(record: Mapping[str, Any], _min_bytes: int) -> tuple[str, str]:
    if record.get("downstream_readable") is True:
        return SATISFIED, "downstream consumers can read it"
    return UNSATISFIED, "downstream consumers cannot read it"


EVALUATORS: tuple[tuple[str, str, EvalFn], ...] = (
    ("C01", CONDITIONS[0][1], _c01),
    ("C02", CONDITIONS[1][1], _c02),
    ("C03", CONDITIONS[2][1], _c03),
    ("C04", CONDITIONS[3][1], _c04),
    ("C05", CONDITIONS[4][1], _c05),
    ("C06", CONDITIONS[5][1], _c06),
    ("C07", CONDITIONS[6][1], _c07),
    ("C08", CONDITIONS[7][1], _c08),
    ("C09", CONDITIONS[8][1], _c09),
    ("C10", CONDITIONS[9][1], _c10),
    ("C11", CONDITIONS[10][1], _c11),
    ("C12", CONDITIONS[11][1], _c12),
)


class _ConditionRows(list):
    """Row list that also answers dict-style lookups by condition id.

    ``rows.get("C05")`` returns "PASS"/"FAIL" for that condition (TST-0145
    consumers); iteration and JSON serialization keep the plain row-list shape
    that IMP-0418 and the other fan-in consumers already rely on.
    """

    def get(self, cid: str, default: Any = None) -> Any:
        for row in self:
            if isinstance(row, dict) and row.get("id") == cid:
                return "PASS" if row.get("outcome") == SATISFIED else "FAIL"
        return default


def _effective_min_bytes(record: Mapping[str, Any], min_bytes: int | None) -> int:
    if min_bytes is not None:
        return int(min_bytes)
    declared = record.get("min_bytes")
    if isinstance(declared, int) and declared > 0:
        return declared
    return DEFAULT_MIN_BYTES


def judge(
    record: Mapping[str, Any] | None = None,
    min_bytes: int | None = None,
) -> dict[str, Any]:
    """Return COMPLETE only when all twelve conditions are SATISFIED.

    ``exit_code`` is never consulted. A record whose only fact is
    ``{"state": "RUNNING", "exit_code": 0}`` is therefore INCOMPLETE.
    """
    payload: Mapping[str, Any] = record if isinstance(record, Mapping) else {}
    floor = _effective_min_bytes(payload, min_bytes)
    rows = []
    failing: list[str] = []
    for cid, name, fn in EVALUATORS:
        outcome, basis = fn(payload, floor)
        rows.append(
            {
                "id": cid,
                "name": name,
                "outcome": outcome,
                "basis": basis,
            }
        )
        if outcome != SATISFIED:
            failing.append(cid)
    complete = not failing
    return {
        "verdict": "COMPLETE" if complete else "INCOMPLETE",
        "complete": complete,
        "failing": failing,
        "conditions": _ConditionRows(rows),
        "min_bytes": floor,
        "exit_code": payload.get("exit_code"),
        "exit_code_consulted": False,
    }


class _EvalResult:
    def __init__(self, verdict: str) -> None:
        self.verdict = verdict


def evaluate(receipt: Mapping[str, Any] | None = None, repo: Any = None, opts: Any = None, **kwargs: Any) -> Any:
    """ADV-0116 hot-path: evaluate(receipt, repo=root) -> object with .verdict."""
    del kwargs
    payload: Mapping[str, Any] = receipt if isinstance(receipt, Mapping) else {}
    if opts is not None and hasattr(opts, "repo_root"):
        repo = getattr(opts, "repo_root", repo)
    try:
        plat = Path(__file__).resolve().parents[2] / "platform" / "lib" / "completion_predicate.py"
        if plat.is_file() and repo is not None:
            import importlib.util

            spec = importlib.util.spec_from_file_location("_plat_cp_adv0116", plat)
            if spec is not None and spec.loader is not None:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                popts = mod.PredicateOptions(repo_root=Path(repo))
                return mod.evaluate(payload, popts)
    except Exception:
        pass
    judged = judge(payload)
    return _EvalResult(judged["verdict"])

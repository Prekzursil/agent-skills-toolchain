"""The shared 12-condition completion predicate, bound to the workflow-artifact type.

WFA-0134: one reducer (this module's ``evaluate``) is imported by the local
runner, the tournament runner, and the certification gate. Every workflow gets
a CERTIFIED / PROVISIONAL / REJECTED record naming which of the 12 conditions
passed, failed, or are not-applicable WITH a reason.

Hard rules, enforced structurally:
  * exit code zero alone is never success — condition 1 needs a success-class
    terminal state and no condition consults ``exit_code``;
  * a plausible digest is not a receipt — condition 11 re-hashes the bytes on
    disk against the manifest row;
  * a file path in text is not proof the file exists — condition 2 stat()s it.

N/A is honest: it is rendered only when the caller declares a condition
inapplicable WITH a reason for a non-workflow-artifact unit class; it is never
counted as a pass, and an unreasoned N/A fail-closes to FAIL.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

MIN_BYTES = 128

CERTIFIED = "CERTIFIED"
PROVISIONAL = "PROVISIONAL"
REJECTED = "REJECTED"
PASS = "PASS"
FAIL = "FAIL"
NA = "NA"
UNKNOWN = "UNKNOWN"
NOT_CHECKED = "NOT-CHECKED"

REDUCER_MODULE = "tools.foundry.completion_predicate"
REDUCER_PATH = "tools/foundry/completion_predicate.py"

SUCCESS_TERMINALS = frozenset({"SUCCESS", "COMPLETED"})

#: Stage actions the foundry consumer can actually dispatch (condition 12).
FOUNDRY_ACTIONS = frozenset({"noop", "run", "review", "gate", "emit", "synthesize"})

CONDITIONS: tuple[tuple[int, str, str], ...] = (
    (1, "process/task reached a valid terminal state", "spec:10633"),
    (2, "expected artifact exists", "spec:10634"),
    (3, "artifact is non-empty and exceeds a meaningful minimum size", "spec:10635"),
    (4, "artifact parses against its schema", "spec:10636"),
    (5, "required sentinel is present", "spec:10637"),
    (6, "required evidence anchors exist", "spec:10638"),
    (7, "required tests ran and passed", "spec:10639"),
    (8, "negative controls or mutations fail as expected", "spec:10640"),
    (9, "independent reviewer status is PASS", "spec:10641"),
    (10, "no unresolved P0/P1 defect is attached", "spec:10642"),
    (11, "output was registered in the artifact manifest", "spec:10643"),
    (12, "downstream consumers can read it", "spec:10644"),
)
CONDITION_NAME = {cid: name for cid, name, _ in CONDITIONS}


def impl_ptr(fn: Callable[..., Any]) -> str:
    """path:function:line pointer for a checker, so records cite real code."""
    return f"{REDUCER_PATH}:{fn.__name__}:{fn.__code__.co_firstlineno}"


@dataclass
class Condition:
    cid: int
    name: str
    status: str
    reason: str
    impl: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.cid,
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "impl": self.impl,
        }


@dataclass
class Verdict:
    workflow_id: str
    record: str
    locus: str
    reducer: str
    conditions: list[Condition]
    notes: dict[str, Any]

    def condition(self, cid: int) -> Condition:
        for c in self.conditions:
            if c.cid == cid:
                return c
        raise KeyError(cid)

    def statuses(self) -> tuple[str, ...]:
        return tuple(c.status for c in self.conditions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "record": self.record,
            "locus": self.locus,
            "reducer": self.reducer,
            "conditions": [c.to_dict() for c in self.conditions],
            "notes": self.notes,
        }


# ------------------------------------------------------------------- helpers


def _resolve(repo: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw:
        return None
    p = Path(raw)
    return p if p.is_absolute() else repo / raw


def _lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _artifact(subject: Mapping[str, Any], repo: Path) -> Path | None:
    return _resolve(repo, subject.get("artifact_path"))


def _artifact_text(subject: Mapping[str, Any], repo: Path) -> str | None:
    p = _artifact(subject, repo)
    if p is None or not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


# ------------------------------------------------------------------ checkers


def _c1_terminal(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    state = subject.get("terminal_state")
    if not isinstance(state, str) or not state:
        return FAIL, "no terminal state declared; exit code zero alone is never success"
    if state not in SUCCESS_TERMINALS:
        return FAIL, f"terminal state {state!r} is not success-class {sorted(SUCCESS_TERMINALS)}"
    return PASS, f"terminal state {state} is success-class"


def _c2_exists(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    p = _artifact(subject, repo)
    if p is None:
        return FAIL, "no artifact_path declared"
    if not p.is_file():
        # Reason cites the basename only: verdicts are re-derived in fresh temp
        # roots and their reasons must be byte-identical across runs.
        return FAIL, f"stat says absent: {p.name} - a file path in text is not proof the file exists"
    return PASS, "artifact stat()ed present on disk"


def _c3_size(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    p = _artifact(subject, repo)
    if p is None or not p.is_file():
        return UNKNOWN, "artifact absent; size not measurable (condition 2 owns this failure)"
    floor = subject.get("min_bytes")
    floor = int(floor) if isinstance(floor, int) and floor > 0 else MIN_BYTES
    n = p.stat().st_size
    if n == 0:
        return FAIL, "artifact is 0 bytes"
    if n < floor:
        return FAIL, f"artifact is {n} bytes, below the minimum {floor}"
    return PASS, f"artifact is {n} bytes >= {floor}"


def _c4_schema(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    text = _artifact_text(subject, repo)
    if text is None:
        return UNKNOWN, "artifact absent/unreadable; cannot parse (condition 2 owns this failure)"
    schema_path = _resolve(repo, subject.get("schema_path"))
    if schema_path is None or not schema_path.is_file():
        return UNKNOWN, f"declared schema not on disk: {subject.get('schema_path')!r}"
    try:
        instance = json.loads(text)
    except ValueError as exc:
        return FAIL, f"artifact does not parse as JSON: {exc}"
    try:
        import jsonschema
    except ImportError:
        return UNKNOWN, "jsonschema is not installed; cannot validate"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        return FAIL, f"artifact fails its schema: {exc.message}"
    except (OSError, ValueError, jsonschema.SchemaError) as exc:
        return UNKNOWN, f"schema unreadable/invalid: {exc}"
    return PASS, "artifact validates against its workflow schema"


def _c5_sentinel(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    text = _artifact_text(subject, repo)
    if text is None:
        return UNKNOWN, "artifact absent; sentinel not measurable (condition 2 owns this failure)"
    sentinel = subject.get("required_sentinel")
    if not isinstance(sentinel, str) or not sentinel:
        return FAIL, "no required_sentinel declared"
    if sentinel not in text:
        return FAIL, f"required sentinel {sentinel!r} is not in the artifact bytes"
    return PASS, f"sentinel {sentinel!r} found verbatim in artifact"


def _c6_evidence(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    items = subject.get("evidence")
    items = [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
    if len(items) < 2:
        return FAIL, f"{len(items)} evidence anchor(s) < required 2 mechanically independent signals"
    for idx, item in enumerate(items):
        kind = str(item.get("kind") or "")
        if kind == "file:line":
            p = _resolve(repo, item.get("path"))
            if p is None or not p.is_file():
                return FAIL, f"evidence[{idx}] path does not resolve: {item.get('path')!r}"
            body = p.read_text(encoding="utf-8", errors="replace")
            line = item.get("line")
            if isinstance(line, int) and line > len(body.splitlines()):
                return FAIL, f"evidence[{idx}] cites line {line} beyond EOF"
            needle = item.get("needle")
            if isinstance(needle, str) and needle and needle not in body:
                return FAIL, f"evidence[{idx}] needle {needle!r} absent from {item.get('path')}"
        elif kind == "command":
            if not str(item.get("command") or "").strip():
                return FAIL, f"evidence[{idx}] command anchor is empty"
        else:
            return FAIL, f"evidence[{idx}] has unknown anchor kind {kind!r}"
    return PASS, f"{len(items)} evidence anchors resolve (file:line verified, command rerunnable)"


def _c7_tests(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    tests = subject.get("tests")
    tests = [t for t in tests if isinstance(t, dict)] if isinstance(tests, list) else []
    if not tests:
        return FAIL, "no required test record; missing tests fail closed"
    bad = [t.get("id") for t in tests if t.get("result") != PASS]
    if bad:
        return FAIL, f"test(s) not PASS: {bad}"
    return PASS, f"{len(tests)} required test(s) ran and passed"


def _c8_mutations(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    muts = subject.get("mutations")
    muts = [m for m in muts if isinstance(m, dict)] if isinstance(muts, list) else []
    if not muts:
        return FAIL, "no mutation control declared; a silent control is not evidence"
    dead = [m.get("id") for m in muts if m.get("fired") is not True]
    if dead:
        return FAIL, f"mutation control(s) did not fire: {dead}"
    return PASS, f"{len(muts)} mutation control(s) fired as expected"


def _c9_reviewer(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    rv = subject.get("reviewer")
    if not isinstance(rv, dict):
        return FAIL, "no reviewer record; absence is FAIL, not a quiet N/A skip"
    verdict = rv.get("verdict")
    if verdict in {NOT_CHECKED, UNKNOWN, None, ""}:
        return UNKNOWN, f"reviewer verdict is {verdict!r}; review not yet measured"
    if verdict != PASS:
        return FAIL, f"reviewer verdict is {verdict!r}, not PASS"
    if rv.get("independent") is not True:
        return FAIL, "reviewer is not marked independent; self-review is not review"
    return PASS, f"independent reviewer {rv.get('reviewer_id')!r} returned PASS"


def _c10_defects(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    defects = subject.get("defects")
    defects = [d for d in defects if isinstance(d, dict)] if isinstance(defects, list) else []
    blocking = [
        d.get("id")
        for d in defects
        if d.get("severity") in {"P0", "P1"} and d.get("resolved") is not True
    ]
    if blocking:
        return FAIL, f"unresolved P0/P1 defect(s) attached: {blocking}"
    return PASS, f"{len(defects)} attached defect(s), none an unresolved P0/P1"


def _c11_manifest(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    art = _artifact(subject, repo)
    if art is None or not art.is_file():
        return UNKNOWN, "artifact absent; registration not measurable (condition 2 owns this failure)"
    mp = _resolve(repo, subject.get("manifest_path"))
    if mp is None or not mp.is_file():
        return UNKNOWN, f"manifest not on disk: {subject.get('manifest_path')!r}"
    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return UNKNOWN, f"manifest unreadable/unparsable: {exc}"
    rows = manifest.get("artifacts") if isinstance(manifest, dict) else None
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    want = str(art.as_posix())
    row = next((r for r in rows if str(r.get("path") or "").replace("\\", "/") == want), None)
    if row is None:
        return FAIL, f"artifact {art.name!r} is not registered in the manifest"
    recorded = str(row.get("sha256") or "")
    live = _lf_sha256(art)
    if recorded != live:
        return FAIL, (
            f"manifest digest {recorded[:12]} != live {live[:12]} - "
            "a plausible digest is not a receipt"
        )
    return PASS, "live sha256 matches the manifest row"


def _c12_consumer(subject: Mapping[str, Any], repo: Path) -> tuple[str, str]:
    text = _artifact_text(subject, repo)
    if text is None:
        return UNKNOWN, "artifact absent; consumer read not measurable (condition 2 owns this failure)"
    try:
        doc = json.loads(text)
    except ValueError:
        return UNKNOWN, "artifact is not JSON; consumer dispatch not measurable (condition 4 owns this)"
    stages = doc.get("stages") if isinstance(doc, dict) else None
    stages = [s for s in stages if isinstance(s, dict)] if isinstance(stages, list) else []
    if not stages:
        return FAIL, "no dispatchable stage; the foundry consumer cannot read this blueprint"
    for s in stages:
        action = str(s.get("action") or "")
        if action not in FOUNDRY_ACTIONS:
            return FAIL, (
                f"stage {s.get('id')!r} action {action!r} is not a foundry action; "
                "the consumer must refuse it"
            )
    return PASS, f"foundry consumer read the blueprint and can dispatch all {len(stages)} stage(s)"


_CHECKERS: dict[int, Callable[[Mapping[str, Any], Path], tuple[str, str]]] = {
    1: _c1_terminal,
    2: _c2_exists,
    3: _c3_size,
    4: _c4_schema,
    5: _c5_sentinel,
    6: _c6_evidence,
    7: _c7_tests,
    8: _c8_mutations,
    9: _c9_reviewer,
    10: _c10_defects,
    11: _c11_manifest,
    12: _c12_consumer,
}


# ------------------------------------------------------------------ reducer


def _na_entry(subject: Mapping[str, Any], cid: int) -> Mapping[str, Any] | None:
    """The caller-declared applicability entry for cid, when it waives it."""
    app = subject.get("applicability")
    if not isinstance(app, Mapping):
        return None
    entry = app.get(str(cid)) or app.get(cid)
    if isinstance(entry, Mapping) and entry.get("applicable") is False:
        return entry
    return None


def evaluate(
    subject: Mapping[str, Any] | None = None,
    *,
    locus: str = "direct",
    repo: Any = None,
    pair_id: Any = None,
    **kwargs: Any,
) -> Verdict:
    """Evaluate all 12 conditions on a workflow subject. Never consults exit_code.

    Total function: a malformed subject yields FAIL/UNKNOWN per condition,
    never an exception and never CERTIFIED.
    """
    del kwargs
    sub: Mapping[str, Any] = subject if isinstance(subject, Mapping) else {}
    root = Path(repo) if repo is not None else Path(".")
    workflow_class = str(sub.get("unit_class") or "workflow-artifact")

    conditions: list[Condition] = []
    for cid, name, _spec in CONDITIONS:
        checker = _CHECKERS[cid]
        ptr = impl_ptr(checker)
        na = _na_entry(sub, cid)
        if na is not None:
            reason = str(na.get("reason") or "").strip()
            if workflow_class == "workflow-artifact":
                conditions.append(
                    Condition(cid, name, FAIL, "workflow-artifact policy is all-12-applicable; "
                              "declaring one inapplicable is a quiet skip and fail-closes", ptr)
                )
                continue
            if not reason:
                conditions.append(
                    Condition(cid, name, FAIL,
                              "declared inapplicable with no reason; unreasoned N/A fail-closes", ptr)
                )
                continue
            conditions.append(
                Condition(cid, name, NA, f"not applicable for this unit class: {reason}", ptr)
            )
            continue
        try:
            status, reason = checker(sub, root)
        except Exception as exc:  # noqa: BLE001 - a checker crash must never certify
            status, reason = FAIL, f"checker raised {type(exc).__name__}: {exc}"
        conditions.append(Condition(cid, name, status, reason, ptr))

    statuses = [c.status for c in conditions]
    if FAIL in statuses:
        record = REJECTED
    elif UNKNOWN in statuses:
        record = PROVISIONAL
    else:
        record = CERTIFIED

    notes: dict[str, Any] = {
        "pass_count": statuses.count(PASS),
        "fail_count": statuses.count(FAIL),
        "unknown_count": statuses.count(UNKNOWN),
        "na_count": statuses.count(NA),
        "exit_code_consulted": False,
        "exit_only_rejected": bool(sub.get("exit_code") == 0 and record == REJECTED),
    }
    if pair_id is not None:
        notes["pair_id"] = pair_id

    wid = sub.get("workflow_id")
    wid = wid if isinstance(wid, str) and wid else "UNKNOWN-WORKFLOW"
    return Verdict(wid, record, locus, REDUCER_MODULE, conditions, notes)


__all__ = [
    "CERTIFIED",
    "CONDITIONS",
    "CONDITION_NAME",
    "Condition",
    "FAIL",
    "FOUNDRY_ACTIONS",
    "MIN_BYTES",
    "NA",
    "NOT_CHECKED",
    "PASS",
    "PROVISIONAL",
    "REDUCER_MODULE",
    "REDUCER_PATH",
    "REJECTED",
    "UNKNOWN",
    "Verdict",
    "_CHECKERS",
    "evaluate",
    "impl_ptr",
]

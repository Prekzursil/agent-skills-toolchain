"""THE COMPLETION ORACLE — the single most important function in this package.

A unit is SUCCESS only on the AND of six clauses:

1. ``exit-zero``        — the rail exited 0;
2. ``receipt-present``  — the receipt exists (``receipt_bytes is not None``);
3. ``receipt-non-empty``— it is not blank;
4. ``receipt-parses``   — it decodes, and for ``fmt="json"`` it parses to an object;
5. ``receipt-schema``   — every ``required_fields`` key is present and non-blank;
6. ``receipt-content``  — no ``forbidden_markers``, and the body is not a progress stream.

**Blocking on process exit is NOT proof of completion.** Exit 0 with a receipt that is
missing, empty, unparseable, schema-invalid or "still in progress" is **SEVERED**, never
SUCCESS. Measured: a foreground dispatch returned after 6m59s carrying only a progress prefix,
and the caller forwarded that as its terminal result while the job was still ``running``.

``Verdict.reason`` is the FINE cause (for the operator) and ``Verdict.severed`` is the family
flag (for consumers that match on ``severed-stream``). Both are emitted, so neither audience
has to parse the other's string — the earlier design shipped only the fine cause and would
have silently broken every consumer matching on ``severed-stream``.

The ``progress`` field of :class:`RailResult` is DIAGNOSTICS. It is never read as a result.

:func:`judge` also REFUSES a vacuous :class:`~agentspec.spec.ReceiptSpec` (fail-closed). Only
``validate_workflow`` used to catch that, so a consumer that hand-built a spec and called
``judge`` directly lost the catch and silently ran a two-clause gate. Both call sites now share
:meth:`~agentspec.spec.ReceiptSpec.is_vacuous`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentspec import receipt as receipt_mod
from agentspec import wire
from agentspec.canonical import dumps as canonical_dumps
from agentspec.envelope import ErrorDetail, Observation, error, success
from agentspec.progress import looks_like_progress
from agentspec.retry import RATE_LIMIT_MAX_ATTEMPTS
from agentspec.spec import RECEIPT_FORMATS, ReceiptSpec
from agentspec.taxonomy import family, rail_exit

TAXONOMY_EMPTY_FANOUT = "empty-fanout"
TAXONOMY_SEVERED_STREAM = "severed-stream"


def evaluate_producer(run: Any) -> dict[str, Any]:
    """Oracle gate for a DynamicFanOut producer run (IMP-0219)."""
    receipt = getattr(run, "receipt", None)
    exit_code = int(getattr(run, "exit_code", 1) or 1)
    stdout = str(getattr(run, "stdout", "") or "")
    if is_progress_stream(stdout):
        return {"ok": False, "reason": "progress-stream"}
    if exit_code == 0 and not receipt:
        return {"ok": False, "reason": "severed-stream"}
    if receipt:
        return {"ok": True, "reason": "ok"}
    return {"ok": False, "reason": "severed-stream"}


def is_progress_stream(body: str | None) -> bool:
    text = str(body or "")
    if looks_like_progress(text):
        return True
    low = text.lstrip()
    if low.startswith("{") or low.startswith("["):
        try:
            doc = json.loads(text)
        except Exception:
            doc = None
        if isinstance(doc, dict):
            markers = {str(doc.get(k) or "").upper() for k in ("kind", "type", "stream", "state")}
            if "PROGRESS" in markers or "RUNNING" in markers:
                return True
        if isinstance(doc, list) and doc and isinstance(doc[0], dict):
            if str(doc[0].get("type") or "").upper() == "PROGRESS":
                return True
    if '"type": "PROGRESS"' in text or '"kind": "PROGRESS"' in text:
        return True
    return False

def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


CLAUSES: tuple[str, ...] = (
    "exit-zero",
    "receipt-present",
    "receipt-non-empty",
    "receipt-parses",
    "receipt-schema",
    "receipt-content",
)


@dataclass(frozen=True, slots=True)
class RailResult:
    """What a rail hands back. ``wall_ms`` is an int; a float would break wire parity."""

    exit_code: int
    receipt_bytes: bytes | None
    progress: str = ""
    wall_ms: int = 0

    def __post_init__(self) -> None:
        wire.require_wire_integer(self.wall_ms, "wall_ms")
        if self.wall_ms < 0:
            raise ValueError("wall_ms must be >= 0")


@dataclass(frozen=True, slots=True)
class Verdict:
    """The oracle's answer. ``ok`` is true only when every clause passed."""

    unit_id: str
    ok: bool
    reason: str | None
    severed: bool
    passed_clauses: tuple[str, ...]
    detail: str
    payload: Mapping[str, Any] | None = None
    text: str | None = None
    wall_ms: int = 0

    @property
    def failure_reason(self) -> str:
        """The taxonomy reason for a FAILED verdict; the empty string for a successful one.

        A total accessor, so no call site needs an ``assert`` (an assert on a condition that
        is never false is an uncoverable branch, i.e. a self-inflicted coverage hole).
        """
        return self.reason or ""


def judge_receipt_path(path: Any, *, root: Any = None) -> Verdict:
    """G-1 receipt-file form used by fan-in consider() and IMP-0226 probes."""
    import json
    from pathlib import Path as _P

    receipt = _P(path)
    base = _P(root) if root is not None else receipt.parent
    try:
        doc = json.loads(receipt.read_text(encoding="utf-8"))
    except Exception:
        return Verdict(
            unit_id="unknown",
            ok=False,
            reason="receipt-unparseable",
            severed=False,
            passed_clauses=(),
            detail="unparseable",
        )
    uid = str(doc.get("unit_id") or receipt.stem)
    arts = doc.get("artifacts") or []
    for art in arts:
        if not isinstance(art, dict):
            continue
        rel = str(art.get("path") or "")
        target = (base / rel) if rel else None
        if target is None or not target.is_file():
            return Verdict(
                unit_id=uid,
                ok=False,
                reason="missing-artifact",
                severed=False,
                passed_clauses=("exit-zero", "receipt-present"),
                detail=rel,
            )
        want = str(art.get("sha256") or "")
        if want:
            got = digest_bytes(target.read_bytes())
            if got != want:
                return Verdict(
                    unit_id=uid,
                    ok=False,
                    reason="sha-mismatch",
                    severed=False,
                    passed_clauses=("exit-zero", "receipt-present"),
                    detail=rel,
                )
    return Verdict(
        unit_id=uid,
        ok=True,
        reason=None,
        severed=False,
        passed_clauses=CLAUSES,
        detail="",
    )


def judge(unit_id: str, result: RailResult | None = None, spec: ReceiptSpec | None = None, *, root: Any = None) -> Verdict:
    """Apply the six-clause AND-gate to ``result``.

    Also accepts ``judge(path, root=root)`` for G-1 fan-in receipt files.
    """
    if spec is None and not isinstance(result, RailResult):
        return judge_receipt_path(unit_id, root=root)
    if wire.is_blank(unit_id):
        raise ValueError("unit_id must be non-empty")
    if spec.fmt not in RECEIPT_FORMATS:
        raise ValueError(f"receipt spec fmt must be one of {list(RECEIPT_FORMATS)}")
    if spec.is_vacuous():
        raise ValueError(
            "receipt spec is vacuous: a json spec needs required_fields and a text spec needs "
            "forbidden_markers, or the AND-gate silently reduces to 'exit 0 AND non-empty' "
            "and a receipt reading 'work is still in progress' reports SUCCESS"
        )

    if result.exit_code != 0:
        return _fail(unit_id, rail_exit(result.exit_code), (), result, severed=False)

    passed = ("exit-zero",)
    if result.receipt_bytes is None:
        return _fail(unit_id, "receipt-missing", passed, result)

    passed = (*passed, "receipt-present")
    try:
        text = receipt_mod.decode(result.receipt_bytes)
    except receipt_mod.ReceiptUnparseable as exc:
        return _fail(unit_id, "receipt-unparseable", passed, result, detail=str(exc))
    if wire.is_blank(text):
        return _fail(unit_id, "receipt-empty", passed, result)

    passed = (*passed, "receipt-non-empty")
    payload: Mapping[str, Any] | None = None
    if spec.fmt == "json":
        try:
            payload = receipt_mod.parse_json_object(text)
        except receipt_mod.ReceiptUnparseable as exc:
            return _fail(
                unit_id, "receipt-unparseable", passed, result, detail=str(exc)
            )

    passed = (*passed, "receipt-parses")
    if payload is not None:
        absent = receipt_mod.missing_fields(payload, spec)
        if absent:
            return _fail(
                unit_id,
                "schema-invalid",
                passed,
                result,
                detail=f"schema-invalid: missing or blank {canonical_dumps(list(absent))}",
            )

    passed = (*passed, "receipt-schema")
    markers = receipt_mod.present_markers(text, spec)
    if markers:
        return _fail(
            unit_id,
            "receipt-incomplete",
            passed,
            result,
            detail=f"receipt-incomplete: body carries {canonical_dumps(list(markers))}",
        )
    if looks_like_progress(text):
        return _fail(
            unit_id,
            "progress-stream",
            passed,
            result,
            detail="progress-stream: the receipt body is a progress/status stream",
        )

    return Verdict(
        unit_id=unit_id,
        ok=True,
        reason=None,
        severed=False,
        passed_clauses=CLAUSES,
        detail="all six clauses passed",
        payload=payload,
        text=text,
        wall_ms=result.wall_ms,
    )


def observe(verdict: Verdict, *, artifacts: tuple[str, ...] = ()) -> Observation:
    """Project a verdict onto the shared observation envelope.

    Every error path carries a root-cause hint, a safe retry instruction and an EXPLICIT stop
    condition — "error-only output without next steps" is a named anti-pattern.
    """
    if verdict.ok:
        return success(
            f"{verdict.unit_id}: completed ({verdict.wall_ms} ms)",
            next_actions=("consume the receipt payload",),
            artifacts=artifacts,
        )
    reason = verdict.failure_reason
    root_cause = _root_cause(verdict, reason)
    return error(
        f"{verdict.unit_id}: {reason}",
        ErrorDetail(
            code=reason,
            root_cause=root_cause,
            retry_instruction=_retry_instruction(reason),
            stop_condition=_stop_condition(reason),
        ),
        next_actions=(_next_action(reason),),
        artifacts=artifacts,
    )


def _fail(
    unit_id: str,
    reason: str,
    passed: tuple[str, ...],
    result: RailResult,
    *,
    severed: bool = True,
    detail: str = "",
) -> Verdict:
    return Verdict(
        unit_id=unit_id,
        ok=False,
        reason=reason,
        severed=severed,
        passed_clauses=passed,
        detail=detail or reason,
        wall_ms=result.wall_ms,
    )


def _root_cause(verdict: Verdict, reason: str) -> str:
    if verdict.severed:
        return (
            f"severed-stream: the rail exited 0 but produced no usable work product "
            f"({verdict.detail}). Exit 0 is not proof of completion."
        )
    return f"the rail itself failed: {reason} ({verdict.detail})"


def _retry_instruction(reason: str) -> str:
    if family(reason) == "rate-limited":
        return (
            "back off and re-dispatch the SAME unit: agentspec.retry.plan_retry returns the "
            "bounded doubling schedule; add jitter in the transport, never here"
        )
    if reason == "receipt-missing":
        return (
            "re-dispatch the SAME unit once, in the FOREGROUND, with an explicit "
            "receipt-path flag (never --background)"
        )
    if reason in {"receipt-empty", "receipt-unparseable"}:
        return "re-dispatch the SAME unit once; do not parse the progress stream as a fallback"
    if reason in {"schema-invalid", "receipt-incomplete", "progress-stream"}:
        return (
            "do NOT retry blindly: the rail returned a real but unusable body, so re-dispatch "
            "only after the prompt states the required receipt shape"
        )
    return "inspect the diagnostic tail first; retry only after the cause is understood"


def _stop_condition(reason: str) -> str:
    if family(reason) == "rate-limited":
        return (
            f"stop after {RATE_LIMIT_MAX_ATTEMPTS} attempts and report "
            f"FAILED <unit> {reason}; never retry unbounded"
        )
    if reason in {"receipt-missing", "receipt-empty", "receipt-unparseable"}:
        return (
            "stop after 1 retry and report FAILED severed-stream; never report SUCCESS"
        )
    return f"stop immediately and report FAILED <unit> {reason}; no automatic retry"


def _next_action(reason: str) -> str:
    return f"resolve {reason} before treating this unit as done"


class Oracle:
    """IMP-0145 resume-oracle: a FAILED receipt must re-dispatch; SUCCESS skips."""

    def passes(self, path: Any, *, root: Any = None) -> Verdict:
        import json
        from pathlib import Path as _P

        receipt = _P(path)
        if not receipt.is_file() or receipt.stat().st_size <= 0:
            return Verdict(
                unit_id=receipt.stem,
                ok=False,
                reason="receipt-missing",
                severed=False,
                passed_clauses=(),
                detail="missing",
            )
        try:
            text = receipt.read_text(encoding="utf-8")
            doc = json.loads(text)
        except Exception:
            return Verdict(
                unit_id=receipt.stem,
                ok=False,
                reason="receipt-unparseable",
                severed=False,
                passed_clauses=("receipt-present",),
                detail="unparseable",
            )
        uid = str(doc.get("unit_id") or receipt.stem)
        st = str(doc.get("state") or "").upper()
        if st in {"FAILED", "BLOCKED", "SEVERED", "TIMEOUT"}:
            return Verdict(
                unit_id=uid,
                ok=False,
                reason=f"state:{st}",
                severed=False,
                passed_clauses=("receipt-present", "receipt-parses"),
                detail=st,
            )
        if f"SUCCESS:{uid}" not in text and doc.get("ok") is not True:
            return Verdict(
                unit_id=uid,
                ok=False,
                reason="sentinel-absent",
                severed=False,
                passed_clauses=("receipt-present", "receipt-parses"),
                detail="sentinel",
            )
        return Verdict(
            unit_id=uid,
            ok=True,
            reason=None,
            severed=False,
            passed_clauses=CLAUSES,
            detail="",
        )

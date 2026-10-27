"""Pause/resume checkpoint runner (IMP-0131)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from agentspec.envelope import STATUS_COMPLETED, STATUS_PAUSED
from agentspec.spec import HumanCheckpoint


@dataclass
class RunResult:
    status: str
    terminal: bool
    reason: str = ""
    pause_record_path: str | None = None
    ledger_path: str | None = None


def dispatch_count(ledger: list[dict[str, Any]] | dict[str, Any], unit_id: str) -> int:
    rows = ledger if isinstance(ledger, list) else list(ledger.get("events") or [])
    return sum(1 for row in rows if row.get("event") == "dispatch" and row.get("unit_id") == unit_id)


def load_pause_record(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_checkpoint(node: Any) -> bool:
    return isinstance(node, HumanCheckpoint) or type(node).__name__ == "HumanCheckpoint"


def _node_id(node: Any) -> str:
    return str(getattr(node, "id", ""))


def run_workflow(
    workflow: Any,
    store: Path,
    *,
    resume_token: str | None = None,
    owner_response: str | None = None,
    responder: Any = None,
) -> RunResult:
    store = Path(store)
    receipts = store / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    ledger_path = store / ("ledger-resume.json" if resume_token else "ledger.json")
    events: list[dict[str, Any]] = []
    completed = {p.stem for p in receipts.glob("*.json")}

    nodes = list(getattr(workflow, "nodes", ()) or ())
    paused_at: HumanCheckpoint | None = None
    for node in nodes:
        if _is_checkpoint(node):
            token = str(getattr(node, "pause_token", ""))
            if resume_token:
                if resume_token != token:
                    continue
                if responder is not None and owner_response is None:
                    try:
                        owner_response = responder(node)
                    except Exception:
                        owner_response = None
                allowed = tuple(getattr(node, "allowed_responses", ()) or ())
                if owner_response not in allowed and owner_response is not None:
                    result = RunResult(
                        status="failed",
                        terminal=True,
                        reason="owner-response-refused",
                        ledger_path=str(ledger_path),
                    )
                    _write(ledger_path, events)
                    return result
                continue
            pause_path = store / "pause.json"
            _write(
                pause_path,
                {
                    "pause_token": token,
                    "checkpoint_id": _node_id(node),
                    "prompt_ref": getattr(node, "prompt_ref", ""),
                    "allowed_responses": list(getattr(node, "allowed_responses", ()) or ()),
                },
            )
            paused_at = node  # type: ignore[assignment]
            break
        uid = _node_id(node)
        if resume_token and uid in completed:
            events.append({"event": "skip-completed", "unit_id": uid})
            continue
        events.append({"event": "dispatch", "unit_id": uid})
        payload = getattr(node, "payload", uid)
        _write(receipts / f"{uid}.json", {"id": uid, "payload": payload, "status": "completed"})
        completed.add(uid)

    _write(ledger_path, events)
    if paused_at is not None and not resume_token:
        return RunResult(
            status=STATUS_PAUSED,
            terminal=True,
            reason="human-checkpoint",
            pause_record_path=str(store / "pause.json"),
            ledger_path=str(ledger_path),
        )
    return RunResult(
        status=STATUS_COMPLETED,
        terminal=True,
        reason="complete",
        ledger_path=str(ledger_path),
    )


@dataclass
class ParamSpec:
    name: str
    secret: bool = False
    secret_ref: str = ""


@dataclass
class RuntimeBinding:
    name: str
    kind: str
    value: str | None = None
    secret_ref: str = ""


def bind_params(
    specs: Iterable[ParamSpec],
    values: dict[str, str],
    secret_store: dict[str, str] | None = None,
) -> dict[str, RuntimeBinding]:
    del secret_store
    out: dict[str, RuntimeBinding] = {}
    for spec in specs:
        if spec.secret:
            out[spec.name] = RuntimeBinding(
                name=spec.name,
                kind="secret_ref",
                value=values.get(spec.name),
                secret_ref=spec.secret_ref,
            )
        else:
            out[spec.name] = RuntimeBinding(
                name=spec.name,
                kind="plain",
                value=values.get(spec.name, ""),
            )
    return out


def serialize_checkpoint(
    *,
    workflow_id: str,
    completed_unit_ids: tuple[str, ...] | list[str],
    receipt_hashes: dict[str, str],
    open_nodes: tuple[str, ...] | list[str],
    bindings: dict[str, RuntimeBinding],
) -> bytes:
    param_bindings: dict[str, Any] = {}
    for name, binding in bindings.items():
        if binding.kind == "secret_ref":
            param_bindings[name] = {
                "kind": "secret_ref",
                "secret_ref": binding.secret_ref,
            }
        else:
            param_bindings[name] = {"kind": "plain", "value": binding.value}
    doc = {
        "format": "agentspec.checkpoint.v1",
        "workflow_id": workflow_id,
        "completed_unit_ids": list(completed_unit_ids),
        "receipt_hashes": dict(receipt_hashes),
        "open_nodes": list(open_nodes),
        "param_bindings": param_bindings,
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_checkpoint(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load_checkpoint_bytes(path: Path) -> bytes:
    return Path(path).read_bytes()


MISSING_CODE = "CREDENTIAL_SOURCE_MISSING"


class CredentialSourceMissing(RuntimeError):
    code = MISSING_CODE


def resume(
    checkpoint: bytes,
    secret_store: dict[str, str] | None = None,
    invocation: dict[str, str] | None = None,
) -> dict[str, Any]:
    del invocation
    doc = json.loads(checkpoint.decode("utf-8"))
    bindings = doc.get("param_bindings") or {}
    acquired: dict[str, str] = {}
    store = secret_store or {}
    for name, rec in bindings.items():
        if not isinstance(rec, dict):
            continue
        if rec.get("kind") == "secret_ref":
            ref = str(rec.get("secret_ref") or "")
            if ref not in store or not store.get(ref):
                exc = CredentialSourceMissing(f"{MISSING_CODE}:{ref}")
                exc.code = f"{MISSING_CODE}:{ref}"
                raise exc
            acquired[name] = store[ref]
        elif rec.get("kind") == "plain":
            acquired[name] = str(rec.get("value") or "")
        elif rec.get("kind") == "value":
            acquired[name] = str(rec.get("value") or "")
    return acquired


def plaintext_hits(blob: bytes, secrets: dict[str, str]) -> list[str]:
    text = blob.decode("utf-8", errors="replace")
    hits = []
    for name, value in secrets.items():
        if value and value in text:
            hits.append(name)
    return hits


# --- IMP-0218: HumanCheckpoint owner gate that never busy-waits -------------------

OWNER_GATE_NO_WAIT_INVARIANTS = (
    "no input()",
    "no poll/sleep loop",
    "persist-emit-exit in one call",
)


@dataclass(frozen=True)
class OwnerQuestion:
    """ONE foundation-level question with a recommendation and a stated default.

    The owner-interaction contract: the gate presents a single question, the
    RECOMMENDED option, the tradeoff (the downside of the recommendation), and
    the DEFAULT taken if the owner does not answer. A question missing any of
    these is a decision dumped in the owner's lap, not a gate.
    """

    checkpoint_id: str
    question: str
    recommendation: str
    tradeoff: str
    default: str
    options: tuple[str, ...] = ()


def owner_gate_pause(
    checkpoint: Any,
    store: Path | str,
    question: OwnerQuestion,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist state, emit the terminal envelope carrying the exact question, return.

    NEVER waits: no ``input()``, no poll/sleep loop. The caller prints the
    envelope and exits; resume happens on a later invocation that supplies the
    pause token and the owner response. Process-count proof lives in
    command-center/p2-wave/probes/IMP-0218/probe1_no_resident_process.py.
    """
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    token = str(getattr(checkpoint, "pause_token", "") or f"cp-{question.checkpoint_id}")
    pause_record = {
        "kind": "human-checkpoint-pause",
        "checkpoint_id": question.checkpoint_id,
        "pause_token": token,
        "prompt_ref": str(getattr(checkpoint, "prompt_ref", "")),
        "allowed_responses": list(getattr(checkpoint, "allowed_responses", ()) or ()),
        "default_if_unanswered": str(
            getattr(checkpoint, "default_if_unanswered", "") or question.default
        ),
        "question": {
            "text": question.question,
            "recommendation": question.recommendation,
            "tradeoff": question.tradeoff,
            "default": question.default,
            "options": list(question.options),
        },
        "context": dict(context or {}),
        "recorded_at": _now_iso(),
        "resume": {
            "mechanism": "re-invoke run_workflow with resume_token=pause_token and owner_response",
            "pause_token": token,
        },
    }
    pause_path = store / "pause.json"
    _write(pause_path, pause_record)
    envelope = {
        "status": STATUS_PAUSED,
        "terminal": True,
        "reason": "human-checkpoint",
        "question": pause_record["question"],
        "question_text": question.question,
        "recommendation": question.recommendation,
        "tradeoff": question.tradeoff,
        "default": question.default,
        "durable_record": str(pause_path),
        "pause_token": token,
        "no_wait_invariants": list(OWNER_GATE_NO_WAIT_INVARIANTS),
    }
    envelope_path = store / "owner-envelope.json"
    _write(envelope_path, envelope)
    return envelope


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assert_no_busy_wait(source_text: str) -> dict[str, Any]:
    """AST static control: the gate source must contain no waiting CALL.

    Walks the parsed tree for Call nodes whose callee is ``input``, reads of
    ``sys.stdin``, ``time.sleep``, or a ``while True`` loop (busy poll).
    Docstring mentions are inert; only executable AST nodes count.
    """
    import ast

    banned_calls: list[str] = []
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        return {"clean": False, "banned_hits": [f"syntax-error: {exc}"], "mode": "ast"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = ""
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = f"{ast.unparse(fn.value)}.{fn.attr}" if hasattr(ast, "unparse") else fn.attr
            if name in {"input", "time.sleep", "sys.stdin.read", "sys.stdin.readline",
                        "msvcrt.kbhit", "stream.readline"}:
                banned_calls.append(f"call:{name}@line{node.lineno}")
        elif isinstance(node, ast.While):
            test = node.test
            const_true = isinstance(test, ast.Constant) and test.value is True
            if const_true:
                banned_calls.append(f"while-True@line{node.lineno}")
    return {"clean": not banned_calls, "banned_hits": banned_calls, "mode": "ast"}

"""PYTHON side of the BEHAVIOURAL parity oracle: drive the shared corpus, emit a manifest.

Mirrors ``src/behaviour.mjs`` op for op. Thin by design — every operation delegates straight
into ``agentspec``, which its own gate holds at 100% line+branch; this file only decodes the
tagged arguments, names the outcome, and writes bytes.

The manifest is written in BINARY with explicit LF (see the note in ``emit_py.py``).
Exit 0 = every op ran; a case that RAISES is a recorded ``err`` outcome, not a failure. The
comparison against the JS manifest is what fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "agentspec"))

from agentspec import wire  # noqa: E402
from agentspec.argv import build_argv, prompt_on_argv, render_cmdline  # noqa: E402
from agentspec.budget import Ledger, cost_per_success  # noqa: E402
from agentspec.canonical import dumps, loadb  # noqa: E402
from agentspec.dispatchpolicy import check_dispatch  # noqa: E402
from agentspec.envelope import ErrorDetail, Observation, validate_observation  # noqa: E402
from agentspec.oracle import RailResult, judge  # noqa: E402
from agentspec.progress import ProgressLog, classify  # noqa: E402
from agentspec.receipt import decode, missing_fields, parse_json_object, present_markers  # noqa: E402
from agentspec.retry import plan_retry, rate_limit_backoff_ms  # noqa: E402
from agentspec.spec import ReceiptSpec  # noqa: E402
from agentspec.terminal import success_line  # noqa: E402

CORPUS = HERE.parent / "fixtures" / "behaviour-corpus.json"


class BehaviourCorpusError(ValueError):
    """The corpus file or a case is malformed. Distinct from a case producing an ``err``."""


def decode_arg(node: Any) -> Any:
    """Materialise one tagged argument node. Mirrors ``decodeArg`` in src/behaviour.mjs."""
    if not isinstance(node, dict) or len(node) != 1:
        raise BehaviourCorpusError(f"arg must be a one-tag object, got {node!r}")
    tag, body = next(iter(node.items()))
    if tag == "s":
        return body
    if tag == "i":
        return int(body)
    if tag == "f":
        return float(body)
    if tag == "b":
        return body
    if tag == "n":
        return None
    if tag == "hex":
        return bytes.fromhex(body)
    if tag == "ss":
        return tuple(body)
    if tag == "kv":
        return {key: decode_arg(value) for key, value in body}
    raise BehaviourCorpusError(f"unknown arg tag {tag!r}")


def error_kind(exc: BaseException) -> str:
    """The portable name for a failure. Anything unrecognised is RE-RAISED, never recorded."""
    code = getattr(exc, "code", None)
    if isinstance(code, str):
        return code
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str):
        return reason
    if isinstance(exc, TypeError):
        return "invalid-type"
    if isinstance(exc, ValueError):
        return "invalid-value"
    raise exc


def _judge(a: dict[str, Any]) -> Any:
    verdict = judge(
        a["unit"],
        RailResult(exit_code=a["exit"], receipt_bytes=a["receipt"], wall_ms=a["wall"]),
        ReceiptSpec(
            fmt=a["fmt"],
            required_fields=a["required"],
            forbidden_markers=a["forbidden"],
        ),
    )
    return {
        "ok": verdict.ok,
        "reason": verdict.reason,
        "severed": verdict.severed,
        "passed": list(verdict.passed_clauses),
        "detail": verdict.detail,
    }


def _classify(a: dict[str, Any]) -> Any:
    classified = classify(a["text"])
    progress = isinstance(classified, ProgressLog)
    return {
        "kind": "progress" if progress else "result",
        "marker": classified.marker if progress else None,
    }


def _validate_observation(a: dict[str, Any]) -> Any:
    detail = (
        None
        if a["code"] is None
        else ErrorDetail(
            code=a["code"],
            root_cause=a["root_cause"],
            retry_instruction=a["retry_instruction"],
            stop_condition=a["stop_condition"],
        )
    )
    return list(
        validate_observation(
            Observation(
                status=a["status"],
                summary=a["summary"],
                next_actions=a["next"],
                artifacts=(),
                error=detail,
            )
        )
    )


OPS = {
    "judge": _judge,
    "missing_fields": lambda a: list(
        missing_fields(
            a["payload"], ReceiptSpec(fmt="json", required_fields=a["required"])
        )
    ),
    "present_markers": lambda a: list(
        present_markers(
            a["text"], ReceiptSpec(fmt="text", forbidden_markers=a["forbidden"])
        )
    ),
    "decode": lambda a: decode(a["receipt"]),
    "parse_json_object": lambda a: list(wire.sorted_wire(parse_json_object(a["text"]))),
    "loadb": lambda a: dumps(loadb(a["receipt"])),
    "render_cmdline": lambda a: render_cmdline(a["argv"]),
    "build_argv": lambda a: (
        build_argv(
            exe=a["exe"],
            prompt=a["prompt"],
            transport=a["transport"],
            flags=a["flags"],
            prompt_flag=a["prompt_flag"],
            prompt_path=a["prompt_path"],
        ).cmdline_len
    ),
    "prompt_on_argv": lambda a: prompt_on_argv(a["element"], a["prompt"]),
    "check_dispatch": lambda a: list(
        check_dispatch(
            background=a["background"], timeout_s=a["timeout"], awaited=a["awaited"]
        )
    ),
    "debit": lambda a: (
        Ledger(limit_micro=a["limit"])
        .debit(a["unit"], attempt=a["attempt"], micro=a["micro"])
        .spent_micro
    ),
    "cost_per_success": lambda a: cost_per_success(
        Ledger(limit_micro=a["limit"]).debit("u", attempt=1, micro=a["micro"]),
        successes=a["successes"],
    ),
    "rate_limit_backoff_ms": lambda a: rate_limit_backoff_ms(a["attempt"]),
    "plan_retry": lambda a: _plan(a),
    "success_line": lambda a: success_line(a["unit"]),
    "classify": _classify,
    "validate_observation": _validate_observation,
    "wire_is_blank": lambda a: wire.is_blank(a["text"]),
    "wire_utf16_len": lambda a: wire.utf16_len(a["text"]),
    "wire_fold_ascii_case": lambda a: wire.fold_ascii_case(a["text"]),
    "wire_is_printable_id": lambda a: wire.is_printable_id(a["text"]),
}


def _plan(a: dict[str, Any]) -> Any:
    decision = plan_retry(a["reason"], attempt=a["attempt"])
    return {
        "retry": decision.retry,
        "next": decision.next_attempt,
        "backoff": decision.backoff_ms,
    }


def run_case(entry: dict[str, Any]) -> str:
    """Return the canonical outcome text for one case."""
    if entry["op"] not in OPS:
        raise BehaviourCorpusError(f"case {entry['id']}: unknown op {entry['op']!r}")
    args = {name: decode_arg(node) for name, node in entry["args"].items()}
    try:
        return dumps({"ok": OPS[entry["op"]](args)})
    except Exception as exc:  # noqa: BLE001 - error_kind re-raises anything unrecognised
        return dumps({"err": error_kind(exc)})


def main() -> int:
    if len(sys.argv) < 2:
        print("SUCCESS:python-behaviour AST parity shell (no output path)")
        return 0
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    entries = corpus["cases"]
    if not entries:
        raise BehaviourCorpusError(
            "corpus has no cases; an empty corpus passes vacuously"
        )
    lines = [
        f"{entry['id']}\t{run_case(entry).encode('utf-8').hex()}" for entry in entries
    ]
    Path(sys.argv[1]).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    print(f"SUCCESS:python-behaviour {len(entries)} cases executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

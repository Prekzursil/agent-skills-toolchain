"""Bridge pass-through grader (lens 08 section 2.1, ``bridge-passthrough``).

Diff the raw OpenAI wire JSON before and after a bridge (``:8317``, a Space proxy, the hub's
``/v1`` face). ``tool_calls`` and every ``tool_call_id`` must survive, a ``refusal`` field must
not be flattened into ``content``, ``<tool_call>`` XML in ``content`` is the classic
flattening signature, and ``finish_reason`` must be preserved. A bridge that loses tool
calls is graded ``capability-absent`` (lock 7: a tradeoff to present, not a model failure);
anything else that changed is ``degraded``. Both fail closed (``passed`` is False).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

OK = "ok"
DEGRADED = "degraded"
CAPABILITY_ABSENT = "capability-absent"

_XML_TOOL_CALL = re.compile(r"<tool_call\b", re.IGNORECASE)


@dataclass(frozen=True)
class Report:
    passed: bool
    verdict: str
    findings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "verdict": self.verdict,
            "findings": list(self.findings),
        }


def _first_choice(response: Mapping[str, Any]) -> Mapping[str, Any]:
    choices = response.get("choices") or []
    return choices[0] if choices else {}


def _message(choice: Mapping[str, Any]) -> Mapping[str, Any]:
    return choice.get("message") or {}


def _tool_calls(message: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(message.get("tool_calls") or [])


def compare(before: Mapping[str, Any], after: Mapping[str, Any]) -> Report:
    before_choice, after_choice = _first_choice(before), _first_choice(after)
    before_msg, after_msg = _message(before_choice), _message(after_choice)
    absent: list[str] = []
    degraded: list[str] = []

    before_calls, after_calls = _tool_calls(before_msg), _tool_calls(after_msg)
    if before_calls and not after_calls:
        absent.append("tool_calls-stripped")
    elif len(before_calls) != len(after_calls):
        absent.append(f"tool_calls-count:{len(before_calls)}->{len(after_calls)}")
    after_ids = {call.get("id") for call in after_calls}
    for call in before_calls:
        if after_calls and call.get("id") not in after_ids:
            absent.append(f"tool_call_id-lost:{call.get('id')}")

    content = after_msg.get("content")
    if isinstance(content, str) and _XML_TOOL_CALL.search(content):
        absent.append("tool_calls-in-content")

    if before_msg.get("refusal") and not after_msg.get("refusal"):
        degraded.append("refusal-flattened")

    if before_choice.get("finish_reason") != after_choice.get("finish_reason"):
        degraded.append(
            f"finish_reason-changed:{before_choice.get('finish_reason')}->{after_choice.get('finish_reason')}"
        )

    if absent:
        return Report(False, CAPABILITY_ABSENT, tuple(absent + degraded))
    if degraded:
        return Report(False, DEGRADED, tuple(degraded))
    return Report(True, OK)

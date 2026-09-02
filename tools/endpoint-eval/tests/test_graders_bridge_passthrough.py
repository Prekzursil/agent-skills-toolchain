"""Golden tests for graders.bridge_passthrough (raw wire diff before/after a bridge)."""

from __future__ import annotations

import copy

from graders.bridge_passthrough import CAPABILITY_ABSENT, DEGRADED, OK, Report, compare

UPSTREAM = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "probe_echo",
                            "arguments": '{"nonce": "n1"}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
}


def bridged(**changes: object) -> dict:
    after = copy.deepcopy(UPSTREAM)
    message = after["choices"][0]["message"]
    for key, value in changes.items():
        if key == "finish_reason":
            after["choices"][0]["finish_reason"] = value
        elif value is None:
            message.pop(key, None)
        else:
            message[key] = value
    return after


def test_report_shape_and_known_good() -> None:
    report = compare(UPSTREAM, copy.deepcopy(UPSTREAM))
    assert isinstance(report, Report)
    assert report.passed is True
    assert report.verdict == OK
    assert report.findings == ()


def test_stripped_tool_calls_is_capability_absent() -> None:
    report = compare(
        UPSTREAM, bridged(tool_calls=None, content="I would call probe_echo.")
    )
    assert not report.passed
    assert report.verdict == CAPABILITY_ABSENT
    assert "tool_calls-stripped" in report.findings


def test_xml_tool_call_in_content_fails_closed() -> None:
    xml = '<tool_call>{"name": "probe_echo", "arguments": {"nonce": "n1"}}</tool_call>'
    report = compare(
        UPSTREAM, bridged(tool_calls=None, content=xml, finish_reason="stop")
    )
    assert report.verdict == CAPABILITY_ABSENT
    assert "tool_calls-in-content" in report.findings
    assert "finish_reason-changed:tool_calls->stop" in report.findings


def test_xml_in_content_even_when_tool_calls_survive_is_capability_absent() -> None:
    after = bridged(content="<tool_call>dup</tool_call>")
    report = compare(UPSTREAM, after)
    assert report.verdict == CAPABILITY_ABSENT
    assert report.findings == ("tool_calls-in-content",)


def test_tool_call_id_must_survive() -> None:
    after = copy.deepcopy(UPSTREAM)
    after["choices"][0]["message"]["tool_calls"][0]["id"] = "renamed"
    report = compare(UPSTREAM, after)
    assert report.verdict == CAPABILITY_ABSENT
    assert "tool_call_id-lost:call_abc" in report.findings


def test_tool_call_count_change_is_reported() -> None:
    after = copy.deepcopy(UPSTREAM)
    after["choices"][0]["message"]["tool_calls"].append(
        {
            "id": "call_abc",
            "type": "function",
            "function": {"name": "x", "arguments": "{}"},
        }
    )
    report = compare(UPSTREAM, after)
    assert report.verdict == CAPABILITY_ABSENT
    assert "tool_calls-count:1->2" in report.findings


REFUSAL_UPSTREAM = {
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": None,
                "refusal": "I cannot help with that.",
            },
            "finish_reason": "stop",
        }
    ]
}


def test_refusal_flattened_is_degraded() -> None:
    after = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I cannot help with that.",
                    "refusal": None,
                },
                "finish_reason": "stop",
            }
        ]
    }
    report = compare(REFUSAL_UPSTREAM, after)
    assert not report.passed
    assert report.verdict == DEGRADED
    assert report.findings == ("refusal-flattened",)


def test_refusal_preserved_is_ok() -> None:
    assert compare(REFUSAL_UPSTREAM, copy.deepcopy(REFUSAL_UPSTREAM)).verdict == OK


def test_finish_reason_change_alone_is_degraded() -> None:
    plain = {
        "choices": [
            {"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}
        ]
    }
    after = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "hi"},
                "finish_reason": "length",
            }
        ]
    }
    report = compare(plain, after)
    assert report.verdict == DEGRADED
    assert report.findings == ("finish_reason-changed:stop->length",)


def test_missing_choices_are_treated_as_empty_messages() -> None:
    report = compare({"choices": []}, {})
    assert report.verdict == OK
    report = compare(UPSTREAM, {"choices": []})
    assert report.verdict == CAPABILITY_ABSENT
    assert "tool_calls-stripped" in report.findings


def test_report_as_dict() -> None:
    report = compare(UPSTREAM, copy.deepcopy(UPSTREAM))
    assert report.as_dict() == {"passed": True, "verdict": OK, "findings": []}

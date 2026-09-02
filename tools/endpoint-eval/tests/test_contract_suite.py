"""T1 contract suite: every check, every taxonomy mapping, the fake matrix and the CLI.

The stub in ``conftest.py`` plays the endpoint; the inference-hub fake server is only
used by the tests marked ``needs_fake``, which skip while that work unit has not landed.
"""

from __future__ import annotations

import io
import json
import os
import runpy
import socket
import sys
import urllib.error
from pathlib import Path
from typing import Any

import contract_suite
import pytest
from conftest import StubOpenAI, free_port_url
from contract_suite import (
    BACKEND_AUTH,
    BACKEND_ERROR,
    BACKEND_RATE_LIMITED,
    BACKEND_UNAVAILABLE,
    CAPABILITY_ABSENT,
    CASE_NAMES,
    CREDENTIAL_MISSING,
    ECHO_SCHEMA,
    FAKE_MATRIX,
    FAKE_MODEL,
    MALFORMED_RESPONSE,
    NAME,
    PROBE_TOOL_NAME,
    TAXONOMY,
    TIMEOUT_NO_OUTPUT,
    TIMEOUT_PARTIAL,
    Case,
    Client,
    WireError,
    assemble_stream,
    classify_status,
    grade_json_reply,
    grade_tool_reply,
    grade_usage,
    load_fake_server,
    main,
    reply_parts,
    run,
    run_fake_matrix,
)

MODULE_PATH = Path(contract_suite.__file__)
FAKE_PRESENT = contract_suite.FAKE_SERVER_PATH.is_file()
needs_fake = pytest.mark.skipif(
    not FAKE_PRESENT,
    reason="inference-hub fake server not present (built by another work unit)",
)
BEARER_ENV = "ENDPOINT_EVAL_TEST_BEARER"
NONCE = "abc123def456"


def _cases(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {case["name"]: case for case in result["cases"]}


def _tool_reply(
    arguments: str | None = None,
    *,
    with_id: bool = True,
    name: str = PROBE_TOOL_NAME,
) -> dict[str, Any]:
    call: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments
            if arguments is not None
            else json.dumps({"nonce": NONCE}),
        },
    }
    if with_id:
        call["id"] = "call_1"
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": None, "tool_calls": [call]},
                "finish_reason": "tool_calls",
            }
        ]
    }


def _content_reply(content: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class FakeDouble:
    """Stand-in for ``FakeOpenAIServer``: maps profile + fault flags onto stub modes."""

    honour_faults = True

    def __init__(self, profile: str, **faults: Any) -> None:
        mode = "ok"
        if profile == "hf-router":
            mode = "401"
        elif self.honour_faults and faults.get("rate_limit_every"):
            mode = "429"
        elif self.honour_faults and faults.get("fail_every"):
            mode = "503"
        elif self.honour_faults and faults.get("malformed"):
            mode = "malformed"
        elif self.honour_faults and faults.get("drop_tool_calls"):
            mode = "drop-tool-calls"
        self.profile = profile
        self.faults = faults
        self._stub = StubOpenAI(mode)

    def start(self) -> FakeDouble:
        self._stub.start()
        return self

    def stop(self) -> None:
        self._stub.stop()

    @property
    def base_url(self) -> str:
        return self._stub.base_url


class FaultBlindDouble(FakeDouble):
    honour_faults = False


# --- constants and pure helpers --------------------------------------------------------


def test_taxonomy_is_the_contracts_nineteen_classes_and_case_names_are_fixed() -> None:
    assert len(TAXONOMY) == 19
    assert {
        BACKEND_AUTH,
        BACKEND_RATE_LIMITED,
        BACKEND_UNAVAILABLE,
        BACKEND_ERROR,
        MALFORMED_RESPONSE,
        TIMEOUT_NO_OUTPUT,
        TIMEOUT_PARTIAL,
        CREDENTIAL_MISSING,
        "HALTED",
    } <= TAXONOMY
    assert CAPABILITY_ABSENT == "capability-absent"
    assert CAPABILITY_ABSENT not in TAXONOMY
    assert CASE_NAMES == (
        "models_list",
        "echo",
        "usage",
        "tools",
        "json_schema",
        "stream",
    )
    assert [row[0] for row in FAKE_MATRIX] == [
        "healthy",
        "rate-limited",
        "unavailable",
        "malformed",
        "bridge-drop",
        "unauthenticated",
    ]
    assert {row[3] for row in FAKE_MATRIX if row[3]} == {
        BACKEND_RATE_LIMITED,
        BACKEND_UNAVAILABLE,
        MALFORMED_RESPONSE,
        CAPABILITY_ABSENT,
        BACKEND_AUTH,
    }


def test_wire_error_and_case_carry_their_fields() -> None:
    error = WireError(BACKEND_ERROR, "HTTP 418", 418)
    assert (error.error_class, error.status, str(error)) == (
        BACKEND_ERROR,
        418,
        "HTTP 418",
    )
    assert WireError(MALFORMED_RESPONSE, "x").status is None
    case = Case("echo", False, BACKEND_ERROR, "d", ("f",))
    assert case.as_dict() == {
        "name": "echo",
        "passed": False,
        "error_class": BACKEND_ERROR,
        "detail": "d",
        "findings": ["f"],
    }


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, None, BACKEND_AUTH),
        (403, {"error": {"message": "nope"}}, BACKEND_AUTH),
        (429, {"error": {"code": "rate_limit_exceeded"}}, BACKEND_RATE_LIMITED),
        (502, None, BACKEND_UNAVAILABLE),
        (503, {"error": "string-not-object"}, BACKEND_UNAVAILABLE),
        (504, {}, BACKEND_UNAVAILABLE),
        (500, {"error": {"code": 7}}, BACKEND_ERROR),
        (418, None, BACKEND_ERROR),
        (500, {"error": {"code": "HALTED"}}, "HALTED"),
        (200, {"error": {"code": "BUDGET_EXCEEDED"}}, "BUDGET_EXCEEDED"),
    ],
)
def test_classify_status_maps_http_onto_the_taxonomy(
    status: int, body: dict[str, Any] | None, expected: str
) -> None:
    assert classify_status(status, body) == expected


def test_http_error_bodies_that_are_not_json_objects_fall_back_to_the_status() -> None:
    def http_error(status: int, raw: bytes) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(
            "http://127.0.0.1/v1/x", status, "msg", None, io.BytesIO(raw)
        )

    not_json = contract_suite._http_error(http_error(500, b"<html>boom</html>"))
    assert (not_json.error_class, not_json.status) == (BACKEND_ERROR, 500)
    json_list = contract_suite._http_error(http_error(503, b"[1, 2]"))
    assert json_list.error_class == BACKEND_UNAVAILABLE
    empty = contract_suite._http_error(http_error(429, b""))
    assert empty.error_class == BACKEND_RATE_LIMITED
    coded = contract_suite._http_error(
        http_error(500, json.dumps({"error": {"code": "HALTED"}}).encode())
    )
    assert coded.error_class == "HALTED"


def test_url_error_distinguishes_connect_timeouts_from_refusals() -> None:
    timed_out = contract_suite._url_error(urllib.error.URLError(socket.timeout()))
    assert timed_out.error_class == TIMEOUT_NO_OUTPUT
    assert (
        contract_suite._url_error(
            urllib.error.URLError(TimeoutError("slow"))
        ).error_class
        == TIMEOUT_NO_OUTPUT
    )
    refused = contract_suite._url_error(urllib.error.URLError(ConnectionRefusedError()))
    assert refused.error_class == BACKEND_UNAVAILABLE
    assert "ConnectionRefusedError" in str(refused)


def test_parse_object_rejects_non_json_and_non_objects() -> None:
    assert contract_suite._parse_object(b'{"a": 1}') == {"a": 1}
    with pytest.raises(WireError) as not_json:
        contract_suite._parse_object(b"{nope")
    assert not_json.value.error_class == MALFORMED_RESPONSE
    with pytest.raises(WireError, match="not a JSON object"):
        contract_suite._parse_object(b"[1]")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": "x"},
        {"choices": []},
        {"choices": ["x"]},
        {"choices": [{"message": "x"}]},
        {"choices": [{}]},
    ],
)
def test_reply_parts_fails_closed_on_every_malformed_shape(
    body: dict[str, Any],
) -> None:
    with pytest.raises(WireError) as excinfo:
        reply_parts(body)
    assert excinfo.value.error_class == MALFORMED_RESPONSE


def test_reply_parts_returns_content_message_and_choice() -> None:
    content, message, choice = reply_parts(_content_reply("hi"))
    assert (content, message["content"], choice["message"] is message) == (
        "hi",
        "hi",
        True,
    )
    assert reply_parts(_content_reply(None))[0] is None
    assert reply_parts(_content_reply(["parts"]))[0] is None


def test_probe_tool_and_prompts_carry_the_nonce() -> None:
    tool = contract_suite.probe_tool(NONCE, "write_note")
    assert tool["function"]["name"] == "write_note"
    assert NONCE in tool["function"]["description"]
    assert tool["function"]["parameters"]["required"] == ["nonce"]
    assert f"nonce={NONCE}" in contract_suite.tool_prompt(NONCE)
    assert json.dumps({"nonce": NONCE}) in contract_suite.tool_prompt(NONCE)
    assert contract_suite.echo_prompt(NONCE).endswith(NONCE)
    assert contract_suite._chat("m", "t", tools=[]) == {
        "model": "m",
        "messages": [{"role": "user", "content": "t"}],
        "tools": [],
    }


# --- graders --------------------------------------------------------------------------


def test_grade_tool_reply_passes_a_single_matching_call_with_an_id() -> None:
    case = grade_tool_reply(_tool_reply(), NONCE)
    assert case.passed
    assert case.error_class is None
    assert "tool_call_id=call_1" in case.detail
    assert case.findings == ()


def test_grade_tool_reply_reports_every_reason() -> None:
    wrong_name = grade_tool_reply(_tool_reply(name="other"), NONCE)
    assert not wrong_name.passed
    assert any(reason.startswith("name-mismatch") for reason in wrong_name.findings)
    wrong_nonce = grade_tool_reply(_tool_reply(json.dumps({"nonce": "zzz"})), NONCE)
    assert "value-not-accepted:nonce" in wrong_nonce.findings
    no_id = grade_tool_reply(_tool_reply(with_id=False), NONCE)
    assert no_id.findings == ("tool_call_id-missing",)
    assert no_id.detail == "tool_call_id-missing"
    bad_json = grade_tool_reply(_tool_reply("{not json"), NONCE)
    assert "arguments-not-json" in bad_json.findings
    two_calls = _tool_reply()
    two_calls["choices"][0]["message"]["tool_calls"].append({"id": "call_2"})
    assert grade_tool_reply(two_calls, NONCE).findings == ("call-count:2",)


def test_grade_tool_reply_without_tool_calls_is_capability_absent() -> None:
    flattened = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '<tool_call>{"name": "probe_echo"}</tool_call>',
                },
                "finish_reason": "stop",
            }
        ]
    }
    case = grade_tool_reply(flattened, NONCE)
    assert (case.name, case.passed, case.error_class) == (
        "tools",
        False,
        CAPABILITY_ABSENT,
    )
    assert "finish_reason='stop'" in case.detail
    assert "tool_calls-stripped" in case.findings
    assert "tool_calls-in-content" in case.findings
    not_a_list = {"choices": [{"message": {"tool_calls": "x", "content": None}}]}
    assert grade_tool_reply(not_a_list, NONCE).error_class == CAPABILITY_ABSENT
    non_mapping_calls = {
        "choices": [{"message": {"tool_calls": ["x"], "content": None}}]
    }
    assert grade_tool_reply(non_mapping_calls, NONCE).error_class == CAPABILITY_ABSENT


def test_grade_json_reply_rates_content_against_the_schema() -> None:
    assert grade_json_reply(
        _content_reply(json.dumps({"echo": NONCE})), ECHO_SCHEMA
    ).passed
    none = grade_json_reply(_content_reply(None), ECHO_SCHEMA)
    assert (none.passed, none.detail) == (False, "content is not a string")
    not_json = grade_json_reply(_content_reply("{nope"), ECHO_SCHEMA)
    assert (not_json.passed, not_json.detail) == (False, "content is not JSON")
    invalid = grade_json_reply(_content_reply(json.dumps({"other": 1})), ECHO_SCHEMA)
    assert not invalid.passed
    assert "missing required echo" in invalid.detail
    assert "additional property other" in invalid.detail
    assert len(invalid.findings) == 2


def test_grade_usage_requires_three_integer_counts() -> None:
    good = {"usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}
    assert grade_usage(good).passed
    missing = grade_usage({"usage": None})
    assert (missing.passed, missing.detail) == (False, "usage missing")
    partial = grade_usage({"usage": {"prompt_tokens": True, "total_tokens": 3.0}})
    assert not partial.passed
    assert (
        partial.detail
        == "usage.prompt_tokens;usage.completion_tokens;usage.total_tokens"
    )


def test_assemble_stream_concatenates_delta_content_and_skips_junk() -> None:
    chunks: list[dict[str, Any]] = [
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "ab"}}]},
        {"choices": []},
        {"choices": "x"},
        {"choices": ["x"]},
        {"choices": [{"delta": "x"}]},
        {"choices": [{"delta": {"content": None}}]},
        {"choices": [{"delta": {"content": "c"}}]},
        {},
    ]
    assert assemble_stream(chunks) == "abc"
    assert assemble_stream([]) == ""


# --- client over the stub -------------------------------------------------------------


def test_client_sends_bearer_only_when_given_and_records_paths(
    stub: StubOpenAI,
) -> None:
    plain = Client(stub.base_url)
    body = plain.post_json("/chat/completions", contract_suite._chat("m", "hi"))
    assert body["choices"][0]["message"]["content"] == "echo:hi"
    assert stub.requests[-1]["_authorization"] is None
    with_bearer = Client(stub.base_url, bearer="value-under-test")
    with_bearer.post_json("/chat/completions", contract_suite._chat("m", "hi"))
    assert stub.requests[-1]["_authorization"] == "Bearer value-under-test"
    assert with_bearer.get_json("/models")["data"][0]["id"] == "stub-model"
    assert with_bearer.calls == ["/chat/completions", "/models"]


def test_client_maps_http_statuses_onto_the_taxonomy(stub_factory: Any) -> None:
    expectations = {
        "429": BACKEND_RATE_LIMITED,
        "503": BACKEND_UNAVAILABLE,
        "500": BACKEND_ERROR,
        "401": BACKEND_AUTH,
        "hub-code": "HALTED",
        "error-no-body": BACKEND_ERROR,
        "malformed": MALFORMED_RESPONSE,
    }
    for mode, expected in expectations.items():
        client = Client(stub_factory(mode).base_url)
        with pytest.raises(WireError) as excinfo:
            client.post_json("/chat/completions", contract_suite._chat("m", "hi"))
        assert excinfo.value.error_class == expected, mode


def test_client_reports_refused_connections_and_read_timeouts(
    stub_factory: Any,
) -> None:
    refused = Client(free_port_url(), timeout_s=2.0)
    with pytest.raises(WireError) as no_listener:
        refused.get_json("/models")
    assert no_listener.value.error_class == BACKEND_UNAVAILABLE
    with pytest.raises(WireError) as no_stream:
        refused.post_stream("/chat/completions", contract_suite._chat("m", "hi"))
    assert no_stream.value.error_class == BACKEND_UNAVAILABLE
    slow = Client(stub_factory("slow").base_url, timeout_s=0.3)
    with pytest.raises(WireError) as timed_out:
        slow.post_json("/chat/completions", contract_suite._chat("m", "hi"))
    assert timed_out.value.error_class == TIMEOUT_NO_OUTPUT
    with pytest.raises(WireError) as stream_timed_out:
        slow.post_stream("/chat/completions", contract_suite._chat("m", "hi"))
    assert stream_timed_out.value.error_class == TIMEOUT_NO_OUTPUT


def test_post_stream_collects_chunks_until_done(stub: StubOpenAI) -> None:
    client = Client(stub.base_url)
    chunks = client.post_stream("/chat/completions", contract_suite._chat("m", "hello"))
    assert stub.requests[-1]["stream"] is True
    assert assemble_stream(chunks) == "echo:hello"
    assert all(chunk["object"] == "chat.completion.chunk" for chunk in chunks)


@pytest.mark.parametrize(
    ("mode", "expected", "fragment"),
    [
        ("hang", TIMEOUT_PARTIAL, "after 1 chunks"),
        ("stream-eof", MALFORMED_RESPONSE, "without [DONE] after 1 chunks"),
        ("stream-eof-empty", MALFORMED_RESPONSE, "without [DONE]"),
        ("no-choices", MALFORMED_RESPONSE, "without [DONE] after 0 chunks"),
        ("429", BACKEND_RATE_LIMITED, "HTTP 429"),
        ("malformed", MALFORMED_RESPONSE, "without [DONE]"),
    ],
)
def test_post_stream_failure_modes(
    stub_factory: Any, mode: str, expected: str, fragment: str
) -> None:
    client = Client(stub_factory(mode).base_url, timeout_s=0.5)
    with pytest.raises(WireError) as excinfo:
        client.post_stream("/chat/completions", contract_suite._chat("m", "hello"))
    assert excinfo.value.error_class == expected
    assert fragment in str(excinfo.value)


# --- run() over the stub ---------------------------------------------------------------


def test_run_passes_every_check_against_a_healthy_endpoint(stub: StubOpenAI) -> None:
    result = run(stub.base_url, model="stub-model")
    assert result["pass_at_1"] == 1.0
    assert result["error_classes_hit"] == []
    cases = _cases(result)
    assert list(cases) == list(CASE_NAMES)
    assert cases["models_list"]["detail"] == "model_listed=True"
    assert cases["echo"]["detail"].startswith("chars=")
    assert cases["stream"]["detail"].startswith("chunks=")
    nonce = result["nonce"]
    assert len(nonce) == 12
    tool_request = next(request for request in stub.requests if "tools" in request)
    assert tool_request["tools"][0]["function"]["name"] == PROBE_TOOL_NAME
    assert nonce in tool_request["messages"][0]["content"]
    schema_request = next(
        request for request in stub.requests if "response_format" in request
    )
    assert schema_request["response_format"]["json_schema"]["strict"] is True
    stream_request = next(request for request in stub.requests if request.get("stream"))
    assert stream_request["stream_options"] == {"include_usage": True}
    assert [request["model"] for request in stub.requests] == ["stub-model"] * 4


def test_run_reports_an_unlisted_model_without_failing(stub: StubOpenAI) -> None:
    result = run(stub.base_url, model=FAKE_MODEL)
    assert result["pass_at_1"] == 1.0
    assert _cases(result)["models_list"]["detail"] == "model_listed=False"


def test_run_fails_closed_when_the_named_bearer_variable_is_unset(
    stub: StubOpenAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(BEARER_ENV, raising=False)
    result = run(stub.base_url, model="stub-model", bearer_env=BEARER_ENV)
    assert result["pass_at_1"] == 0.0
    assert result["error_classes_hit"] == [CREDENTIAL_MISSING]
    assert stub.requests == []
    for case in result["cases"]:
        assert case["error_class"] == CREDENTIAL_MISSING
        assert case["detail"] == f"{BEARER_ENV} is not set"


def test_run_sends_the_bearer_read_by_name_without_printing_it(
    stub: StubOpenAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(BEARER_ENV, "value-under-test")
    result = run(stub.base_url, model="stub-model", bearer_env=BEARER_ENV)
    assert result["pass_at_1"] == 1.0
    assert all(
        request["_authorization"] == "Bearer value-under-test"
        for request in stub.requests
    )
    assert "value-under-test" not in json.dumps(result)


@pytest.mark.parametrize(
    ("mode", "failing", "classes"),
    [
        (
            "429",
            {"echo", "usage", "tools", "json_schema", "stream"},
            [BACKEND_RATE_LIMITED],
        ),
        (
            "503",
            {"echo", "usage", "tools", "json_schema", "stream"},
            [BACKEND_UNAVAILABLE],
        ),
        ("401", {"echo", "usage", "tools", "json_schema", "stream"}, [BACKEND_AUTH]),
        (
            "malformed",
            {"echo", "usage", "tools", "json_schema", "stream"},
            [MALFORMED_RESPONSE],
        ),
        ("models-broken", {"models_list"}, [MALFORMED_RESPONSE]),
        ("models-empty", {"models_list"}, []),
        ("wrong-echo", {"echo", "stream"}, []),
        ("no-usage", {"usage"}, []),
        ("drop-tool-calls", {"tools"}, [CAPABILITY_ABSENT]),
        ("no-tool-calls", {"tools"}, [CAPABILITY_ABSENT]),
        ("bad-args", {"tools"}, []),
        ("no-call-id", {"tools"}, []),
        ("bad-json-content", {"json_schema"}, []),
        ("stream-mismatch", {"stream"}, []),
        ("stream-eof", {"stream"}, [MALFORMED_RESPONSE]),
        ("hang", {"stream"}, [TIMEOUT_PARTIAL]),
    ],
)
def test_run_isolates_each_failure_to_its_check(
    stub_factory: Any, mode: str, failing: set[str], classes: list[str]
) -> None:
    result = run(stub_factory(mode).base_url, model="stub-model", timeout_s=0.5)
    cases = _cases(result)
    assert {name for name, case in cases.items() if not case["passed"]} == failing
    assert result["error_classes_hit"] == classes
    assert result["pass_at_1"] == pytest.approx((6 - len(failing)) / 6)


def test_run_details_name_the_reason(stub_factory: Any) -> None:
    cases = _cases(run(stub_factory("wrong-echo").base_url, model="stub-model"))
    assert cases["echo"]["detail"] == "nonce not echoed"
    assert cases["stream"]["detail"].startswith("streamed text differs")
    cases = _cases(run(stub_factory("malformed").base_url, model="stub-model"))
    assert cases["usage"]["detail"] == "no echo reply to inspect"
    cases = _cases(run(stub_factory("models-empty").base_url, model="stub-model"))
    assert cases["models_list"]["detail"] == "no models listed"
    cases = _cases(run(stub_factory("no-choices").base_url, model="stub-model"))
    assert cases["echo"]["error_class"] == MALFORMED_RESPONSE
    assert cases["usage"]["detail"] == "usage missing"


def test_run_against_nothing_listening_is_backend_unavailable_everywhere() -> None:
    result = run(free_port_url(), model="stub-model", timeout_s=2.0)
    assert result["pass_at_1"] == 0.0
    assert result["error_classes_hit"] == [BACKEND_UNAVAILABLE]
    assert _cases(result)["usage"]["detail"] == "no echo reply to inspect"


# --- fake server loading and matrix -----------------------------------------------------


def test_load_fake_server_returns_none_when_the_hub_tree_lacks_the_fake(
    tmp_path: Path,
) -> None:
    assert load_fake_server(tmp_path) is None


def test_load_fake_server_imports_the_class_by_path_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "testing"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "fake_openai_v1.py").write_text(
        "class FakeOpenAIServer:\n    marker = 'tmp'\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "path", list(sys.path))
    names = ("testing", "testing.fake_openai_v1")
    saved = {name: sys.modules.pop(name, None) for name in names}
    try:
        server_class = load_fake_server(tmp_path)
        assert server_class is not None
        assert server_class.marker == "tmp"
        assert sys.path[0] == str(tmp_path)
        assert load_fake_server(tmp_path) is server_class
        assert sys.path.count(str(tmp_path)) == 1
    finally:
        for name, module in saved.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module


def test_run_fake_matrix_hits_every_expected_class_with_a_faithful_double() -> None:
    result = run_fake_matrix(FakeDouble, timeout_s=2.0)
    assert result["ok"]
    assert result["pass_at_1"] == 1.0
    assert len(result["cases"]) == len(CASE_NAMES)
    assert result["error_classes_hit"] == sorted(
        {
            BACKEND_AUTH,
            BACKEND_RATE_LIMITED,
            BACKEND_UNAVAILABLE,
            MALFORMED_RESPONSE,
            CAPABILITY_ABSENT,
        }
    )
    by_label = {row["label"]: row for row in result["matrix"]}
    assert by_label["healthy"] == {
        "label": "healthy",
        "expected": None,
        "hit": [],
        "ok": True,
    }
    assert by_label["bridge-drop"]["hit"] == [CAPABILITY_ABSENT]
    assert by_label["unauthenticated"]["hit"] == [BACKEND_AUTH]
    assert all(row["ok"] for row in result["matrix"])


def test_run_fake_matrix_flags_rows_whose_class_never_appeared() -> None:
    result = run_fake_matrix(FaultBlindDouble, timeout_s=2.0)
    assert not result["ok"]
    assert result["pass_at_1"] == 1.0
    failed = [row["label"] for row in result["matrix"] if not row["ok"]]
    assert failed == ["rate-limited", "unavailable", "malformed", "bridge-drop"]
    assert result["error_classes_hit"] == [BACKEND_AUTH]


# --- CLI --------------------------------------------------------------------------------


def test_cli_requires_a_target(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 1
    assert (
        capsys.readouterr().out == f"FAILED:{NAME} --base-url or --fake is required\n"
    )


def test_cli_success_line_against_a_healthy_base_url(
    stub: StubOpenAI, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--base-url", stub.base_url, "--model", "stub-model"]) == 0
    out = capsys.readouterr().out
    assert out == f"SUCCESS:{NAME} pass_at_1=1.00 cases=6 classes=0\n"


def test_cli_failure_line_names_the_failed_cases_and_classes(
    stub_factory: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--base-url", stub_factory("429").base_url, "--timeout-s", "2"])
    assert rc == 1
    out = capsys.readouterr().out
    assert out.startswith(f"FAILED:{NAME} pass_at_1=0.17 cases=6 classes=1 failed=")
    assert "echo:BACKEND_RATE_LIMITED" in out
    assert "usage:failed" in out


def test_cli_bearer_env_is_a_name_and_a_missing_variable_fails_closed(
    stub: StubOpenAI,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv(BEARER_ENV, raising=False)
    rc = main(["--base-url", stub.base_url, "--bearer-env", BEARER_ENV])
    assert rc == 1
    out = capsys.readouterr().out
    assert "CREDENTIAL_MISSING" in out
    assert stub.requests == []
    monkeypatch.setenv(BEARER_ENV, "value-under-test")
    assert main(["--base-url", stub.base_url, "--bearer-env", BEARER_ENV]) == 0
    assert "value-under-test" not in capsys.readouterr().out


def test_cli_fake_reports_a_missing_fake_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(contract_suite, "load_fake_server", lambda: None)
    assert main(["--fake"]) == 1
    out = capsys.readouterr().out
    assert out.startswith(f"FAILED:{NAME} fake-server-missing ")
    assert out.rstrip().endswith("fake_openai_v1.py")


def test_cli_fake_runs_the_matrix_and_prints_the_t1_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(contract_suite, "load_fake_server", lambda: FakeDouble)
    assert main(["--fake", "--timeout-s", "2"]) == 0
    assert (
        capsys.readouterr().out == f"SUCCESS:{NAME} pass_at_1=1.00 cases=6 classes=5\n"
    )
    monkeypatch.setattr(contract_suite, "load_fake_server", lambda: FaultBlindDouble)
    assert main(["--fake", "--timeout-s", "2"]) == 1
    out = capsys.readouterr().out
    assert out == (
        f"FAILED:{NAME} pass_at_1=1.00 cases=6 classes=1 "
        "failed=rate-limited,unavailable,malformed,bridge-drop\n"
    )


def test_module_entry_point_runs_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["contract_suite.py"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(MODULE_PATH), run_name="__main__")
    assert excinfo.value.code == 1
    assert capsys.readouterr().out.startswith(f"FAILED:{NAME} ")


# --- against the real fake (skipped until it lands) -------------------------------------


@needs_fake
def test_real_fake_matrix_passes_t1() -> None:
    server_class = load_fake_server()
    assert server_class is not None
    result = run_fake_matrix(server_class, timeout_s=10.0)
    assert result["ok"], result["matrix"]
    assert result["pass_at_1"] == 1.0
    assert {
        BACKEND_AUTH,
        BACKEND_RATE_LIMITED,
        BACKEND_UNAVAILABLE,
        MALFORMED_RESPONSE,
        CAPABILITY_ABSENT,
    } <= set(result["error_classes_hit"])


@needs_fake
def test_real_fake_cli_prints_the_success_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--fake"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"SUCCESS:{NAME} pass_at_1=1.00 cases=6 classes=")


def test_environment_never_leaks_into_results(stub: StubOpenAI) -> None:
    result = run(stub.base_url, model="stub-model")
    dumped = json.dumps(result)
    for name, value in os.environ.items():
        if name.endswith(("_KEY", "_TOKEN", "_SECRET")) and len(value) >= 8:
            assert value not in dumped

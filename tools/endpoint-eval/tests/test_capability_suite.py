"""T2/T3 capability suite: probes, estimators, decisions, the live refusal and the CLI.

The stub in ``conftest.py`` plays the endpoint; scripted trials exercise the estimator and
decision arithmetic without a wire at all; the inference-hub fake server is only used by
the tests marked ``needs_fake``, which skip while that work unit has not landed.
"""

from __future__ import annotations

import base64
import json
import runpy
import struct
import sys
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, ClassVar

import capability_suite
import pytest
from capability_suite import (
    CHAT,
    CONTEXT_CHARS,
    CRASH_CLASSES,
    DEFAULT_K,
    DEFAULT_N,
    JSON_SCHEMAS,
    LIVE_ENV,
    NAME,
    PIXELS,
    PROBES,
    TOOL_CHOICES,
    TOOL_NAMES,
    Client,
    LiveDisabledError,
    Probe,
    data_uri,
    haystack,
    is_loopback,
    main,
    needle_prompt,
    png_1x1,
    run,
    run_probe,
    summary_line,
)
from conftest import StubOpenAI
from contract_suite import (
    BACKEND_AUTH,
    BACKEND_RATE_LIMITED,
    BACKEND_UNAVAILABLE,
    CREDENTIAL_MISSING,
    FAKE_MODEL,
    MALFORMED_RESPONSE,
    TIMEOUT_NO_OUTPUT,
    TIMEOUT_PARTIAL,
    WireError,
)
from graders.passk import (
    CRASH,
    DISCARD,
    INSUFFICIENT,
    KEEP,
    T2_PASS_AT_3,
    T3_PASS_AT_3,
)

MODULE_PATH = Path(capability_suite.__file__)
FAKE_PRESENT = capability_suite.FAKE_SERVER_PATH.is_file()
needs_fake = pytest.mark.skipif(
    not FAKE_PRESENT,
    reason="inference-hub fake server not present (built by another work unit)",
)
BEARER_ENV = "ENDPOINT_EVAL_TEST_BEARER"
NONCE = "abc123def456"
UNUSED_URL = "http://127.0.0.1:1/v1"
REMOTE_URL = "https://api.example.com/v1"
PROBE_NAMES = (
    "tools_roundtrip",
    "tool_choice_required",
    "json_schema_native",
    "vision_base64",
    "usage_reported",
    "reasoning_effort_low",
    "reasoning_effort_high",
    "context_probe_8k",
    "context_probe_32k",
    "tool_call_id_roundtrip",
)
GATED = {
    "tools_roundtrip",
    "tool_choice_required",
    "json_schema_native",
    "usage_reported",
    "tool_call_id_roundtrip",
}
REQUESTS_PER_FULL_RUN = 88
Trial = Callable[[Client, str, int, str], bool]


def _content_reply(content: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _report(decision: str, pass_at_3: float, pass_hat_3: float) -> dict[str, Any]:
    return {"decision": decision, "pass_at_3": pass_at_3, "pass_hat_3": pass_hat_3}


def _scripted(outcomes: Sequence[bool | WireError]) -> tuple[Trial, list[str]]:
    """A trial replaying ``outcomes`` cyclically (raising the WireErrors) that logs nonces."""
    seen: list[str] = []

    def trial(client: Client, model: str, item: int, nonce: str) -> bool:
        seen.append(nonce)
        outcome = outcomes[(len(seen) - 1) % len(outcomes)]
        if isinstance(outcome, WireError):
            raise outcome
        return outcome

    return trial, seen


def _probe(trial: Trial, items: int = 1, gate: bool = False) -> Probe:
    return Probe("scripted", items, gate, trial, "scripted outcomes")


def _named(name: str) -> Probe:
    return next(probe for probe in PROBES if probe.name == name)


def _png_chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    chunks: list[tuple[bytes, bytes]] = []
    offset = 8
    while offset < len(png):
        (length,) = struct.unpack(">I", png[offset : offset + 4])
        kind = png[offset + 4 : offset + 8]
        data = png[offset + 8 : offset + 8 + length]
        (crc,) = struct.unpack(">I", png[offset + 8 + length : offset + 12 + length])
        assert crc == zlib.crc32(kind + data) & 0xFFFFFFFF
        chunks.append((kind, data))
        offset += 12 + length
    return chunks


class FakeDouble:
    """Stand-in for ``FakeOpenAIServer`` with the constructor and lifecycle the CLI uses."""

    instances: ClassVar[list[FakeDouble]] = []

    def __init__(self, profile: str = "openai", **faults: Any) -> None:
        self.profile = profile
        self.faults = faults
        self.stopped = False
        self._stub = StubOpenAI("ok")
        FakeDouble.instances.append(self)

    def start(self) -> FakeDouble:
        self._stub.start()
        return self

    def stop(self) -> None:
        self._stub.stop()
        self.stopped = True

    @property
    def base_url(self) -> str:
        return self._stub.base_url

    @property
    def requests(self) -> list[dict[str, Any]]:
        return self._stub.requests


# --- definitions ------------------------------------------------------------------------


def test_probe_set_is_the_t2_t3_definition() -> None:
    assert tuple(probe.name for probe in PROBES) == PROBE_NAMES
    by_name = {probe.name: probe for probe in PROBES}
    assert by_name["tools_roundtrip"].items == len(TOOL_NAMES) == 5
    assert by_name["tool_choice_required"].items == len(TOOL_CHOICES) == 3
    assert by_name["json_schema_native"].items == len(JSON_SCHEMAS) == 5
    assert by_name["vision_base64"].items == len(PIXELS) == 2
    assert {name for name, probe in by_name.items() if probe.reliability_gate} == GATED
    assert all(probe.description for probe in PROBES)
    assert sum(probe.items for probe in PROBES) * DEFAULT_N + 4 == REQUESTS_PER_FULL_RUN
    assert CRASH_CLASSES == {
        BACKEND_RATE_LIMITED,
        BACKEND_UNAVAILABLE,
        BACKEND_AUTH,
        TIMEOUT_NO_OUTPUT,
        TIMEOUT_PARTIAL,
        CREDENTIAL_MISSING,
    }
    assert MALFORMED_RESPONSE not in CRASH_CLASSES
    assert (DEFAULT_K, DEFAULT_N) == (3, 4)
    assert CONTEXT_CHARS == {"8k": 24_000, "32k": 96_000}
    assert all("echo" in schema["required"] for schema in JSON_SCHEMAS)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:8000/v1", True),
        ("http://127.9.9.9/v1", True),
        ("http://localhost:11434/v1", True),
        ("http://[::1]:8000/v1", True),
        ("http://0.0.0.0:8000/v1", False),
        ("http://localhost.example.com/v1", False),
        (REMOTE_URL, False),
        ("http://10.0.0.5:8000/v1", False),
        ("not a url", False),
        ("", False),
    ],
)
def test_is_loopback_only_trusts_loopback_hosts(url: str, expected: bool) -> None:
    assert is_loopback(url) is expected


def test_png_1x1_is_a_well_formed_rgb_png() -> None:
    for rgb in PIXELS:
        png = png_1x1(rgb)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        chunks = _png_chunks(png)
        assert [kind for kind, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
        assert chunks[0][1] == struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        assert zlib.decompress(chunks[1][1]) == b"\x00" + bytes(rgb)
        assert chunks[2][1] == b""
    assert png_1x1(PIXELS[0]) != png_1x1(PIXELS[1])


def test_data_uri_round_trips_the_png() -> None:
    png = png_1x1((1, 2, 3))
    uri = data_uri(png)
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == png


def test_haystack_plants_the_needle_at_depth_and_meets_the_size() -> None:
    text = haystack(2_000, "NEEDLE")
    lines = text.split("\n")
    assert len(text) >= 2_000
    assert lines.count("NEEDLE") == 1
    filler = [line for line in lines if line != "NEEDLE"]
    assert lines.index("NEEDLE") == len(filler) // 2
    assert filler[0].startswith("Rule 1: ")
    assert filler[-1].startswith(f"Rule {len(filler)}: ")
    assert haystack(500, "N", depth=0.0).split("\n")[0] == "N"
    assert haystack(500, "N", depth=1.0).split("\n")[-1] == "N"
    assert haystack(0, "N") == "N"


def test_needle_prompt_sizes_the_haystack_and_asks_for_the_nonce() -> None:
    small = needle_prompt("8k", NONCE)
    large = needle_prompt("32k", NONCE)
    assert f"The secret nonce is {NONCE}." in small
    assert small.endswith("Reply with the nonce only.")
    assert CONTEXT_CHARS["8k"] <= len(small) < CONTEXT_CHARS["32k"] <= len(large)
    assert small.count(NONCE) == 1
    with pytest.raises(KeyError):
        needle_prompt("1m", NONCE)


def test_request_helpers_shape_the_wire_payload() -> None:
    user = capability_suite._user("hi")
    assert user == {"role": "user", "content": "hi"}
    assert capability_suite._chat("m", [user], tools=[]) == {
        "model": "m",
        "messages": [user],
        "tools": [],
    }
    assert capability_suite._echoes(_content_reply(f"echo:{NONCE}"), NONCE)
    assert not capability_suite._echoes(_content_reply("other"), NONCE)
    assert not capability_suite._echoes(_content_reply(None), NONCE)
    assert capability_suite._mean([]) == 0.0
    assert capability_suite._mean([1.0, 0.0]) == 0.5


# --- trials over the stub ---------------------------------------------------------------


def test_trials_pass_against_a_healthy_stub_and_shape_their_requests(
    stub: StubOpenAI,
) -> None:
    client = Client(stub.base_url)
    assert capability_suite.trial_tools_roundtrip(client, "m", 1, NONCE)
    assert stub.requests[-1]["tools"][0]["function"]["name"] == TOOL_NAMES[1]
    assert capability_suite.trial_tool_choice_required(client, "m", 1, NONCE)
    assert stub.requests[-1]["tool_choice"] == TOOL_CHOICES[1][1]
    assert capability_suite.trial_json_schema_native(client, "m", 2, NONCE)
    assert stub.requests[-1]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "echo_2", "strict": True, "schema": JSON_SCHEMAS[2]},
    }
    assert capability_suite.trial_vision_base64(client, "m", 1, NONCE)
    parts = stub.requests[-1]["messages"][0]["content"]
    assert parts[1]["image_url"]["url"] == data_uri(png_1x1(PIXELS[1]))
    assert f"nonce={NONCE}" in parts[0]["text"]
    assert capability_suite.trial_usage_reported(client, "m", 0, NONCE)
    assert capability_suite._reasoning_trial("high")(client, "m", 0, NONCE)
    assert stub.requests[-1]["reasoning_effort"] == "high"
    assert capability_suite._context_trial("8k")(client, "m", 0, NONCE)
    assert len(stub.requests[-1]["messages"][0]["content"]) >= CONTEXT_CHARS["8k"]
    assert capability_suite.trial_tool_call_id_roundtrip(client, "m", 0, NONCE)
    follow_up = stub.requests[-1]["messages"]
    assert [message["role"] for message in follow_up] == [
        "user",
        "assistant",
        "tool",
        "user",
    ]
    assert follow_up[1]["tool_calls"][0]["id"] == "call_1"
    assert follow_up[1]["content"] is None
    assert follow_up[2]["tool_call_id"] == "call_1"
    assert json.loads(follow_up[2]["content"]) == {"nonce": NONCE, "status": "ok"}
    assert "tools" not in stub.requests[-1]
    assert client.calls == [CHAT] * 9


def test_trials_fail_closed_on_degraded_replies(stub_factory: Any) -> None:
    dropped = Client(stub_factory("drop-tool-calls").base_url)
    assert not capability_suite.trial_tools_roundtrip(dropped, "m", 0, NONCE)
    assert not capability_suite.trial_tool_choice_required(dropped, "m", 0, NONCE)
    no_id_stub = stub_factory("no-call-id")
    no_id = Client(no_id_stub.base_url)
    assert not capability_suite.trial_tool_call_id_roundtrip(no_id, "m", 0, NONCE)
    assert len(no_id_stub.requests) == 1
    bad_json = Client(stub_factory("bad-json-content").base_url)
    assert not capability_suite.trial_json_schema_native(bad_json, "m", 0, NONCE)
    wrong = Client(stub_factory("wrong-echo").base_url)
    assert not capability_suite.trial_vision_base64(wrong, "m", 0, NONCE)
    assert not capability_suite._reasoning_trial("low")(wrong, "m", 0, NONCE)
    assert not capability_suite._context_trial("8k")(wrong, "m", 0, NONCE)
    assert not capability_suite.trial_usage_reported(wrong, "m", 0, NONCE)
    no_usage = Client(stub_factory("no-usage").base_url)
    assert not capability_suite.trial_usage_reported(no_usage, "m", 0, NONCE)


def test_trials_let_wire_errors_propagate(stub_factory: Any) -> None:
    client = Client(stub_factory("429").base_url)
    with pytest.raises(WireError) as excinfo:
        capability_suite.trial_tools_roundtrip(client, "m", 0, NONCE)
    assert excinfo.value.error_class == BACKEND_RATE_LIMITED


# --- run_probe: estimators and the decision table ---------------------------------------


def test_run_probe_scores_every_item_with_fresh_nonces() -> None:
    trial, seen = _scripted([True])
    report = run_probe(
        _probe(trial, items=3, gate=True),
        Client(UNUSED_URL),
        "m",
        k=3,
        n=4,
        pass_at_k_target=T2_PASS_AT_3,
    )
    assert report == {
        "pass_at_1": 1.0,
        "pass_at_3": 1.0,
        "pass_hat_3": 1.0,
        "n": 4,
        "k": 3,
        "items": 3,
        "items_completed": 3,
        "reliability_gate": True,
        "decision": KEEP,
        "error_classes_hit": [],
    }
    assert len(seen) == 12
    assert len(set(seen)) == 12
    assert all(len(nonce) == 12 for nonce in seen)


def test_run_probe_reliability_gate_separates_capability_from_reliability() -> None:
    trial, _ = _scripted([True, False])
    ungated = run_probe(
        _probe(trial), Client(UNUSED_URL), "m", k=3, n=4, pass_at_k_target=T2_PASS_AT_3
    )
    assert (ungated["pass_at_1"], ungated["pass_at_3"], ungated["pass_hat_3"]) == (
        0.5,
        1.0,
        0.0,
    )
    assert ungated["decision"] == KEEP
    trial, _ = _scripted([True, False])
    gated = run_probe(
        _probe(trial, gate=True),
        Client(UNUSED_URL),
        "m",
        k=3,
        n=4,
        pass_at_k_target=T2_PASS_AT_3,
    )
    assert (gated["pass_at_3"], gated["pass_hat_3"]) == (1.0, 0.0)
    assert gated["decision"] == DISCARD


def test_run_probe_tier_targets_decide_between_t2_and_t3() -> None:
    outcomes = [True, True, False, False, False, False]
    for target, expected in ((T2_PASS_AT_3, DISCARD), (T3_PASS_AT_3, KEEP)):
        trial, _ = _scripted(outcomes)
        report = run_probe(
            _probe(trial), Client(UNUSED_URL), "m", k=3, n=6, pass_at_k_target=target
        )
        assert report["pass_at_3"] == pytest.approx(0.8)
        assert report["decision"] == expected


def test_run_probe_with_too_few_trials_is_insufficient() -> None:
    trial, _ = _scripted([True])
    report = run_probe(
        _probe(trial), Client(UNUSED_URL), "m", k=3, n=3, pass_at_k_target=T2_PASS_AT_3
    )
    assert (report["pass_at_3"], report["decision"]) == (1.0, INSUFFICIENT)


def test_run_probe_counts_non_crash_wire_errors_as_failures(stub_factory: Any) -> None:
    client = Client(stub_factory("malformed").base_url)
    report = run_probe(
        _named("usage_reported"), client, "m", k=3, n=4, pass_at_k_target=T2_PASS_AT_3
    )
    assert (report["pass_at_1"], report["pass_at_3"], report["pass_hat_3"]) == (
        0.0,
        0.0,
        0.0,
    )
    assert report["decision"] == DISCARD
    assert report["items_completed"] == 1
    assert report["error_classes_hit"] == [MALFORMED_RESPONSE]
    assert len(client.calls) == 4


def test_run_probe_stops_sampling_at_the_first_crash_class(stub_factory: Any) -> None:
    client = Client(stub_factory("429").base_url)
    report = run_probe(
        _named("tools_roundtrip"), client, "m", k=3, n=4, pass_at_k_target=T2_PASS_AT_3
    )
    assert report["decision"] == CRASH
    assert report["items_completed"] == 0
    assert report["error_classes_hit"] == [BACKEND_RATE_LIMITED]
    assert (report["pass_at_1"], report["pass_at_3"], report["pass_hat_3"]) == (
        0.0,
        0.0,
        0.0,
    )
    assert len(client.calls) == 1


def test_run_probe_keeps_completed_items_when_a_later_item_crashes() -> None:
    trial, seen = _scripted(
        [True, True, True, True, WireError(BACKEND_UNAVAILABLE, "HTTP 503", 503)]
    )
    report = run_probe(
        _probe(trial, items=3, gate=True),
        Client(UNUSED_URL),
        "m",
        k=3,
        n=4,
        pass_at_k_target=T2_PASS_AT_3,
    )
    assert report["decision"] == CRASH
    assert report["items_completed"] == 1
    assert report["pass_at_3"] == 1.0
    assert report["error_classes_hit"] == [BACKEND_UNAVAILABLE]
    assert len(seen) == 5


def test_run_probe_treats_a_read_timeout_as_a_crash(stub_factory: Any) -> None:
    client = Client(stub_factory("slow").base_url, timeout_s=0.3)
    report = run_probe(
        _named("usage_reported"), client, "m", k=3, n=4, pass_at_k_target=T2_PASS_AT_3
    )
    assert report["decision"] == CRASH
    assert report["error_classes_hit"] == [TIMEOUT_NO_OUTPUT]


# --- run() ------------------------------------------------------------------------------


def test_run_rejects_impossible_k_and_n() -> None:
    with pytest.raises(ValueError, match="need 1 <= k <= n, got k=0 n=4"):
        run(UNUSED_URL, "m", k=0, n=4, probes=())
    with pytest.raises(ValueError, match="k=5 n=4"):
        run(UNUSED_URL, "m", k=5, n=4, probes=())


def test_run_refuses_non_loopback_targets_unless_marked_live() -> None:
    with pytest.raises(LiveDisabledError, match=f"owner-run behind {LIVE_ENV}=1"):
        run(REMOTE_URL, "m", probes=())
    result = run(REMOTE_URL, "m", live=True, probes=())
    assert result["probes"] == {}
    assert result["requests"] == 0


def test_run_fails_closed_on_a_named_but_unset_bearer(
    stub: StubOpenAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(BEARER_ENV, raising=False)
    with pytest.raises(WireError) as excinfo:
        run(stub.base_url, "m", bearer_env=BEARER_ENV)
    assert excinfo.value.error_class == CREDENTIAL_MISSING
    assert str(excinfo.value) == f"{BEARER_ENV} is not set"
    assert stub.requests == []


def test_run_sends_the_bearer_read_by_name_and_never_prints_it(
    stub: StubOpenAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(BEARER_ENV, "value-under-test")
    result = run(
        stub.base_url, "m", bearer_env=BEARER_ENV, probes=[_named("usage_reported")]
    )
    assert stub.requests
    assert all(
        request["_authorization"] == "Bearer value-under-test"
        for request in stub.requests
    )
    assert "value-under-test" not in json.dumps(result)
    assert result["probes"]["usage_reported"]["decision"] == KEEP


def test_run_keeps_every_probe_against_a_healthy_stub(stub: StubOpenAI) -> None:
    result = run(stub.base_url, "stub-model")
    assert result["model"] == "stub-model"
    assert (result["k"], result["n"], result["hosted"]) == (3, 4, False)
    assert result["pass_at_k_target"] == T2_PASS_AT_3
    assert tuple(result["probes"]) == PROBE_NAMES
    assert {report["decision"] for report in result["probes"].values()} == {KEEP}
    assert result["requests"] == len(stub.requests) == REQUESTS_PER_FULL_RUN
    assert all(request["model"] == "stub-model" for request in stub.requests)
    assert all(
        report["n"] == 4 and report["k"] == 3 for report in result["probes"].values()
    )


def test_run_hosted_applies_the_t3_target(stub: StubOpenAI) -> None:
    result = run(stub.base_url, "m", hosted=True, probes=())
    assert result["hosted"] is True
    assert result["pass_at_k_target"] == T3_PASS_AT_3


def test_summary_line_reports_minima_and_names_the_not_kept() -> None:
    kept = {"probes": {"a": _report(KEEP, 1.0, 1.0), "b": _report(KEEP, 0.95, 1.0)}}
    assert summary_line(kept) == (
        True,
        "probes=2 pass_at_3_min=0.95 pass_hat_3_min=1.00",
    )
    mixed = {
        "probes": {
            "a": _report(KEEP, 1.0, 1.0),
            "b": _report(DISCARD, 0.75, 0.25),
            "c": _report(CRASH, 0.0, 0.0),
        }
    }
    assert summary_line(mixed) == (
        False,
        "probes=3 pass_at_3_min=0.00 pass_hat_3_min=0.00 not_kept=b:discard,c:crash",
    )


# --- CLI --------------------------------------------------------------------------------


def test_cli_requires_a_target(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 1
    assert (
        capsys.readouterr().out == f"FAILED:{NAME} --base-url or --fake is required\n"
    )


def test_cli_success_line_against_a_healthy_stub(
    stub: StubOpenAI, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--base-url", stub.base_url, "--model", "stub-model"]) == 0
    assert capsys.readouterr().out == (
        f"SUCCESS:{NAME} probes=10 pass_at_3_min=1.00 pass_hat_3_min=1.00\n"
    )


def test_cli_failure_line_names_the_probes_not_kept(
    stub_factory: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--base-url", stub_factory("no-usage").base_url]) == 1
    assert capsys.readouterr().out == (
        f"FAILED:{NAME} probes=10 pass_at_3_min=0.00 pass_hat_3_min=0.00 "
        "not_kept=usage_reported:discard\n"
    )


def test_cli_too_few_trials_is_insufficient_everywhere(
    stub: StubOpenAI, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--base-url", stub.base_url, "--n", "3", "--k", "3"]) == 1
    out = capsys.readouterr().out
    assert out.startswith(f"FAILED:{NAME} probes=10 ")
    assert out.count(f":{INSUFFICIENT}") == 10


def test_cli_rate_limits_are_crashes_never_scores(
    stub_factory: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--base-url", stub_factory("503").base_url]) == 1
    out = capsys.readouterr().out
    assert out.count(f":{CRASH}") == 10
    assert f":{DISCARD}" not in out


def test_cli_refuses_a_non_loopback_target_without_the_live_marker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(LIVE_ENV, raising=False)
    assert main(["--base-url", REMOTE_URL]) == 1
    assert capsys.readouterr().out == (
        f"FAILED:{NAME} live-disabled (export {LIVE_ENV}=1 for an owner-run live pass)\n"
    )


def test_cli_live_marker_and_flags_reach_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[dict[str, Any]] = []

    def recording_run(base_url: str, model: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"base_url": base_url, "model": model, **kwargs})
        return {"probes": {"p": _report(KEEP, 1.0, 1.0)}}

    monkeypatch.setattr(capability_suite, "run", recording_run)
    monkeypatch.setenv(LIVE_ENV, "1")
    argv = [
        "--base-url",
        REMOTE_URL,
        "--model",
        "m",
        "--hosted",
        "--bearer-env",
        BEARER_ENV,
        "--timeout-s",
        "5",
        "--n",
        "6",
        "--k",
        "2",
    ]
    assert main(argv) == 0
    assert calls == [
        {
            "base_url": REMOTE_URL,
            "model": "m",
            "k": 2,
            "n": 6,
            "live": True,
            "hosted": True,
            "bearer_env": BEARER_ENV,
            "timeout_s": 5.0,
        }
    ]
    assert capsys.readouterr().out == (
        f"SUCCESS:{NAME} probes=1 pass_at_3_min=1.00 pass_hat_3_min=1.00\n"
    )
    monkeypatch.setenv(LIVE_ENV, "0")
    assert main(["--base-url", REMOTE_URL]) == 0
    assert calls[-1]["live"] is False
    assert calls[-1]["hosted"] is False


def test_cli_reports_value_and_wire_errors(
    stub: StubOpenAI,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--base-url", stub.base_url, "--k", "0"]) == 1
    assert capsys.readouterr().out == f"FAILED:{NAME} need 1 <= k <= n, got k=0 n=4\n"
    monkeypatch.delenv(BEARER_ENV, raising=False)
    assert main(["--base-url", stub.base_url, "--bearer-env", BEARER_ENV]) == 1
    assert capsys.readouterr().out == f"FAILED:{NAME} {BEARER_ENV} is not set\n"
    assert stub.requests == []


def test_cli_fake_reports_a_missing_fake_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(capability_suite, "load_fake_server", lambda: None)
    assert main(["--fake"]) == 1
    out = capsys.readouterr().out
    assert out.startswith(f"FAILED:{NAME} fake-server-missing ")
    assert out.rstrip().endswith("fake_openai_v1.py")


def test_cli_fake_starts_the_server_runs_every_probe_and_stops_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(capability_suite, "load_fake_server", lambda: FakeDouble)
    assert main(["--fake", "--n", "4", "--k", "3"]) == 0
    assert capsys.readouterr().out == (
        f"SUCCESS:{NAME} probes=10 pass_at_3_min=1.00 pass_hat_3_min=1.00\n"
    )
    server = FakeDouble.instances[-1]
    assert (server.profile, server.faults, server.stopped) == ("openai", {}, True)
    assert len(server.requests) == REQUESTS_PER_FULL_RUN
    assert all(request["model"] == FAKE_MODEL for request in server.requests)


def test_module_entry_point_runs_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["capability_suite.py"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(MODULE_PATH), run_name="__main__")
    assert excinfo.value.code == 1
    assert (
        capsys.readouterr().out == f"FAILED:{NAME} --base-url or --fake is required\n"
    )


# --- against the real fake (skipped until it lands) -------------------------------------


@needs_fake
def test_real_fake_keeps_every_probe() -> None:
    server_class = capability_suite.load_fake_server()
    assert server_class is not None
    server = server_class("openai").start()
    try:
        result = run(server.base_url, FAKE_MODEL, k=3, n=4)
    finally:
        server.stop()
    assert {report["decision"] for report in result["probes"].values()} == {KEEP}
    assert result["requests"] == REQUESTS_PER_FULL_RUN


@needs_fake
def test_real_fake_bridge_drop_discards_the_tool_probes_without_crashing() -> None:
    server_class = capability_suite.load_fake_server()
    assert server_class is not None
    server = server_class("openai", drop_tool_calls=True).start()
    try:
        result = run(server.base_url, FAKE_MODEL, k=3, n=4)
    finally:
        server.stop()
    decisions = {name: report["decision"] for name, report in result["probes"].items()}
    assert {name for name, verdict in decisions.items() if verdict == DISCARD} == {
        "tools_roundtrip",
        "tool_choice_required",
        "tool_call_id_roundtrip",
    }
    assert set(decisions.values()) == {KEEP, DISCARD}


@needs_fake
def test_real_fake_rate_limit_is_a_crash_on_every_probe() -> None:
    server_class = capability_suite.load_fake_server()
    assert server_class is not None
    server = server_class("openai", rate_limit_every=1).start()
    try:
        result = run(server.base_url, FAKE_MODEL, k=3, n=4)
    finally:
        server.stop()
    reports = result["probes"].values()
    assert {report["decision"] for report in reports} == {CRASH}
    assert all(
        report["error_classes_hit"] == [BACKEND_RATE_LIMITED] for report in reports
    )
    assert result["requests"] == len(PROBES)


@needs_fake
def test_real_fake_cli_prints_the_success_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--fake", "--n", "4", "--k", "3"]) == 0
    assert capsys.readouterr().out == (
        f"SUCCESS:{NAME} probes=10 pass_at_3_min=1.00 pass_hat_3_min=1.00\n"
    )

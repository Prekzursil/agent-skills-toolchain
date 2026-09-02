"""Pin the fake OpenAI-compatible server's contract (BUILD-CONTRACT section 5).

Every profile behaviour and every fault flag is reproduced here with plain
``urllib`` so the later suites (hub, probes, eval harness) can trust the fixture
independently of the code they test.
"""

from __future__ import annotations

import io
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import pytest

from testing import fake_openai_v1
from testing.fake_openai_v1 import (
    AUTH2API_MODEL_IDS,
    HANG_CAP_S,
    OLLAMA_MODELS,
    PROFILES,
    FakeOpenAIServer,
    _hold_connection,
    _stream_sse,
    _write,
    main,
)

FAKE_BEARER = "FAKE_BEARER_NOT_A_TOKEN"
BEARER = {"Authorization": f"Bearer {FAKE_BEARER}"}
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "probe_echo",
            "parameters": {
                "type": "object",
                "properties": {"nonce": {"type": "string"}},
            },
        },
    }
]
JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {"name": "echo", "schema": {"type": "object"}},
}


def _request(
    url: str,
    *,
    method: str = "GET",
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, str], bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (
                resp.status,
                {k.lower(): v for k, v in resp.headers.items()},
                resp.read(),
            )
    except urllib.error.HTTPError as err:
        return err.code, {k.lower(): v for k, v in err.headers.items()}, err.read()


def _post(
    url: str, body: Any, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], Any]:
    status, hdrs, raw = _request(url, method="POST", body=body, headers=headers)
    return status, hdrs, json.loads(raw)


def _chat(text: str, model: str = "gpt-5.2", **extra: Any) -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "user", "content": text}], **extra}


def _events(raw: bytes) -> list[Any]:
    events: list[Any] = []
    for block in raw.decode("utf-8").split("\n\n"):
        if block.startswith("data: "):
            payload = block[len("data: ") :]
            events.append(payload if payload == "[DONE]" else json.loads(payload))
    return events


def _stream(url: str, body: dict[str, Any], headers: dict[str, str] | None = None):
    return _request(url, method="POST", body={**body, "stream": True}, headers=headers)


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.02)


# --- request log and lifecycle ------------------------------------------------


def test_models_list_and_request_log_never_store_the_authorization_value(fake_openai):
    status, headers, raw = _request(fake_openai.base_url + "/models", headers=BEARER)
    assert status == 200
    body = json.loads(raw)
    assert body["object"] == "list"
    assert "gpt-5.2" in {model["id"] for model in body["data"]}
    assert all(model["object"] == "model" for model in body["data"])
    assert headers["x-fake-generation"] == "1"

    entry = fake_openai.requests[-1]
    assert set(entry) == {"method", "path", "headers", "json"}
    assert (entry["method"], entry["path"], entry["json"]) == (
        "GET",
        "/v1/models",
        None,
    )
    assert entry["headers"]["authorization"] == "<present>"
    assert entry["headers"]["content-type"] == "application/json"
    assert FAKE_BEARER not in json.dumps(fake_openai.requests)


def test_base_url_root_url_and_profile_validation():
    with FakeOpenAIServer() as fake:
        assert fake.profile == "openai"
        assert fake.root_url == f"http://127.0.0.1:{fake.port}"
        assert fake.base_url == fake.root_url + "/v1"
        assert fake.running
    assert not fake.running
    with pytest.raises(ValueError):
        FakeOpenAIServer("bedrock")
    assert PROFILES == ("openai", "ollama", "hf-router", "auth2api", "lmstudio")


def test_stop_refuses_connections_and_start_rebinds_the_same_port():
    fake = FakeOpenAIServer("openai").start()
    assert fake.start() is fake
    port = fake.port
    fake.stop()
    fake.stop()
    assert not fake.running
    with pytest.raises(urllib.error.URLError) as exc:
        _request(f"http://127.0.0.1:{port}/v1/models", timeout=2)
    assert isinstance(exc.value.reason, ConnectionRefusedError)

    fake.start()
    assert fake.port == port
    status, headers, _ = _request(fake.base_url + "/models")
    assert (status, headers["x-fake-generation"]) == (200, "2")
    fake.stop()


def test_restart_keeps_the_port_and_keeps_serving():
    with FakeOpenAIServer("openai", rate_limit_every=2) as fake:
        url = fake.base_url + "/chat/completions"
        port = fake.port
        assert _post(url, _chat("one"))[0] == 200
        fake.restart()
        assert (fake.port, fake.running, fake.generation) == (port, True, 2)
        status, headers, _ = _post(url, _chat("two"))
        assert (status, headers["x-fake-generation"]) == (200, "2")
        assert _post(url, _chat("three"))[0] == 429
        assert [entry["json"]["messages"][0]["content"] for entry in fake.requests] == [
            "one",
            "two",
            "three",
        ]


def test_restart_every_restarts_periodically_until_stopped():
    with FakeOpenAIServer("openai", restart_every=0.1) as fake:
        time.sleep(0.35)
        assert fake.generation >= 3
        assert _request(fake.base_url + "/models")[0] == 200
    assert not fake.running


# --- openai profile -----------------------------------------------------------


def test_openai_chat_json_echoes_the_last_user_text_with_usage(fake_openai):
    status, _, body = _post(
        fake_openai.base_url + "/chat/completions",
        {
            "model": "gpt-5.2",
            "messages": [
                {"role": "system", "content": "be terse"},
                {"role": "user", "content": "first question"},
                {"role": "assistant", "content": "first answer"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "hello"},
                        {"type": "text", "text": "world"},
                    ],
                },
            ],
        },
    )
    assert status == 200
    assert body["object"] == "chat.completion"
    assert body["model"] == "gpt-5.2"
    assert body["id"].startswith("chatcmpl-")
    [choice] = body["choices"]
    assert choice["index"] == 0
    assert choice["finish_reason"] == "stop"
    assert choice["message"] == {
        "role": "assistant",
        "content": "echo:hello world",
        "refusal": None,
    }
    assert body["usage"] == {
        "prompt_tokens": 8,
        "completion_tokens": 2,
        "total_tokens": 10,
        "prompt_tokens_details": {"cached_tokens": 0},
    }
    assert fake_openai.requests[-1]["json"]["model"] == "gpt-5.2"


def test_openai_chat_ignores_trailing_non_user_messages_and_odd_content(fake_openai):
    url = fake_openai.base_url + "/chat/completions"
    _, _, body = _post(
        url,
        {
            "model": "gpt-5.2",
            "messages": [
                {"role": "user", "content": "kept"},
                {"role": "assistant", "content": None},
            ],
        },
    )
    assert body["choices"][0]["message"]["content"] == "echo:kept"
    _, _, body = _post(
        url,
        {"model": "gpt-5.2", "messages": [{"role": "system", "content": "x"}, "junk"]},
    )
    assert body["choices"][0]["message"]["content"] == "echo:"


def test_openai_stream_is_sse_with_deltas_usage_and_done(fake_openai):
    status, headers, raw = _stream(
        fake_openai.base_url + "/chat/completions", _chat("alpha beta gamma")
    )
    assert status == 200
    assert headers["content-type"].startswith("text/event-stream")
    assert headers["transfer-encoding"] == "chunked"
    events = _events(raw)
    assert events[-1] == "[DONE]"
    chunks = events[:-1]
    assert all(chunk["object"] == "chat.completion.chunk" for chunk in chunks)
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert "role" not in chunks[1]["choices"][0]["delta"]
    text = "".join(chunk["choices"][0]["delta"].get("content", "") for chunk in chunks)
    assert text == "echo:alpha beta gamma"
    assert [chunk["choices"][0]["finish_reason"] for chunk in chunks] == [
        None,
        None,
        None,
        "stop",
    ]
    assert chunks[-1]["choices"][0]["delta"] == {}
    assert chunks[-1]["usage"]["completion_tokens"] == 3
    assert all("usage" not in chunk for chunk in chunks[:-1])


def test_tools_produce_one_tool_call_carrying_the_prompt_nonce(fake_openai):
    url = fake_openai.base_url + "/chat/completions"
    _, _, body = _post(
        url, _chat("call the tool with nonce=abc123 please", tools=TOOLS)
    )
    [choice] = body["choices"]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["content"] is None
    assert choice["message"]["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "probe_echo",
                "arguments": json.dumps({"nonce": "abc123"}),
            },
        }
    ]
    assert body["usage"]["completion_tokens"] == 2

    _, _, body = _post(url, _chat("no nonce here", tools=TOOLS))
    arguments = body["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    assert json.loads(arguments) == {"nonce": "0"}

    _, _, body = _post(url, _chat("nonce=x", tools=[]))
    assert body["choices"][0]["message"]["content"] == "echo:nonce=x"

    _, _, raw = _stream(url, _chat("nonce=zz", tools=TOOLS))
    chunks = _events(raw)[:-1]
    first = chunks[0]["choices"][0]["delta"]["tool_calls"][0]
    assert (first["id"], first["type"], first["function"]["name"]) == (
        "call_1",
        "function",
        "probe_echo",
    )
    second = chunks[1]["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"]
    assert json.loads(second) == {"nonce": "zz"}
    assert [chunk["choices"][0]["finish_reason"] for chunk in chunks] == [
        None,
        None,
        "tool_calls",
    ]


def test_json_schema_response_format_is_honoured_except_on_ollama(
    fake_openai, fake_ollama
):
    _, _, body = _post(
        fake_openai.base_url + "/chat/completions",
        _chat("structured please", response_format=JSON_SCHEMA),
    )
    assert json.loads(body["choices"][0]["message"]["content"]) == {
        "echo": "structured please"
    }

    _, _, body = _post(
        fake_ollama.base_url + "/chat/completions",
        _chat("structured please", model="qwen3:8b", response_format=JSON_SCHEMA),
    )
    assert body["choices"][0]["message"]["content"] == "echo:structured please"


def test_openai_responses_endpoint_answers_text_refusals_and_function_calls(
    fake_openai,
):
    url = fake_openai.base_url + "/responses"
    status, _, body = _post(url, {"model": "gpt-5.2", "input": "ping"})
    assert status == 200
    assert (body["object"], body["status"], body["model"]) == (
        "response",
        "completed",
        "gpt-5.2",
    )
    assert body["previous_response_id"] is None
    [message] = body["output"]
    assert message["type"] == "message"
    assert message["content"] == [
        {"type": "output_text", "text": "echo:ping", "annotations": []}
    ]
    assert body["usage"] == {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}

    status, _, body = _post(
        url,
        {
            "model": "gpt-5.2",
            "instructions": "be brief",
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "nonce=n1"}],
                }
            ],
            "tools": [{"type": "function", "name": "probe_echo", "parameters": {}}],
            "previous_response_id": "resp_from_elsewhere",
        },
    )
    [call] = body["output"]
    assert (call["type"], call["name"], call["call_id"]) == (
        "function_call",
        "probe_echo",
        "call_1",
    )
    assert json.loads(call["arguments"]) == {"nonce": "n1"}
    assert body["usage"]["input_tokens"] == 3
    assert body["previous_response_id"] == "resp_from_elsewhere"

    _, _, body = _post(
        url,
        {
            "model": "gpt-5.2",
            "input": "shape me",
            "text": {"format": {"type": "json_schema", "name": "echo", "schema": {}}},
        },
    )
    assert json.loads(body["output"][0]["content"][0]["text"]) == {"echo": "shape me"}

    _, _, body = _post(url, {"model": "gpt-5.2", "input": "refuse:nope"})
    assert body["output"][0]["content"] == [
        {"type": "refusal", "refusal": "refused:nope"}
    ]

    status, _, body = _post(url, {"model": "gpt-5.2", "input": 7})
    assert status == 400
    assert body["error"]["param"] == "input"


# --- ollama profile -----------------------------------------------------------


def test_ollama_native_discovery_routes(fake_ollama):
    root = fake_ollama.root_url
    status, _, raw = _request(root + "/api/version")
    assert (status, json.loads(raw)) == (200, {"version": "0.13.3"})

    _, _, raw = _request(root + "/api/tags")
    tags = json.loads(raw)["models"]
    assert [tag["name"] for tag in tags] == list(OLLAMA_MODELS)
    assert tags[0]["details"]["quantization_level"] == "Q4_K_M"

    status, _, body = _post(root + "/api/show", {"model": "qwen3:8b"})
    assert status == 200
    assert body["capabilities"][:2] == ["completion", "tools"]
    info = body["model_info"]
    assert info["general.architecture"] == "qwen3"
    assert info["qwen3.block_count"] == 36
    assert info["qwen3.attention.head_count_kv"] == 8
    assert info["qwen3.attention.key_length"] == 128

    status, _, body = _post(root + "/api/show", {"name": "llama9:1b"})
    assert (status, body) == (404, {"error": "model 'llama9:1b' not found"})

    _, _, raw = _request(fake_ollama.base_url + "/models")
    assert [model["id"] for model in json.loads(raw)["data"]] == list(OLLAMA_MODELS)
    status, _, body = _post(
        fake_ollama.base_url + "/responses", {"model": "qwen3:8b", "input": "x"}
    )
    assert (status, body) == (404, {"error": "Not found"})


def test_ollama_rejects_tool_choice_unknown_models_and_http_images(fake_ollama):
    url = fake_ollama.base_url + "/chat/completions"
    status, _, body = _post(
        url, _chat("hi", model="qwen3:8b", tools=TOOLS, tool_choice="required")
    )
    assert status == 400
    assert body == {"error": "tool_choice is not supported"}

    status, _, body = _post(url, _chat("hi", model="qwen9:1b"))
    assert (status, body) == (404, {"error": "model 'qwen9:1b' not found"})

    def with_image(image: Any) -> dict[str, Any]:
        return _chat("describe", model="qwen3:8b") | {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image_url", "image_url": image},
                    ],
                }
            ]
        }

    status, _, body = _post(
        url, with_image({"url": "data:image/png;base64,iVBORw0KGgo="})
    )
    assert status == 200
    assert body["choices"][0]["message"]["content"] == "echo:describe"
    status, _, body = _post(url, with_image("data:image/png;base64,iVBORw0KGgo="))
    assert status == 200
    status, _, body = _post(url, with_image({"url": "https://example.invalid/cat.png"}))
    assert (status, body) == (400, {"error": "image url must be a base64 data URI"})

    _, _, body = _post(url, _chat("hi", model="qwen3:8b", tools=TOOLS))
    assert body["choices"][0]["finish_reason"] == "tool_calls"


def test_ollama_streams_usage_only_when_include_usage_is_requested(fake_ollama):
    url = fake_ollama.base_url + "/chat/completions"
    base = _chat("one two", model="qwen2.5:7b")
    _, _, raw = _stream(url, base)
    chunks = _events(raw)[:-1]
    assert all("usage" not in chunk for chunk in chunks)
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"

    _, _, raw = _stream(url, {**base, "stream_options": {"include_usage": True}})
    chunks = _events(raw)[:-1]
    assert chunks[-1]["usage"] == {
        "prompt_tokens": 2,
        "completion_tokens": 2,
        "total_tokens": 4,
    }

    _, _, raw = _stream(url, {**base, "stream_options": "yes"})
    assert all("usage" not in chunk for chunk in _events(raw)[:-1])

    _, _, body = _post(url, base)
    assert body["usage"] == {
        "prompt_tokens": 2,
        "completion_tokens": 2,
        "total_tokens": 4,
    }


# --- hf-router profile --------------------------------------------------------


def test_hf_router_requires_a_bearer_token(fake_hf_router):
    status, _, raw = _request(fake_hf_router.base_url + "/models")
    assert (status, json.loads(raw)) == (401, {"error": "unauthorized"})
    status, _, _ = _request(
        fake_hf_router.base_url + "/chat/completions",
        method="POST",
        body=_chat("x"),
        headers={"Authorization": "Basic FAKE_BASIC_NOT_A_TOKEN"},
    )
    assert status == 401
    status, _, _ = _request(
        fake_hf_router.base_url + "/models", headers={"Authorization": "Bearer "}
    )
    assert status == 401
    status, _, _ = _request(fake_hf_router.base_url + "/models", headers=BEARER)
    assert status == 200
    assert "authorization" not in fake_hf_router.requests[0]["headers"]
    assert fake_hf_router.requests[-1]["headers"]["authorization"] == "<present>"


def test_hf_router_models_carry_providers_and_the_provider_suffix_is_echoed(
    fake_hf_router,
):
    _, _, raw = _request(fake_hf_router.base_url + "/models", headers=BEARER)
    listing = json.loads(raw)
    glm = next(model for model in listing["data"] if model["id"] == "zai-org/GLM-5.3")
    assert glm["providers"]
    for provider in glm["providers"]:
        assert set(provider) == {
            "provider",
            "status",
            "supports_tools",
            "supports_structured_output",
            "pricing",
        }
        assert set(provider["pricing"]) == {"input", "output"}
    assert "cost" not in json.dumps(listing)

    url = fake_hf_router.base_url + "/chat/completions"
    status, headers, body = _post(
        url,
        _chat("hi", model="zai-org/GLM-5.3:novita"),
        headers={**BEARER, "X-HF-Bill-To": "my-org"},
    )
    assert status == 200
    assert body["model"] == "zai-org/GLM-5.3:novita"
    assert headers["x-hf-bill-to"] == "my-org"
    assert fake_hf_router.requests[-1]["headers"]["x-hf-bill-to"] == "my-org"
    assert "cost" not in body

    _, headers, body = _post(url, _chat("hi", model="zai-org/GLM-5.3"), headers=BEARER)
    assert body["model"] == "zai-org/GLM-5.3:" + glm["providers"][0]["provider"]
    assert "x-hf-bill-to" not in headers

    _, _, body = _post(url, _chat("hi", model="acme/unknown"), headers=BEARER)
    assert body["model"] == "acme/unknown"

    _, headers, raw = _stream(
        url,
        _chat("a b", model="acme/unknown:groq"),
        headers={**BEARER, "X-HF-Bill-To": "org2"},
    )
    assert headers["x-hf-bill-to"] == "org2"
    chunks = _events(raw)[:-1]
    assert chunks[0]["model"] == "acme/unknown:groq"
    assert "usage" in chunks[-1]


# --- auth2api profile ---------------------------------------------------------


def test_auth2api_lists_36_cursor_ids_and_serves_the_bridge_routes(fake_auth2api):
    assert len(AUTH2API_MODEL_IDS) == 36 == len(set(AUTH2API_MODEL_IDS))
    assert all(model_id.startswith("cursor-") for model_id in AUTH2API_MODEL_IDS)
    assert {"cursor-grok-4.6", "cursor-auto"} <= set(AUTH2API_MODEL_IDS)
    _, _, raw = _request(fake_auth2api.base_url + "/models")
    assert [model["id"] for model in json.loads(raw)["data"]] == list(
        AUTH2API_MODEL_IDS
    )

    status, _, body = _post(
        fake_auth2api.base_url + "/chat/completions", _chat("hi", model="cursor-auto")
    )
    assert (status, body["model"]) == (200, "cursor-auto")
    assert body["usage"] == {
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
    }

    status, _, body = _post(
        fake_auth2api.base_url + "/responses",
        {"model": "cursor-grok-4.6", "input": "hi"},
    )
    assert status == 200
    assert body["output"][0]["content"][0]["text"] == "echo:hi"

    url = fake_auth2api.base_url + "/messages"
    status, _, body = _post(
        url,
        {
            "model": "cursor-grok-4.6",
            "max_tokens": 64,
            "system": "be terse",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "hello there"}]}
            ],
        },
        headers={
            "x-api-key": "FAKE_KEY_NOT_A_SECRET",
            "anthropic-version": "2023-06-01",
        },
    )
    assert status == 200
    assert (body["type"], body["role"], body["model"]) == (
        "message",
        "assistant",
        "cursor-grok-4.6",
    )
    assert body["id"].startswith("msg_")
    assert body["content"] == [{"type": "text", "text": "echo:hello there"}]
    assert (body["stop_reason"], body["stop_sequence"]) == ("end_turn", None)
    assert body["usage"] == {"input_tokens": 4, "output_tokens": 2}
    assert fake_auth2api.requests[-1]["headers"]["x-api-key"] == "<present>"
    assert "FAKE_KEY_NOT_A_SECRET" not in json.dumps(fake_auth2api.requests)

    status, _, body = _post(
        url,
        {
            "model": "cursor-grok-4.6",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "nonce=q"}],
            "tools": [{"name": "probe_echo", "input_schema": {"type": "object"}}],
        },
    )
    assert body["stop_reason"] == "tool_use"
    assert body["content"] == [
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "probe_echo",
            "input": {"nonce": "q"},
        }
    ]

    status, _, body = _post(
        url, {"model": "cursor-grok-4.6", "max_tokens": 8, "messages": "no"}
    )
    assert (status, body["error"]["param"]) == (400, "messages")


def test_auth2api_responses_and_messages_can_be_switched_off():
    with FakeOpenAIServer("auth2api", responses=False, messages=False) as fake:
        status, _, body = _post(
            fake.base_url + "/responses", {"model": "cursor-auto", "input": "x"}
        )
        assert status == 404
        assert body["error"]["code"] == "not_found"
        status, _, _ = _post(
            fake.base_url + "/messages",
            {"model": "cursor-auto", "max_tokens": 8, "messages": []},
        )
        assert status == 404
        status, _, _ = _post(
            fake.base_url + "/chat/completions", _chat("x", model="cursor-auto")
        )
        assert status == 200


# --- lmstudio profile ---------------------------------------------------------


def test_lmstudio_v0_models_and_stateful_responses(fake_lmstudio):
    _, _, raw = _request(fake_lmstudio.root_url + "/api/v0/models")
    data = json.loads(raw)["data"]
    assert [(m["id"], m["type"], m["state"]) for m in data] == [
        ("qwen3-8b", "llm", "loaded"),
        ("qwen2.5-7b-instruct", "llm", "not-loaded"),
        ("text-embedding-nomic-embed-text-v1.5", "embeddings", "not-loaded"),
    ]
    assert all(isinstance(m["max_context_length"], int) for m in data)
    _, _, raw = _request(fake_lmstudio.base_url + "/models")
    assert [m["id"] for m in json.loads(raw)["data"]] == [m["id"] for m in data]

    url = fake_lmstudio.base_url + "/responses"
    _, _, first = _post(url, {"model": "qwen3-8b", "input": "one two three"})
    assert first["previous_response_id"] is None
    assert first["usage"] == {"input_tokens": 3, "output_tokens": 3, "total_tokens": 6}
    _, _, second = _post(
        url, {"model": "qwen3-8b", "input": "four", "previous_response_id": first["id"]}
    )
    assert second["previous_response_id"] == first["id"]
    assert second["usage"]["input_tokens"] == 1 + first["usage"]["total_tokens"]

    status, _, body = _post(
        url, {"model": "qwen3-8b", "input": "x", "previous_response_id": "resp_nope"}
    )
    assert (status, body["error"]["code"]) == (404, "not_found")

    fake_lmstudio.restart()
    status, _, _ = _post(
        url, {"model": "qwen3-8b", "input": "x", "previous_response_id": first["id"]}
    )
    assert status == 404

    status, _, _ = _post(
        fake_lmstudio.base_url + "/messages",
        {"model": "qwen3-8b", "max_tokens": 1, "messages": []},
    )
    assert status == 404


# --- fault flags --------------------------------------------------------------


def test_rate_limit_every_answers_429_with_retry_after():
    with FakeOpenAIServer("openai", rate_limit_every=2) as fake:
        url = fake.base_url + "/chat/completions"
        statuses: list[int] = []
        for _ in range(4):
            status, headers, body = _post(url, _chat("x"))
            statuses.append(status)
            if status == 429:
                assert headers["retry-after"] == "1"
                assert body["error"]["type"] == "rate_limit_error"
                assert body["error"]["code"] == "rate_limit_exceeded"
        assert statuses == [200, 429, 200, 429]
        assert _request(fake.base_url + "/models")[0] == 200


def test_fail_every_answers_503_with_an_openai_error_body():
    with FakeOpenAIServer("openai", fail_every=3) as fake:
        url = fake.base_url + "/chat/completions"
        assert [_post(url, _chat("x"))[0] for _ in range(2)] == [200, 200]
        status, _, body = _post(url, _chat("x"))
        assert status == 503
        assert body["error"] == {
            "message": "The server is temporarily unavailable",
            "type": "server_error",
            "param": None,
            "code": "service_unavailable",
        }
        status, _, body = _post(
            fake.base_url + "/responses", {"model": "gpt-5.2", "input": "x"}
        )
        assert status == 200


def test_slow_first_token_delays_the_first_byte():
    with FakeOpenAIServer("openai", slow_first_token=0.3) as fake:
        req = urllib.request.Request(
            fake.base_url + "/chat/completions",
            data=json.dumps(_chat("a b", stream=True)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        with urllib.request.urlopen(req, timeout=5) as resp:
            first_byte = time.monotonic() - started
            events = _events(resp.read())
        assert first_byte >= 0.3
        assert events[-1] == "[DONE]"


def test_hang_after_tokens_streams_n_tokens_then_holds_until_the_client_leaves():
    with FakeOpenAIServer("openai", hang_after_tokens=2) as fake:
        req = urllib.request.Request(
            fake.base_url + "/chat/completions",
            data=json.dumps(_chat("a b c d e", stream=True)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=0.5)
        received = []
        for _ in range(2):
            line = resp.readline()
            assert line.startswith(b"data: ")
            received.append(json.loads(line[len(b"data: ") :]))
            assert resp.readline() == b"\n"
        assert [c["choices"][0]["delta"]["content"] for c in received] == [
            "echo:a ",
            "b ",
        ]
        with pytest.raises(TimeoutError):
            resp.readline()
        resp.close()
        _wait_for(lambda: fake.holds == ["disconnected"])

        started = time.monotonic()
        # urllib wraps connect/send failures in URLError but lets a timeout while
        # waiting for the status line propagate as a bare TimeoutError.
        with pytest.raises(TimeoutError):
            _request(
                fake.base_url + "/chat/completions",
                method="POST",
                body=_chat("x"),
                timeout=0.3,
            )
        assert time.monotonic() - started >= 0.3
        _wait_for(lambda: fake.holds == ["disconnected", "disconnected"])
    assert HANG_CAP_S == 30.0


def test_stopping_the_server_releases_a_hanging_stream():
    fake = FakeOpenAIServer("openai", hang_after_tokens=1).start()
    outcome: dict[str, Any] = {}

    def client() -> None:
        try:
            _stream(fake.base_url + "/chat/completions", _chat("a b c"))
        except Exception as exc:  # noqa: BLE001 - the shape of the failure is not the point
            outcome["error"] = exc
        else:
            outcome["error"] = None

    thread = threading.Thread(target=client)
    thread.start()
    _wait_for(lambda: len(fake.requests) == 1)
    time.sleep(0.1)
    fake.stop()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert outcome["error"] is not None
    assert fake.holds == ["stopped"]


def test_malformed_returns_truncated_json_with_200():
    with FakeOpenAIServer("openai", malformed=True) as fake:
        status, headers, raw = _request(
            fake.base_url + "/chat/completions", method="POST", body=_chat("x")
        )
        assert (status, raw) == (200, b'{"choices": [')
        assert headers["content-type"] == "application/json"
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)
        status, _, raw = _request(
            fake.base_url + "/chat/completions",
            method="POST",
            body=_chat("x", stream=True),
        )
        assert (status, raw) == (200, b'{"choices": [')


def test_echo_secret_reflects_the_authorization_value_into_content_only():
    with FakeOpenAIServer("openai", echo_secret=True) as fake:
        url = fake.base_url + "/chat/completions"
        _, _, body = _post(url, _chat("x"), headers=BEARER)
        assert (
            body["choices"][0]["message"]["content"] == f"echo:x Bearer {FAKE_BEARER}"
        )
        assert FAKE_BEARER not in json.dumps(fake.requests)
        _, _, body = _post(url, _chat("x"))
        assert body["choices"][0]["message"]["content"] == "echo:x"


def test_drop_tool_calls_flattens_the_call_into_tool_call_text():
    with FakeOpenAIServer("openai", drop_tool_calls=True) as fake:
        _, _, body = _post(
            fake.base_url + "/chat/completions", _chat("nonce=k1", tools=TOOLS)
        )
        [choice] = body["choices"]
        assert choice["finish_reason"] == "stop"
        assert "tool_calls" not in choice["message"]
        match = re.fullmatch(
            r"<tool_call>(.*)</tool_call>", choice["message"]["content"], re.S
        )
        assert match is not None
        assert json.loads(match.group(1)) == {
            "name": "probe_echo",
            "arguments": {"nonce": "k1"},
        }


def test_refusals_are_a_separate_field_unless_flattened(fake_openai):
    url = fake_openai.base_url + "/chat/completions"
    _, _, body = _post(url, _chat("refuse:no thanks"))
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": None,
        "refusal": "refused:no thanks",
    }
    assert body["usage"]["completion_tokens"] == 2
    _, _, raw = _stream(url, _chat("refuse:no thanks"))
    chunks = _events(raw)[:-1]
    assert (
        "".join(c["choices"][0]["delta"].get("refusal", "") for c in chunks)
        == "refused:no thanks"
    )
    assert all("content" not in c["choices"][0]["delta"] for c in chunks)

    with FakeOpenAIServer("openai", flatten_refusal=True) as fake:
        _, _, body = _post(
            fake.base_url + "/chat/completions", _chat("refuse:no thanks")
        )
        assert body["choices"][0]["message"] == {
            "role": "assistant",
            "content": "refused:no thanks",
        }
        _, _, body = _post(fake.base_url + "/chat/completions", _chat("plain"))
        assert body["choices"][0]["message"] == {
            "role": "assistant",
            "content": "echo:plain",
        }


def test_latency_s_delays_every_request_and_two_servers_overlap():
    with (
        FakeOpenAIServer("openai", latency_s=0.3) as one,
        FakeOpenAIServer("openai", latency_s=0.3) as two,
    ):
        elapsed: dict[str, float] = {}

        def call(name: str, fake: FakeOpenAIServer) -> None:
            started = time.monotonic()
            status, _, _ = _post(fake.base_url + "/chat/completions", _chat("x"))
            assert status == 200
            elapsed[name] = time.monotonic() - started

        threads = [
            threading.Thread(target=call, args=("one", one)),
            threading.Thread(target=call, args=("two", two)),
        ]
        started = time.monotonic()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        wall = time.monotonic() - started
        assert elapsed["one"] >= 0.3 and elapsed["two"] >= 0.3
        assert wall < elapsed["one"] + elapsed["two"]
        assert wall < 0.5

        started = time.monotonic()
        assert _request(one.base_url + "/models")[0] == 200
        assert time.monotonic() - started >= 0.3


# --- request validation -------------------------------------------------------


def test_bad_bodies_and_unknown_routes_are_rejected(fake_openai):
    url = fake_openai.base_url + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=b"{not json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=5)
    assert exc.value.code == 400
    assert json.loads(exc.value.read())["error"]["message"] == "invalid JSON body"
    assert fake_openai.requests[-1]["json"] is None

    status, _, body = _post(url, ["not", "an", "object"])
    assert (status, body["error"]["message"]) == (
        400,
        "request body must be a JSON object",
    )
    status, _, body = _post(url, {"model": "gpt-5.2"})
    assert (status, body["error"]["param"]) == (400, "messages")

    status, _, body = _request(fake_openai.root_url + "/nowhere")
    assert (status, json.loads(body)["error"]["code"]) == (404, "not_found")
    status, _, _ = _request(fake_openai.base_url + "/messages", method="POST", body={})
    assert status == 404
    status, _, _ = _request(fake_openai.base_url + "/models", method="POST", body={})
    assert status == 404
    status, _, _ = _request(fake_openai.root_url + "/api/tags")
    assert status == 404


# --- low-level helpers --------------------------------------------------------


def test_write_reports_a_vanished_client():
    class Gone:
        def write(self, data: bytes) -> None:
            raise BrokenPipeError

        def flush(self) -> None:
            pass

    assert _write(Gone(), b"x") is False
    buffer = io.BytesIO()
    assert _write(buffer, b"x") is True
    assert buffer.getvalue() == b"x"


def test_stream_sse_reports_done_gone_or_hang():
    chunks = [{"n": 0}, {"n": 1}, {"n": 2}]

    class Sink:
        def __init__(self, fail_at: int | None = None) -> None:
            self.writes: list[bytes] = []
            self.fail_at = fail_at

        def __call__(self, data: bytes) -> bool:
            if self.fail_at is not None and len(self.writes) >= self.fail_at:
                return False
            self.writes.append(data)
            return True

    sink = Sink()
    assert _stream_sse(sink, chunks, 0) == "done"
    assert len(sink.writes) == 5
    assert sink.writes[-2].endswith(b"data: [DONE]\n\n\r\n")
    assert sink.writes[-1] == b"0\r\n\r\n"
    assert all(re.match(rb"^[0-9a-f]+\r\n", write) for write in sink.writes[:-1])

    sink = Sink(fail_at=1)
    assert _stream_sse(sink, chunks, 0) == "gone"
    assert len(sink.writes) == 1

    sink = Sink(fail_at=3)
    assert _stream_sse(sink, chunks, 0) == "gone"
    assert len(sink.writes) == 3

    sink = Sink()
    assert _stream_sse(sink, chunks, 1) == "hang"
    assert len(sink.writes) == 1

    sink = Sink()
    assert _stream_sse(sink, chunks, 5) == "hang"
    assert len(sink.writes) == 3


def test_hold_connection_reports_why_it_let_go():
    stopping = threading.Event()
    server_side, client_side = socket.socketpair()
    with server_side, client_side:
        assert _hold_connection(server_side, stopping, cap_s=0.0) == "cap"
        client_side.sendall(b"x")
        assert _hold_connection(server_side, stopping, cap_s=0.15) == "cap"
        stopping.set()
        assert _hold_connection(server_side, stopping, cap_s=5.0) == "stopped"
        stopping.clear()
        client_side.close()
        assert _hold_connection(server_side, stopping, cap_s=5.0) == "disconnected"

    class Broken:
        def __init__(self, sock: socket.socket) -> None:
            self._sock = sock

        def fileno(self) -> int:
            return self._sock.fileno()

        def recv(self, size: int) -> bytes:
            raise ConnectionResetError

    server_side, client_side = socket.socketpair()
    with server_side, client_side:
        client_side.sendall(b"x")
        assert (
            _hold_connection(Broken(server_side), stopping, cap_s=5.0) == "disconnected"
        )


# --- CLI ----------------------------------------------------------------------


def test_cli_prints_the_success_line_and_serves_until_stopped(capsys):
    stop = threading.Event()
    seen: dict[str, Any] = {}

    def ready(server: FakeOpenAIServer) -> None:
        seen["server"] = server
        seen["models"] = _request(server.base_url + "/models", headers=BEARER)[0]
        seen["tags"] = _request(server.root_url + "/api/tags")[0]

    thread = threading.Thread(
        target=lambda: seen.setdefault(
            "rc",
            main(
                [
                    "--port",
                    "0",
                    "--profile",
                    "ollama",
                    "--rate-limit-every",
                    "3",
                    "--fail-every",
                    "4",
                    "--slow-first-token",
                    "0",
                    "--hang-after-tokens",
                    "0",
                    "--malformed",
                    "--echo-secret",
                    "--drop-tool-calls",
                    "--flatten-refusal",
                    "--latency",
                    "0",
                    "--no-responses",
                    "--no-messages",
                    "--restart-every",
                    "0",
                ],
                stop=stop,
                ready=ready,
            ),
        )
    )
    thread.start()
    _wait_for(lambda: "tags" in seen)
    time.sleep(0.25)
    stop.set()
    thread.join(timeout=5)
    assert seen["rc"] == 0
    server = seen["server"]
    assert (seen["models"], seen["tags"]) == (200, 200)
    assert not server.running
    assert (server.profile, server.rate_limit_every, server.fail_every) == (
        "ollama",
        3,
        4,
    )
    assert (server.malformed, server.echo_secret, server.drop_tool_calls) == (
        True,
        True,
        True,
    )
    assert (server.flatten_refusal, server.responses, server.messages) == (
        True,
        False,
        False,
    )
    out = capsys.readouterr().out
    assert re.search(
        r"^SUCCESS:fake-openai-v1 listening=http://127\.0\.0\.1:\d+/v1 profile=ollama$",
        out,
        re.M,
    )


def test_cli_stops_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    def interrupt(stop: threading.Event) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(fake_openai_v1, "_serve_until", interrupt)
    assert main(["--profile", "openai"]) == 0
    assert (
        "SUCCESS:fake-openai-v1 listening=http://127.0.0.1:" in capsys.readouterr().out
    )

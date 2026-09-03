from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from typing import Any

import glm53_core
import mcp_server
import openai_proxy
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from starlette.requests import Request
from starlette.testclient import TestClient


class FakeMessage:
    def __init__(self, result: Any = "GLM reply") -> None:
        self.content = result


class FakeChoice:
    def __init__(self, result: Any = "GLM reply") -> None:
        self.message = FakeMessage(result)


class FakeResponse:
    def __init__(self, result: Any = "GLM reply") -> None:
        self.choices = [FakeChoice(result)]


class FakeCompletions:
    def __init__(self, result: Any = "GLM reply") -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse(self.result)


class FakeChat:
    def __init__(self, result: Any = "GLM reply") -> None:
        self.completions = FakeCompletions(result)


class FakeOpenAIClient:
    def __init__(self, result: Any = "GLM reply") -> None:
        self.chat = FakeChat(result)


def test_invoke_passes_prompt_then_blank_system_prompt() -> None:
    fake = FakeOpenAIClient()
    created: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeOpenAIClient:
        created.append(kwargs)
        return fake

    result = glm53_core.invoke(
        prompt="Hello",
        system_prompt="",
        token="test-token",
        client_factory=factory,
    )

    assert result == "GLM reply"
    assert created == [
        {
            "base_url": "https://router.huggingface.co/v1",
            "api_key": "test-token",
            "timeout": 120.0,
            "max_retries": 1,
        }
    ]
    assert fake.chat.completions.calls == [
        {
            "model": "zai-org/GLM-5.3:zai-org",
            "messages": [
                {"role": "system", "content": ""},
                {"role": "user", "content": "Hello"},
            ],
        }
    ]


@pytest.mark.parametrize("result", [None, 42, {"text": "reply"}, ["reply"]])
def test_invoke_rejects_non_text_space_results(result: Any) -> None:
    fake = FakeOpenAIClient(result)

    with pytest.raises(glm53_core.Glm53Error, match="non-text"):
        glm53_core.invoke(
            "Hello",
            token="dedicated-token",
            client_factory=lambda *_args, **_kwargs: fake,
        )


def test_messages_without_system_keep_system_prompt_blank() -> None:
    prompt, system_prompt = glm53_core.messages_to_prompts(
        [{"role": "user", "content": "Hello"}]
    )

    assert prompt == "Hello"
    assert system_prompt == ""


def test_messages_preserve_system_and_conversation_context() -> None:
    prompt, system_prompt = glm53_core.messages_to_prompts(
        [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {
                "role": "user",
                "content": [{"type": "text", "text": "Follow-up"}],
            },
        ]
    )

    assert system_prompt == "Be concise."
    assert prompt == (
        'Conversation JSON:\n[{"role":"user","content":"First question"},'
        '{"role":"assistant","content":"First answer"},'
        '{"role":"user","content":"Follow-up"}]'
    )


def test_messages_reject_unsupported_multimodal_content() -> None:
    with pytest.raises(glm53_core.Glm53Error, match="text-only"):
        glm53_core.messages_to_prompts(
            [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": "x"}],
                }
            ]
        )


def test_invoke_requires_huggingface_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)

    with pytest.raises(glm53_core.Glm53Error, match="HUGGINGFACE_TOKEN"):
        glm53_core.invoke(
            "Hello",
            client_factory=lambda **_kwargs: pytest.fail(
                "client must not be created without Hugging Face auth"
            ),
        )


def test_inference_specific_token_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_INFERENCE_TOKEN", "inference-only")
    monkeypatch.setenv("HUGGINGFACE_TOKEN", "broader-hub-token")

    assert glm53_core._token_from_env() == "inference-only"


def test_invoke_does_not_leak_upstream_exception_text() -> None:
    class BrokenCompletions(FakeCompletions):
        def create(self, **kwargs: Any) -> FakeResponse:
            raise RuntimeError("https://user:SECRETPW@internal.invalid")

    broken = FakeOpenAIClient()
    broken.chat.completions = BrokenCompletions()

    with pytest.raises(glm53_core.Glm53UpstreamError) as error:
        glm53_core.invoke(
            "Hello",
            token="dedicated-token",
            client_factory=lambda **_kwargs: broken,
        )

    assert str(error.value) == "GLM 5.3 router request failed"
    assert "SECRETPW" not in str(error.value)


def test_invoke_rejects_missing_message_shape() -> None:
    fake = FakeOpenAIClient()
    fake.chat.completions.create = lambda **_kwargs: type(
        "Response",
        (),
        {"choices": [type("Choice", (), {"message": None})()]},
    )()

    with pytest.raises(glm53_core.Glm53UpstreamError):
        glm53_core.invoke(
            "Hello",
            token="test-token",
            client_factory=lambda **_kwargs: fake,
        )


def test_mcp_tool_exposes_editable_blank_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[tuple[str, str]] = []

    def invoke(prompt: str, system_prompt: str = "") -> str:
        received.append((prompt, system_prompt))
        return "MCP reply"

    monkeypatch.setattr(mcp_server.core, "invoke", invoke)

    result = mcp_server.glm53_chat(user_prompt="Hello")

    assert result == {
        "ok": True,
        "model": "glm-5.3-custom",
        "upstream_model": "zai-org/GLM-5.3:zai-org",
        "trust": "untrusted-third-party-model-output",
        "response": "<untrusted-model-output>MCP reply</untrusted-model-output>",
    }
    assert received == [("Hello", "")]


def test_mcp_tool_raises_safe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def invoke(_prompt: str, _system_prompt: str = "") -> str:
        raise glm53_core.Glm53UpstreamError("GLM 5.3 router request failed")

    monkeypatch.setattr(mcp_server.core, "invoke", invoke)

    with pytest.raises(ToolError, match="GLM 5.3 router request failed"):
        asyncio.run(
            mcp_server.mcp.call_tool(
                "glm53_chat",
                {"user_prompt": "Hello", "system_prompt": ""},
            )
        )


def make_client(
    invoke: Callable[[str, str], str],
    *,
    api_key: str = "proxy-test-key",
) -> TestClient:
    client = TestClient(
        openai_proxy.create_app(
            invoke=invoke,
            api_key=api_key,
            allowed_hosts=["testserver", "127.0.0.1", "localhost"],
        )
    )
    if api_key:
        client.headers["Authorization"] = f"Bearer {api_key}"
    return client


def test_models_endpoint_exposes_custom_model() -> None:
    client = make_client(lambda _prompt, _system: "unused")

    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "glm-5.3-custom"


def test_health_endpoint_does_not_require_authentication() -> None:
    client = make_client(lambda _prompt, _system: "unused", api_key="")

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "model": "glm-5.3-custom"}


def test_proxy_requires_configured_api_key() -> None:
    client = make_client(lambda _prompt, _system: "unused", api_key="")

    response = client.get("/v1/models")

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "proxy API key is not configured"


def test_proxy_rejects_wrong_api_key() -> None:
    client = TestClient(
        openai_proxy.create_app(
            invoke=lambda _prompt, _system: "unused",
            api_key="expected",
            allowed_hosts=["testserver"],
        )
    )

    response = client.get(
        "/v1/models",
        headers={"Authorization": "Bearer wrong"},
    )

    assert response.status_code == 401


def test_proxy_rejects_non_ascii_authorization_without_crashing() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/models",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer \xe9\xe9")],
            "scheme": "http",
            "server": ("127.0.0.1", 8321),
            "client": ("127.0.0.1", 12345),
        }
    )

    response = openai_proxy._auth_error(request, "expected")

    assert response is not None
    assert response.status_code == 401


def test_proxy_rejects_browser_origins() -> None:
    client = make_client(lambda _prompt, _system: "unused")

    response = client.post(
        "/v1/chat/completions",
        headers={"Origin": "https://attacker.invalid"},
        json={
            "model": "glm-5.3-custom",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 403


def test_proxy_rejects_untrusted_host_header() -> None:
    client = make_client(lambda _prompt, _system: "unused")

    response = client.get(
        "/v1/models",
        headers={"Host": "attacker.invalid"},
    )

    assert response.status_code == 400


def test_chat_completions_preserve_blank_system_prompt() -> None:
    received: list[tuple[str, str]] = []

    def invoke(prompt: str, system_prompt: str) -> str:
        received.append((prompt, system_prompt))
        return "Hello from GLM"

    client = make_client(invoke)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.3-custom",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 200
    assert received == [("Hello", "")]
    body = response.json()
    assert body["model"] == "glm-5.3-custom"
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": "Hello from GLM",
    }


def test_chat_completions_support_single_chunk_streaming() -> None:
    client = make_client(lambda _prompt, _system: "Streamed reply")

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.3-custom",
            "messages": [{"role": "system", "content": ""}, {"role": "user", "content": "Hi"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"content":"Streamed reply"' in response.text
    assert "data: [DONE]" in response.text


def test_chat_completions_reject_unknown_model() -> None:
    client = make_client(lambda _prompt, _system: "unused")

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "not-glm",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request_error"


def test_proxy_rejects_malformed_json() -> None:
    client = make_client(lambda _prompt, _system: "unused")

    response = client.post(
        "/v1/chat/completions",
        content=b"{not-json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "request body must be valid JSON"


def test_proxy_maps_validation_and_upstream_errors() -> None:
    def invalid(_prompt: str, _system_prompt: str) -> str:
        raise glm53_core.Glm53ValidationError("bad prompt")

    invalid_response = make_client(invalid).post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.3-custom",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json()["error"]["message"] == "bad prompt"

    def upstream(_prompt: str, _system_prompt: str) -> str:
        raise glm53_core.Glm53UpstreamError("internal sensitive detail")

    upstream_response = make_client(upstream).post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.3-custom",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert upstream_response.status_code == 502
    assert "sensitive" not in upstream_response.text


def test_proxy_rejects_invalid_content_length() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/chat/completions",
            "query_string": b"",
            "headers": [
                (b"authorization", b"Bearer expected"),
                (b"content-length", b"not-a-number"),
            ],
            "scheme": "http",
            "server": ("127.0.0.1", 8321),
            "client": ("127.0.0.1", 12345),
        }
    )

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    request._receive = receive
    response = asyncio.run(
        openai_proxy._chat_response(
            request,
            "expected",
            lambda _prompt, _system: "unused",
        )
    )

    assert response.status_code == 400


def test_proxy_rejects_unsupported_openai_parameters() -> None:
    client = make_client(lambda _prompt, _system: "unused")
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.3-custom",
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [{"type": "function", "function": {"name": "x"}}],
        },
    )

    assert response.status_code == 400
    assert "unsupported parameters: tools" in response.json()["error"]["message"]


def test_proxy_rejects_oversized_request_before_json_parsing() -> None:
    client = make_client(lambda _prompt, _system: "unused")

    response = client.post(
        "/v1/chat/completions",
        content=b"x" * (openai_proxy.MAX_BODY_BYTES + 1),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413


def test_proxy_does_not_leak_unexpected_upstream_errors() -> None:
    def broken(_prompt: str, _system_prompt: str) -> str:
        raise RuntimeError("sensitive upstream detail")

    client = make_client(broken)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.3-custom",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 502
    assert response.json()["error"]["message"] == "upstream GLM 5.3 request failed"
    assert "sensitive" not in response.text


def test_main_rejects_ipv6_loopback_until_host_parsing_is_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["openai_proxy.py", "--host", "::1"],
    )

    with pytest.raises(SystemExit, match="2"):
        openai_proxy.main()

"""Shared GLM 5.3 Hugging Face Space client logic."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from openai import OpenAI

HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"
HF_MODEL_ID = "zai-org/GLM-5.3:zai-org"
MODEL_ID = "glm-5.3-custom"
MAX_PROMPT_CHARS = 500_000


class Glm53Error(RuntimeError):
    """A safe, user-facing GLM adapter error."""


class Glm53ValidationError(Glm53Error):
    """The caller supplied an invalid request."""


class Glm53UpstreamError(Glm53Error):
    """The hosted inference router failed without exposing upstream details."""


class CompletionClient(Protocol):
    """Subset of the OpenAI-compatible HF client used by this adapter."""

    @property
    def chat(self) -> Any:
        """Expose the chat-completions resource."""
        ...


ClientFactory = Callable[..., CompletionClient]


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, Sequence) or isinstance(content, (bytes, bytearray)):
        raise Glm53ValidationError(
            "GLM 5.3 adapter accepts text-only message content"
        )

    parts: list[str] = []
    for block in content:
        if (
            not isinstance(block, Mapping)
            or block.get("type") != "text"
            or not isinstance(block.get("text"), str)
        ):
            raise Glm53ValidationError(
                "GLM 5.3 adapter accepts text-only message content"
            )
        parts.append(block["text"])
    return "\n".join(parts)


def messages_to_prompts(messages: Any) -> tuple[str, str]:
    """Convert OpenAI-style messages into Space prompt/system fields."""
    if not isinstance(messages, list) or not messages:
        raise Glm53ValidationError("messages must be a non-empty array")

    system_parts: list[str] = []
    conversation: list[tuple[str, str]] = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise Glm53ValidationError("each message must be an object")
        role = message.get("role")
        if role not in {"system", "developer", "user", "assistant"}:
            raise Glm53ValidationError(f"unsupported message role: {role!r}")
        text = _text_content(message.get("content"))
        if role in {"system", "developer"}:
            if text:
                system_parts.append(text)
        else:
            conversation.append((str(role), text))

    if not conversation:
        raise Glm53ValidationError(
            "messages must include a user or assistant message"
        )

    if len(conversation) == 1 and conversation[0][0] == "user":
        prompt = conversation[0][1]
    else:
        prompt = "Conversation JSON:\n" + json.dumps(
            [
                {"role": role, "content": text}
                for role, text in conversation
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    system_prompt = "\n\n".join(system_parts)
    _validate_lengths(prompt, system_prompt)
    return prompt, system_prompt


def _validate_lengths(prompt: str, system_prompt: str) -> None:
    if not isinstance(prompt, str) or not isinstance(system_prompt, str):
        raise Glm53ValidationError(
            "prompt and system_prompt must be strings"
        )
    if not prompt.strip():
        raise Glm53ValidationError("prompt must not be empty")
    if len(prompt) + len(system_prompt) > MAX_PROMPT_CHARS:
        raise Glm53ValidationError(
            f"combined prompt exceeds the {MAX_PROMPT_CHARS}-character limit"
        )


def _token_from_env() -> str:
    token = (
        os.getenv("HF_INFERENCE_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
        or os.getenv("HF_TOKEN")
    )
    if not token:
        raise Glm53ValidationError(
            "HUGGINGFACE_TOKEN or HF_TOKEN is required for the official "
            "Hugging Face inference router"
        )
    return token


def invoke(
    prompt: str,
    system_prompt: str = "",
    *,
    token: str | None = None,
    client_factory: ClientFactory = OpenAI,
) -> str:
    """Call GLM 5.3 through Hugging Face's official OpenAI-compatible router."""
    _validate_lengths(prompt, system_prompt)
    try:
        client = client_factory(
            base_url=HF_ROUTER_BASE_URL,
            api_key=token if token is not None else _token_from_env(),
            timeout=120.0,
            max_retries=1,
        )
        completion = client.chat.completions.create(
            model=HF_MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        if not completion.choices:
            raise Glm53UpstreamError(
                "GLM 5.3 router returned no completion choices"
            )
        message = completion.choices[0].message
        if message is None:
            raise Glm53UpstreamError(
                "GLM 5.3 router returned no completion message"
            )
        result = message.content
    except Glm53Error:
        raise
    except Exception as exc:
        raise Glm53UpstreamError("GLM 5.3 router request failed") from exc

    if not isinstance(result, str):
        raise Glm53UpstreamError(
            "GLM 5.3 router returned a non-text response"
        )
    return result

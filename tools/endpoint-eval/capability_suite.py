"""T2/T3 capability and reliability definitions (lens 08 sections 2-3; BUILD-CONTRACT 6).

LIVE RUNS ARE OWNER-RUN. A non-loopback ``base_url`` is refused unless the owner exports
``INFERENCE_LIVE=1``; CI only ever runs ``--fake`` (the inference-hub fake server) and the
in-test loopback stubs. Nothing here reads a credential value: ``bearer_env`` is the NAME of
the environment variable and a named-but-unset variable fails closed with
``CREDENTIAL_MISSING`` before any request leaves the box.

``PROBES`` is the T2/T3 definition: each probe is a family of items (distinct prompts, tools or
schemas) and every item runs ``n`` independent trials against the same endpoint. The graders
are all code: a tool_call that carries the prompt nonce, schema-valid structured output, a
nonce echoed back from a base64 image prompt or a planted needle, integer ``usage`` counts, a
``tool_call_id`` that survives a round trip. Per probe the runner reports the tau-bench
estimators from ``graders.passk`` averaged over the probe's items -- ``pass_at_3`` (capability:
one of k trials succeeds) and ``pass_hat_3`` (reliability: all k trials succeed) -- and the
keep / discard / crash / insufficient decision: pass@3 must reach 0.90 for a local endpoint
(T2) or 0.80 for a hosted one (T3); reliability-gated probes (tools, schema, usage, id
round trip) must also reach pass^3 == 1.00; fewer than 4 trials is ``insufficient``; a 429,
5xx, auth or timeout during sampling is a ``crash`` (guardrail 6: rate-limited endpoints are
never scored as fast), never a discard.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import struct
import urllib.parse
import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from contract_suite import (
    BACKEND_AUTH,
    BACKEND_RATE_LIMITED,
    BACKEND_UNAVAILABLE,
    CREDENTIAL_MISSING,
    FAKE_MODEL,
    FAKE_SERVER_PATH,
    PROBE_TOOL_NAME,
    TIMEOUT_NO_OUTPUT,
    TIMEOUT_PARTIAL,
    Client,
    WireError,
    echo_prompt,
    grade_json_reply,
    grade_tool_reply,
    grade_usage,
    load_fake_server,
    probe_tool,
    reply_parts,
    tool_prompt,
)
from graders.passk import (
    KEEP,
    RELIABILITY_PASS_HAT_3,
    T2_PASS_AT_3,
    T3_PASS_AT_3,
    decision,
    pass_at_k,
    pass_hat_k,
)

NAME = "endpoint-eval-capability"
LIVE_ENV = "INFERENCE_LIVE"
CHAT = "/chat/completions"
DEFAULT_K = 3
DEFAULT_N = 4
DEFAULT_TIMEOUT_S = 30.0

CRASH_CLASSES = frozenset(
    {
        BACKEND_RATE_LIMITED,
        BACKEND_UNAVAILABLE,
        BACKEND_AUTH,
        TIMEOUT_NO_OUTPUT,
        TIMEOUT_PARTIAL,
        CREDENTIAL_MISSING,
    }
)

TOOL_NAMES = (
    PROBE_TOOL_NAME,
    "write_note",
    "send_message",
    "browser_navigate",
    "search_code",
)
TOOL_CHOICES: tuple[tuple[str, Any], ...] = (
    (PROBE_TOOL_NAME, "required"),
    ("write_note", {"type": "function", "function": {"name": "write_note"}}),
    ("send_message", "required"),
)
_ECHO_STRING = {"type": "string"}
JSON_SCHEMAS: tuple[dict[str, Any], ...] = (
    {
        "type": "object",
        "properties": {"echo": _ECHO_STRING},
        "required": ["echo"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {"echo": _ECHO_STRING, "confidence": {"type": "number"}},
        "required": ["echo"],
    },
    {
        "type": "object",
        "properties": {
            "echo": _ECHO_STRING,
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["echo"],
    },
    {
        "type": "object",
        "properties": {
            "echo": _ECHO_STRING,
            "level": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["echo"],
    },
    {
        "type": "object",
        "properties": {
            "echo": _ECHO_STRING,
            "meta": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        },
        "required": ["echo"],
    },
)
PIXELS: tuple[tuple[int, int, int], ...] = ((255, 0, 0), (0, 0, 255))
REASONING_EFFORTS = ("low", "high")
CONTEXT_CHARS = {"8k": 24_000, "32k": 96_000}
CONTEXT_SIZES = tuple(CONTEXT_CHARS)
NEEDLE_DEPTH = 0.5
_FILLER = (
    "The ledger is append-only and every row names the variant it measured.",
    "A bridge that strips tool calls is graded capability-absent, never failed.",
    "Secrets travel by environment-variable name; a value never enters a fixture.",
    "The hub idle-exits after ten minutes and the bind is its own mutex.",
    "Quota-billed rows carry a null cost because zero could be optimised into free.",
    "Every script is dry-run by default and prints exactly one status line.",
    "pass at k measures capability and pass hat k measures reliability.",
    "The routing policy names models, never URLs, and lives in one file.",
)


class LiveDisabledError(RuntimeError):
    """Raised for a non-loopback base URL when the run was not marked live."""


def is_loopback(base_url: str) -> bool:
    host = urllib.parse.urlsplit(base_url).hostname
    if host is None:
        return False
    return host in ("localhost", "::1") or host.startswith("127.")


def png_1x1(rgb: tuple[int, int, int]) -> bytes:
    """A valid 8-bit RGB 1x1 PNG built with stdlib only."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = zlib.compress(b"\x00" + bytes(rgb))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )


def data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def haystack(chars: int, needle: str, depth: float = NEEDLE_DEPTH) -> str:
    """Repo-flavoured filler of at least ``chars`` characters with ``needle`` at ``depth``."""
    sentences: list[str] = []
    total = 0
    index = 0
    while total < chars:
        sentence = f"Rule {index + 1}: {_FILLER[index % len(_FILLER)]}"
        sentences.append(sentence)
        total += len(sentence) + 1
        index += 1
    sentences.insert(int(len(sentences) * depth), needle)
    return "\n".join(sentences)


def needle_prompt(size: str, nonce: str) -> str:
    text = haystack(CONTEXT_CHARS[size], f"The secret nonce is {nonce}.")
    return (
        f"{text}\n\nQuestion: what is the secret nonce planted in the text above? "
        "Reply with the nonce only."
    )


def _chat(
    model: str, messages: Sequence[Mapping[str, Any]], **extra: Any
) -> dict[str, Any]:
    return {"model": model, "messages": list(messages), **extra}


def _user(text: str) -> dict[str, Any]:
    return {"role": "user", "content": text}


def _echoes(body: Mapping[str, Any], nonce: str) -> bool:
    content, _, _ = reply_parts(body)
    return content is not None and nonce in content


def trial_tools_roundtrip(client: Client, model: str, item: int, nonce: str) -> bool:
    name = TOOL_NAMES[item]
    body = client.post_json(
        CHAT,
        _chat(
            model, [_user(tool_prompt(nonce, name))], tools=[probe_tool(nonce, name)]
        ),
    )
    return grade_tool_reply(body, nonce, name).passed


def trial_tool_choice_required(
    client: Client, model: str, item: int, nonce: str
) -> bool:
    name, choice = TOOL_CHOICES[item]
    body = client.post_json(
        CHAT,
        _chat(
            model,
            [_user(tool_prompt(nonce, name))],
            tools=[probe_tool(nonce, name)],
            tool_choice=choice,
        ),
    )
    return grade_tool_reply(body, nonce, name).passed


def trial_json_schema_native(client: Client, model: str, item: int, nonce: str) -> bool:
    schema = JSON_SCHEMAS[item]
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": f"echo_{item}", "strict": True, "schema": schema},
    }
    body = client.post_json(
        CHAT,
        _chat(
            model,
            [_user(f"Return the token {nonce} as the echo field.")],
            response_format=response_format,
        ),
    )
    return grade_json_reply(body, schema).passed


def trial_vision_base64(client: Client, model: str, item: int, nonce: str) -> bool:
    content = [
        {
            "type": "text",
            "text": f"Name the colour of the image in one word, then repeat nonce={nonce} verbatim.",
        },
        {"type": "image_url", "image_url": {"url": data_uri(png_1x1(PIXELS[item]))}},
    ]
    body = client.post_json(CHAT, _chat(model, [{"role": "user", "content": content}]))
    return _echoes(body, nonce)


def trial_usage_reported(client: Client, model: str, item: int, nonce: str) -> bool:
    body = client.post_json(CHAT, _chat(model, [_user(echo_prompt(nonce))]))
    return grade_usage(body).passed and _echoes(body, nonce)


def _reasoning_trial(effort: str) -> Callable[[Client, str, int, str], bool]:
    def trial(client: Client, model: str, item: int, nonce: str) -> bool:
        body = client.post_json(
            CHAT, _chat(model, [_user(echo_prompt(nonce))], reasoning_effort=effort)
        )
        return _echoes(body, nonce)

    return trial


def _context_trial(size: str) -> Callable[[Client, str, int, str], bool]:
    def trial(client: Client, model: str, item: int, nonce: str) -> bool:
        body = client.post_json(CHAT, _chat(model, [_user(needle_prompt(size, nonce))]))
        return _echoes(body, nonce)

    return trial


def trial_tool_call_id_roundtrip(
    client: Client, model: str, item: int, nonce: str
) -> bool:
    first = _user(tool_prompt(nonce))
    body = client.post_json(CHAT, _chat(model, [first], tools=[probe_tool(nonce)]))
    if not grade_tool_reply(body, nonce).passed:
        return False
    _, message, _ = reply_parts(body)
    call = message["tool_calls"][0]
    follow_up = [
        first,
        {"role": "assistant", "content": None, "tool_calls": [dict(call)]},
        {
            "role": "tool",
            "tool_call_id": call["id"],
            "content": json.dumps({"nonce": nonce, "status": "ok"}),
        },
        _user(f"The tool has run. Reply with the value it returned: nonce={nonce}"),
    ]
    body = client.post_json(CHAT, _chat(model, follow_up))
    return _echoes(body, nonce)


@dataclass(frozen=True)
class Probe:
    name: str
    items: int
    reliability_gate: bool
    trial: Callable[[Client, str, int, str], bool]
    description: str


PROBES: tuple[Probe, ...] = (
    Probe(
        "tools_roundtrip",
        len(TOOL_NAMES),
        True,
        trial_tools_roundtrip,
        "one tool_call per house tool, JSON arguments carry the nonce, id present",
    ),
    Probe(
        "tool_choice_required",
        len(TOOL_CHOICES),
        True,
        trial_tool_choice_required,
        "tool_choice required / named function is honoured",
    ),
    Probe(
        "json_schema_native",
        len(JSON_SCHEMAS),
        True,
        trial_json_schema_native,
        "response_format json_schema strict yields schema-valid JSON",
    ),
    Probe(
        "vision_base64",
        len(PIXELS),
        False,
        trial_vision_base64,
        "a base64 1x1 PNG data URI is accepted and the text part is answered",
    ),
    Probe("usage_reported", 1, True, trial_usage_reported, "integer usage counts"),
    Probe(
        "reasoning_effort_low",
        1,
        False,
        _reasoning_trial("low"),
        "reasoning_effort=low is accepted",
    ),
    Probe(
        "reasoning_effort_high",
        1,
        False,
        _reasoning_trial("high"),
        "reasoning_effort=high is accepted",
    ),
    Probe(
        "context_probe_8k",
        1,
        False,
        _context_trial("8k"),
        "needle recalled at 50 % depth of a ~6k-token haystack",
    ),
    Probe(
        "context_probe_32k",
        1,
        False,
        _context_trial("32k"),
        "needle recalled at 50 % depth of a ~24k-token haystack",
    ),
    Probe(
        "tool_call_id_roundtrip",
        1,
        True,
        trial_tool_call_id_roundtrip,
        "a tool result addressed by the issued tool_call_id is accepted",
    ),
)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_probe(
    probe: Probe,
    client: Client,
    model: str,
    *,
    k: int,
    n: int,
    pass_at_k_target: float,
) -> dict[str, Any]:
    per_item_at_k: list[float] = []
    per_item_hat_k: list[float] = []
    per_item_at_1: list[float] = []
    classes: set[str] = set()
    crashed = False
    for item in range(probe.items):
        successes = 0
        for _ in range(n):
            nonce = secrets.token_hex(6)
            try:
                passed = probe.trial(client, model, item, nonce)
            except WireError as error:
                classes.add(error.error_class)
                passed = False
                if error.error_class in CRASH_CLASSES:
                    crashed = True
                    break
            successes += int(passed)
        if crashed:
            break
        per_item_at_k.append(pass_at_k(n, successes, k))
        per_item_hat_k.append(pass_hat_k(n, successes, k))
        per_item_at_1.append(successes / n)
    pass_at_1, at_k, hat_k = (
        _mean(per_item_at_1),
        _mean(per_item_at_k),
        _mean(per_item_hat_k),
    )
    return {
        "pass_at_1": pass_at_1,
        "pass_at_3": at_k,
        "pass_hat_3": hat_k,
        "n": n,
        "k": k,
        "items": probe.items,
        "items_completed": len(per_item_at_k),
        "reliability_gate": probe.reliability_gate,
        "decision": decision(
            pass_at_1,
            at_k,
            hat_k,
            n,
            crashed=crashed,
            pass_at_3_target=pass_at_k_target,
            pass_hat_3_target=RELIABILITY_PASS_HAT_3
            if probe.reliability_gate
            else None,
        ),
        "error_classes_hit": sorted(classes),
    }


def run(
    base_url: str,
    model: str,
    *,
    k: int = DEFAULT_K,
    n: int = DEFAULT_N,
    live: bool = False,
    hosted: bool = False,
    bearer_env: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    probes: Sequence[Probe] = PROBES,
) -> dict[str, Any]:
    """Run every probe ``n`` times per item; ``k`` is the pass@k / pass^k draw size."""
    if k < 1 or n < k:
        raise ValueError(f"need 1 <= k <= n, got k={k} n={n}")
    if not live and not is_loopback(base_url):
        raise LiveDisabledError(
            f"{base_url} is not loopback; live runs are owner-run behind {LIVE_ENV}=1"
        )
    bearer = os.environ.get(bearer_env) if bearer_env else None
    if bearer_env and not bearer:
        raise WireError(CREDENTIAL_MISSING, f"{bearer_env} is not set")
    client = Client(base_url, bearer, timeout_s)
    target = T3_PASS_AT_3 if hosted else T2_PASS_AT_3
    results = {
        probe.name: run_probe(probe, client, model, k=k, n=n, pass_at_k_target=target)
        for probe in probes
    }
    return {
        "model": model,
        "k": k,
        "n": n,
        "hosted": hosted,
        "pass_at_k_target": target,
        "probes": results,
        "requests": len(client.calls),
    }


def summary_line(result: Mapping[str, Any]) -> tuple[bool, str]:
    probes: Mapping[str, Mapping[str, Any]] = result["probes"]
    not_kept = [
        f"{name}:{report['decision']}"
        for name, report in probes.items()
        if report["decision"] != KEEP
    ]
    at_k_min = min(report["pass_at_3"] for report in probes.values())
    hat_k_min = min(report["pass_hat_3"] for report in probes.values())
    summary = f"probes={len(probes)} pass_at_3_min={at_k_min:.2f} pass_hat_3_min={hat_k_min:.2f}"
    if not_kept:
        return False, f"{summary} not_kept={','.join(not_kept)}"
    return True, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="capability_suite",
        description="T2/T3 capability and reliability probes (live runs are owner-run).",
    )
    parser.add_argument("--base-url", help="OpenAI-compatible base URL ending in /v1")
    parser.add_argument("--model", default=FAKE_MODEL)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument(
        "--hosted", action="store_true", help="apply the T3 target (0.80)"
    )
    parser.add_argument("--bearer-env", default=None)
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--fake", action="store_true", help="run against the fake server"
    )
    args = parser.parse_args(argv)
    try:
        if args.fake:
            server_class = load_fake_server()
            if server_class is None:
                print(f"FAILED:{NAME} fake-server-missing {FAKE_SERVER_PATH}")
                return 1
            server = server_class("openai")
            server.start()
            try:
                result = run(
                    server.base_url,
                    FAKE_MODEL,
                    k=args.k,
                    n=args.n,
                    timeout_s=args.timeout_s,
                )
            finally:
                server.stop()
        elif not args.base_url:
            print(f"FAILED:{NAME} --base-url or --fake is required")
            return 1
        else:
            result = run(
                args.base_url,
                args.model,
                k=args.k,
                n=args.n,
                live=os.environ.get(LIVE_ENV) == "1",
                hosted=args.hosted,
                bearer_env=args.bearer_env,
                timeout_s=args.timeout_s,
            )
    except LiveDisabledError:
        print(
            f"FAILED:{NAME} live-disabled (export {LIVE_ENV}=1 for an owner-run live pass)"
        )
        return 1
    except (ValueError, WireError) as error:
        print(f"FAILED:{NAME} {error}")
        return 1
    ok, summary = summary_line(result)
    if ok:
        print(f"SUCCESS:{NAME} {summary}")
        return 0
    print(f"FAILED:{NAME} {summary}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

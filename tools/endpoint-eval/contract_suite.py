"""T1 contract suite (BUILD-CONTRACT section 6) over an OpenAI-compatible ``/v1`` face.

``run(base_url, model=...)`` drives six checks with plain ``urllib`` and grades each with
code: the model list parses, a plain prompt echoes a nonce, ``usage`` is present, ``tools``
yield exactly one ``tool_call`` whose JSON ``arguments`` carry the nonce (graded by
``graders.tool_fidelity``), ``response_format`` ``json_schema`` yields schema-valid JSON, and a
streamed SSE reply assembles to the non-streamed text and ends with ``[DONE]``. ``pass_at_1`` is
the fraction of checks that passed and must be 1.00 for a T1 pass.

Transport failures are mapped onto the hub's error taxonomy (BUILD-CONTRACT section 4):
429 -> ``BACKEND_RATE_LIMITED``, 401/403 -> ``BACKEND_AUTH``, 502/503/504 ->
``BACKEND_UNAVAILABLE``, other 4xx/5xx -> ``BACKEND_ERROR`` unless the error body's ``code``
already names a taxonomy class, unparseable bodies and streams -> ``MALFORMED_RESPONSE``,
socket timeouts -> ``TIMEOUT_NO_OUTPUT`` / ``TIMEOUT_PARTIAL``. A reply that lost its
``tool_calls`` (a bridge that flattened them into ``<tool_call>`` text) is graded through
``graders.bridge_passthrough`` and reported as ``capability-absent`` (lock 7: a tradeoff to
present, not a model failure). Every class seen is listed in ``error_classes_hit``.

Secrets travel by environment-variable NAME only (``bearer_env``); the value is read at call
time, never printed, and a named-but-unset variable fails every check closed with
``CREDENTIAL_MISSING`` before any request is sent.

``--fake`` spins the inference-hub fake server (imported lazily by path, so this module has no
import-time dependency on it) through a matrix of fault flags and asserts every mapping above.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import secrets
import socket
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from graders import bridge_passthrough
from graders.tool_fidelity import grade_tool_call, schema_errors

NAME = "endpoint-eval-t1"

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]
HUB_DIR = REPO_ROOT / "tools" / "mcp" / "inference-hub"
FAKE_SERVER_PATH = HUB_DIR / "testing" / "fake_openai_v1.py"
FAKE_MODEL = "gpt-5.2"

BACKEND_AUTH = "BACKEND_AUTH"
BACKEND_RATE_LIMITED = "BACKEND_RATE_LIMITED"
BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
BACKEND_ERROR = "BACKEND_ERROR"
MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
TIMEOUT_NO_OUTPUT = "TIMEOUT_NO_OUTPUT"
TIMEOUT_PARTIAL = "TIMEOUT_PARTIAL"
CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
CAPABILITY_ABSENT = bridge_passthrough.CAPABILITY_ABSENT
TAXONOMY = frozenset(
    {
        "REGISTRY_UNAVAILABLE",
        "UNKNOWN_MODEL",
        "MODEL_DISABLED",
        "ENDPOINT_DISABLED",
        "CALLER_DENIED",
        CREDENTIAL_MISSING,
        "REFUSED_SECRET_IN_PROMPT",
        "UNSUPPORTED_CAPABILITY",
        "INVALID_ARGUMENT",
        BACKEND_AUTH,
        BACKEND_RATE_LIMITED,
        BACKEND_UNAVAILABLE,
        BACKEND_ERROR,
        MALFORMED_RESPONSE,
        TIMEOUT_NO_OUTPUT,
        TIMEOUT_PARTIAL,
        "BUDGET_EXCEEDED",
        "CONCURRENCY_SATURATED",
        "HALTED",
    }
)

PROBE_TOOL_NAME = "probe_echo"
ECHO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"echo": {"type": "string"}},
    "required": ["echo"],
    "additionalProperties": False,
}
CASE_NAMES = ("models_list", "echo", "usage", "tools", "json_schema", "stream")

FakeRow = tuple[str, str, dict[str, Any], str | None]
FAKE_MATRIX: tuple[FakeRow, ...] = (
    ("healthy", "openai", {}, None),
    ("rate-limited", "openai", {"rate_limit_every": 2}, BACKEND_RATE_LIMITED),
    ("unavailable", "openai", {"fail_every": 2}, BACKEND_UNAVAILABLE),
    ("malformed", "openai", {"malformed": True}, MALFORMED_RESPONSE),
    ("bridge-drop", "openai", {"drop_tool_calls": True}, CAPABILITY_ABSENT),
    ("unauthenticated", "hf-router", {}, BACKEND_AUTH),
)


class WireError(Exception):
    """A transport-level failure already mapped onto the error taxonomy."""

    def __init__(
        self, error_class: str, message: str, status: int | None = None
    ) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.status = status


@dataclass
class Case:
    name: str
    passed: bool
    error_class: str | None = None
    detail: str = ""
    findings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "error_class": self.error_class,
            "detail": self.detail,
            "findings": list(self.findings),
        }


@dataclass
class Client:
    """Minimal urllib client for one ``/v1`` base URL."""

    base_url: str
    bearer: str | None = None
    timeout_s: float = 10.0
    calls: list[str] = field(default_factory=list)

    def _request(self, path: str, payload: Any | None) -> urllib.request.Request:
        url = self.base_url.rstrip("/") + path
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.bearer:
            headers["Authorization"] = f"Bearer {self.bearer}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        self.calls.append(path)
        return urllib.request.Request(
            url, data=data, headers=headers, method="GET" if data is None else "POST"
        )

    def get_json(self, path: str) -> dict[str, Any]:
        return self._json_exchange(path, None)

    def post_json(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._json_exchange(path, dict(payload))

    def _json_exchange(self, path: str, payload: Any | None) -> dict[str, Any]:
        request = self._request(path, payload)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise _http_error(error) from None
        except urllib.error.URLError as error:
            raise _url_error(error) from None
        except TimeoutError:
            raise WireError(TIMEOUT_NO_OUTPUT, "read timed out") from None
        return _parse_object(raw)

    def post_stream(
        self, path: str, payload: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Collect the ``data:`` chunks of an SSE reply; ``[DONE]`` is mandatory."""
        request = self._request(path, {**payload, "stream": True})
        chunks: list[dict[str, Any]] = []
        done = False
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                for line in response:
                    stripped = line.strip()
                    if not stripped.startswith(b"data:"):
                        continue
                    body = stripped[len(b"data:") :].strip()
                    if body == b"[DONE]":
                        done = True
                        break
                    chunks.append(_parse_object(body))
        except urllib.error.HTTPError as error:
            raise _http_error(error) from None
        except urllib.error.URLError as error:
            raise _url_error(error) from None
        except TimeoutError:
            error_class = TIMEOUT_PARTIAL if chunks else TIMEOUT_NO_OUTPUT
            raise WireError(
                error_class, f"stream timed out after {len(chunks)} chunks"
            ) from None
        if not done:
            raise WireError(
                MALFORMED_RESPONSE,
                f"stream ended without [DONE] after {len(chunks)} chunks",
            )
        return chunks


def _parse_object(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except ValueError:
        raise WireError(MALFORMED_RESPONSE, "body is not JSON") from None
    if not isinstance(parsed, dict):
        raise WireError(MALFORMED_RESPONSE, "body is not a JSON object")
    return parsed


def classify_status(status: int, body: Mapping[str, Any] | None = None) -> str:
    """Taxonomy class for an HTTP error; a hub-shaped ``error.code`` wins over the status."""
    error = body.get("error") if body else None
    code = error.get("code") if isinstance(error, Mapping) else None
    if isinstance(code, str) and code in TAXONOMY:
        return code
    if status in (401, 403):
        return BACKEND_AUTH
    if status == 429:
        return BACKEND_RATE_LIMITED
    if status in (502, 503, 504):
        return BACKEND_UNAVAILABLE
    return BACKEND_ERROR


def _http_error(error: urllib.error.HTTPError) -> WireError:
    raw = error.read()
    body: dict[str, Any] | None
    try:
        parsed = json.loads(raw) if raw else None
        body = parsed if isinstance(parsed, dict) else None
    except ValueError:
        body = None
    return WireError(
        classify_status(error.code, body), f"HTTP {error.code}", error.code
    )


def _url_error(error: urllib.error.URLError) -> WireError:
    reason = error.reason
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return WireError(TIMEOUT_NO_OUTPUT, "connect timed out")
    return WireError(BACKEND_UNAVAILABLE, f"connection failed: {type(reason).__name__}")


def reply_parts(
    body: Mapping[str, Any],
) -> tuple[str | None, Mapping[str, Any], Mapping[str, Any]]:
    choices = body.get("choices")
    if (
        not isinstance(choices, list)
        or not choices
        or not isinstance(choices[0], Mapping)
    ):
        raise WireError(MALFORMED_RESPONSE, "no choices in reply")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise WireError(MALFORMED_RESPONSE, "choice has no message")
    content = message.get("content")
    return (content if isinstance(content, str) else None), message, choice


def probe_tool(nonce: str, name: str = PROBE_TOOL_NAME) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Echo probe; call it once with the nonce {nonce}.",
            "parameters": {
                "type": "object",
                "properties": {"nonce": {"type": "string"}},
                "required": ["nonce"],
                "additionalProperties": False,
            },
        },
    }


def tool_prompt(nonce: str, name: str = PROBE_TOOL_NAME) -> str:
    return (
        f"Call the {name} tool exactly once with nonce={nonce} as its only "
        f'argument, i.e. {{"nonce": "{nonce}"}}. Do not answer in prose.'
    )


def echo_prompt(nonce: str) -> str:
    return f"Reply with exactly this token and nothing else: {nonce}"


def _chat(model: str, text: str, **extra: Any) -> dict[str, Any]:
    return {"model": model, "messages": [{"role": "user", "content": text}], **extra}


def grade_tool_reply(
    body: Mapping[str, Any], nonce: str, name: str = PROBE_TOOL_NAME
) -> Case:
    """One tool_call naming ``name`` with ``{"nonce": nonce}`` and a tool_call id."""
    content, message, choice = reply_parts(body)
    calls = message.get("tool_calls")
    emitted = (
        [call for call in calls if isinstance(call, Mapping)]
        if isinstance(calls, list)
        else []
    )
    if not emitted:
        expected = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"id": "expected_call", "type": "function"}]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
        observed = {
            "choices": [
                {
                    "message": {"content": content, "tool_calls": emitted},
                    "finish_reason": choice.get("finish_reason"),
                }
            ]
        }
        report = bridge_passthrough.compare(expected, observed)
        return Case(
            "tools",
            False,
            CAPABILITY_ABSENT,
            f"no tool_calls in reply (finish_reason={choice.get('finish_reason')!r})",
            report.findings,
        )
    grade = grade_tool_call(emitted, {"name": name, "args": {"nonce": [nonce]}})
    reasons = list(grade.reasons)
    call_id = emitted[0].get("id")
    if not isinstance(call_id, str) or not call_id:
        reasons.append("tool_call_id-missing")
    detail = ";".join(reasons) or f"tool_call_id={call_id} content={content!r}"
    return Case("tools", not reasons, None, detail, tuple(reasons))


def grade_json_reply(body: Mapping[str, Any], schema: Mapping[str, Any]) -> Case:
    content, _, _ = reply_parts(body)
    if content is None:
        return Case("json_schema", False, None, "content is not a string")
    try:
        parsed = json.loads(content)
    except ValueError:
        return Case("json_schema", False, None, "content is not JSON")
    errors = schema_errors(parsed, schema)
    return Case("json_schema", not errors, None, ";".join(errors), tuple(errors))


def grade_usage(body: Mapping[str, Any]) -> Case:
    usage = body.get("usage")
    if not isinstance(usage, Mapping):
        return Case("usage", False, None, "usage missing")
    missing = [
        key
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if not isinstance(usage.get(key), int) or isinstance(usage.get(key), bool)
    ]
    return Case("usage", not missing, None, ";".join(f"usage.{key}" for key in missing))


def assemble_stream(chunks: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    for chunk in chunks:
        choices = chunk.get("choices")
        if (
            not isinstance(choices, list)
            or not choices
            or not isinstance(choices[0], Mapping)
        ):
            continue
        delta = choices[0].get("delta")
        content = delta.get("content") if isinstance(delta, Mapping) else None
        if isinstance(content, str):
            pieces.append(content)
    return "".join(pieces)


def _guarded(name: str, check: Callable[[], Case]) -> Case:
    try:
        return check()
    except WireError as error:
        return Case(name, False, error.error_class, str(error))


def run(
    base_url: str,
    *,
    model: str,
    bearer_env: str | None = None,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    """Run the T1 checks against ``base_url`` (which ends in ``/v1``)."""
    nonce = secrets.token_hex(6)
    bearer = os.environ.get(bearer_env) if bearer_env else None
    if bearer_env and not bearer:
        cases = [
            Case(name, False, CREDENTIAL_MISSING, f"{bearer_env} is not set")
            for name in CASE_NAMES
        ]
        return _summarize(cases, nonce)
    client = Client(base_url, bearer, timeout_s)
    cases: list[Case] = []
    echo_body: dict[str, Any] = {}
    echo_text: list[str] = []

    def models_list() -> Case:
        body = client.get_json("/models")
        data = body.get("data")
        ids = (
            [entry.get("id") for entry in data if isinstance(entry, Mapping)]
            if isinstance(data, list)
            else []
        )
        listed = [model_id for model_id in ids if isinstance(model_id, str)]
        if not listed:
            return Case("models_list", False, None, "no models listed")
        return Case("models_list", True, None, f"model_listed={model in listed}")

    def echo() -> Case:
        body = client.post_json("/chat/completions", _chat(model, echo_prompt(nonce)))
        echo_body.update(body)
        content, _, _ = reply_parts(body)
        if content is None or nonce not in content:
            return Case("echo", False, None, "nonce not echoed")
        echo_text.append(content)
        return Case("echo", True, None, f"chars={len(content)}")

    def usage() -> Case:
        if not echo_body:
            return Case("usage", False, None, "no echo reply to inspect")
        return grade_usage(echo_body)

    def tools() -> Case:
        body = client.post_json(
            "/chat/completions",
            _chat(model, tool_prompt(nonce), tools=[probe_tool(nonce)]),
        )
        return grade_tool_reply(body, nonce)

    def json_schema() -> Case:
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": "echo", "strict": True, "schema": ECHO_SCHEMA},
        }
        body = client.post_json(
            "/chat/completions",
            _chat(
                model,
                f"Return the token {nonce} as the echo field.",
                response_format=response_format,
            ),
        )
        return grade_json_reply(body, ECHO_SCHEMA)

    def stream() -> Case:
        chunks = client.post_stream(
            "/chat/completions",
            _chat(model, echo_prompt(nonce), stream_options={"include_usage": True}),
        )
        text = assemble_stream(chunks)
        passed = text == echo_text[0] if echo_text else nonce in text
        detail = (
            f"chunks={len(chunks)}"
            if passed
            else f"streamed text differs (chunks={len(chunks)})"
        )
        return Case("stream", passed, None, detail)

    checks: tuple[tuple[str, Callable[[], Case]], ...] = (
        ("models_list", models_list),
        ("echo", echo),
        ("usage", usage),
        ("tools", tools),
        ("json_schema", json_schema),
        ("stream", stream),
    )
    for name, check in checks:
        cases.append(_guarded(name, check))
    return _summarize(cases, nonce)


def _summarize(cases: list[Case], nonce: str) -> dict[str, Any]:
    passed = sum(1 for case in cases if case.passed)
    classes = sorted({case.error_class for case in cases if case.error_class})
    return {
        "pass_at_1": passed / len(cases),
        "cases": [case.as_dict() for case in cases],
        "error_classes_hit": classes,
        "nonce": nonce,
    }


def load_fake_server(hub_dir: Path = HUB_DIR) -> Any | None:
    """``FakeOpenAIServer`` imported by path from the inference-hub tree; None when absent."""
    if not (hub_dir / "testing" / "fake_openai_v1.py").is_file():
        return None
    if str(hub_dir) not in sys.path:
        sys.path.insert(0, str(hub_dir))
    module: ModuleType = importlib.import_module("testing.fake_openai_v1")
    return module.FakeOpenAIServer


def run_fake_matrix(server_class: Any, *, timeout_s: float = 10.0) -> dict[str, Any]:
    """Run every FAKE_MATRIX row against a fresh fake; report the healthy run and the classes."""
    rows: list[dict[str, Any]] = []
    healthy: dict[str, Any] = {}
    classes: set[str] = set()
    for label, profile, faults, expected in FAKE_MATRIX:
        server = server_class(profile, **faults)
        server.start()
        try:
            result = run(server.base_url, model=FAKE_MODEL, timeout_s=timeout_s)
        finally:
            server.stop()
        hit = set(result["error_classes_hit"])
        classes |= hit
        if expected is None:
            healthy = result
            ok = result["pass_at_1"] == 1.0
        else:
            ok = expected in hit
        rows.append(
            {"label": label, "expected": expected, "hit": sorted(hit), "ok": ok}
        )
    return {
        "pass_at_1": healthy.get("pass_at_1", 0.0),
        "cases": healthy.get("cases", []),
        "error_classes_hit": sorted(classes),
        "matrix": rows,
        "ok": bool(rows) and all(row["ok"] for row in rows),
    }


def _failed_cases(cases: list[dict[str, Any]]) -> str:
    return ",".join(
        f"{case['name']}:{case['error_class'] or 'failed'}"
        for case in cases
        if not case["passed"]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contract_suite",
        description="T1 contract suite over an OpenAI-compatible /v1 face.",
    )
    parser.add_argument("--base-url", help="OpenAI-compatible base URL ending in /v1")
    parser.add_argument("--model", default=FAKE_MODEL)
    parser.add_argument(
        "--bearer-env", default=None, help="NAME of the env var holding the bearer"
    )
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="run the fault matrix against the inference-hub fake server",
    )
    args = parser.parse_args(argv)
    if args.fake:
        server_class = load_fake_server()
        if server_class is None:
            print(f"FAILED:{NAME} fake-server-missing {FAKE_SERVER_PATH}")
            return 1
        result = run_fake_matrix(server_class, timeout_s=args.timeout_s)
        ok = result["ok"]
        bad = ",".join(row["label"] for row in result["matrix"] if not row["ok"])
    elif not args.base_url:
        print(f"FAILED:{NAME} --base-url or --fake is required")
        return 1
    else:
        result = run(
            args.base_url,
            model=args.model,
            bearer_env=args.bearer_env,
            timeout_s=args.timeout_s,
        )
        ok = result["pass_at_1"] == 1.0
        bad = _failed_cases(result["cases"])
    summary = (
        f"pass_at_1={result['pass_at_1']:.2f} cases={len(result['cases'])} "
        f"classes={len(result['error_classes_hit'])}"
    )
    if ok:
        print(f"SUCCESS:{NAME} {summary}")
        return 0
    print(f"FAILED:{NAME} {summary} failed={bad}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

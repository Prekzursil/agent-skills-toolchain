#!/usr/bin/env python3
"""Stdlib client for inference-hub's ``/v1`` face and ``/healthz`` (the TUI client).

The hub (BUILD-CONTRACT section 4) listens on ``127.0.0.1:8901`` and speaks
standard OpenAI ``/v1``: ``GET /v1/models``, ``POST /v1/chat/completions`` (JSON or
SSE when ``stream`` is true) plus ``GET /healthz``. This client speaks exactly those
routes. Budget status and the timed fan-out live on the MCP face (``POST /mcp``,
tools ``budget_status`` / ``chat_many`` / ``probe``), reached through the stdio shim
``.agents/scripts/inference_hub_stdio.py``; :meth:`InferenceClient.budget_status`
says so instead of guessing.

Routing is read-only: :meth:`InferenceClient.route` loads ``.agents/routing-policy.json``
and ``.agents/models.json`` through the repo's own validators (imported by path from
``<repo>/.agents/scripts``) and falls back loudly to the registry ``slots`` when the
policy is missing or invalid. No call accepts a base URL, an API key, a provider or
extra headers: credentials are the hub's business, by environment-variable NAME only
(L6), and OpenRouter never reaches Cursor or Claude callers (L1).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import http.client
import importlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from types import ModuleType
from typing import Any, Protocol

__all__ = [
    "CLIENT_ERROR",
    "DEFAULT_BASE_URL",
    "FORBIDDEN_KWARGS",
    "HUB_UNREACHABLE",
    "HttpResponse",
    "HttpTransport",
    "InferenceClient",
    "InferenceClientError",
    "default_http",
    "main",
]

NAME = "inference-client"
DEFAULT_BASE_URL = "http://127.0.0.1:8901"
DEFAULT_TIMEOUT_S = 60.0
HEALTH_TIMEOUT_S = 2.0
DEFAULT_POLL_INTERVAL_S = 0.25
MAX_FAN_OUT = 16
REGISTRY_ENV = "INFERENCE_HUB_REGISTRY"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "scripts"
DEFAULT_REGISTRY_PATH = REPO_ROOT / ".agents" / "models.json"
SLOT_NAMES = ("large", "small", "subagent", "web_search", "summary", "embed")
FORBIDDEN_KWARGS = frozenset({"base_url", "api_key", "headers", "provider"})

# Taxonomy classes (BUILD-CONTRACT section 4) this client raises on its own.
REGISTRY_UNAVAILABLE = "REGISTRY_UNAVAILABLE"
UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
TIMEOUT_NO_OUTPUT = "TIMEOUT_NO_OUTPUT"
# Client-side codes, outside the hub taxonomy: the hub was never reached, or the
# failure happened inside this process.
HUB_UNREACHABLE = "HUB_UNREACHABLE"
CLIENT_ERROR = "CLIENT_ERROR"

_DETACH_KWARGS: dict[str, Any] = (
    {
        "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
    }
    if sys.platform == "win32"
    else {"start_new_session": True}
)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class InferenceClientError(Exception):
    """A failed call: ``code`` is a taxonomy class, a client code or an HTTP status."""

    def __init__(
        self, code: str | int, message: str, *, status: int | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(f"{code}: {message}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {"code": self.code, "message": self.message, "status": self.status}
        }


class HttpResponse(Protocol):
    """What a transport returns: HTTP errors arrive as responses, never raised."""

    status: int

    def read(self) -> bytes: ...

    def readline(self) -> bytes: ...

    def getheader(self, name: str, default: str | None = None) -> str | None: ...

    def close(self) -> None: ...


HttpTransport = Callable[[urllib.request.Request, float], HttpResponse]


class _ErrorResponse:
    """Adapter that lets an ``HTTPError`` be read like a normal response."""

    def __init__(self, error: urllib.error.HTTPError) -> None:
        self.status = error.code
        self._error = error

    def read(self) -> bytes:
        return self._error.read()

    def readline(self) -> bytes:
        return self._error.readline()

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self._error.headers.get(name, default)

    def close(self) -> None:
        self._error.close()


def default_http(request: urllib.request.Request, timeout: float) -> HttpResponse:
    """urllib transport: no proxies (the hub is loopback), HTTP errors returned."""
    try:
        return _OPENER.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        return _ErrorResponse(error)


def _normalize_base_url(url: str) -> str:
    text = url.strip().rstrip("/")
    if not text.startswith(("http://", "https://")):
        raise ValueError(f"base_url must be an http(s) URL, got {url!r}")
    if text.endswith("/v1"):
        text = text[: -len("/v1")]
    return text


def _reject_kwargs(kw: Mapping[str, Any]) -> None:
    forbidden = sorted(FORBIDDEN_KWARGS.intersection(kw))
    if forbidden:
        raise ValueError(
            f"{forbidden[0]!r} is never accepted: the hub owns endpoints and "
            "credentials (by environment-variable name only)"
        )
    if "stream" in kw:
        raise ValueError("chat() never takes 'stream'; use stream_chat()")


def _transport_code(error: OSError) -> str:
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    return TIMEOUT_NO_OUTPUT if isinstance(reason, TimeoutError) else HUB_UNREACHABLE


def _io_error(context: str, error: Exception) -> InferenceClientError:
    code = _transport_code(error) if isinstance(error, OSError) else MALFORMED_RESPONSE
    return InferenceClientError(code, f"{context}: {type(error).__name__}: {error}")


def _loads(raw: bytes | str, context: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError as error:
        raise InferenceClientError(
            MALFORMED_RESPONSE, f"{context}: non-JSON body ({type(error).__name__})"
        ) from error


def _parse_json(raw: bytes, status: int, context: str) -> Any:
    if status < 400:
        return _loads(raw, context)
    try:
        return json.loads(raw)
    except ValueError as error:
        raise InferenceClientError(
            status, f"{context}: HTTP {status} with a non-JSON body", status=status
        ) from error


def _error_fields(error: Any, status: int) -> tuple[str | int, str]:
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message")
        return (
            code if isinstance(code, str) and code else status,
            str(message) if message else f"HTTP {status}",
        )
    if isinstance(error, str) and error:
        return status, error
    return status, f"HTTP {status}"


def _raise_for_error(status: int, payload: Any) -> None:
    error = payload.get("error") if isinstance(payload, dict) else None
    if error is None and status < 400:
        return
    code, message = _error_fields(error, status)
    raise InferenceClientError(code, message, status=status)


def _read_body(response: HttpResponse, context: str) -> tuple[int, bytes]:
    try:
        return response.status, response.read()
    except (OSError, http.client.HTTPException) as error:
        raise _io_error(context, error) from error


def _iter_sse(response: HttpResponse, context: str) -> Iterator[dict[str, Any]]:
    while True:
        try:
            line = response.readline()
        except (OSError, http.client.HTTPException) as error:
            raise _io_error(context, error) from error
        if not line:
            raise InferenceClientError(
                MALFORMED_RESPONSE, f"{context}: stream ended before [DONE]"
            )
        text = line.decode("utf-8", errors="replace").strip()
        if not text.startswith("data:"):
            continue
        data = text[len("data:") :].strip()
        if data == "[DONE]":
            return
        chunk = _loads(data, context)
        if not isinstance(chunk, dict):
            raise InferenceClientError(
                MALFORMED_RESPONSE, f"{context}: chunk is not a JSON object"
            )
        yield chunk


def _as_messages(prompt: str | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(prompt, str):
        return [{"role": "user", "content": prompt}]
    return [dict(message) for message in prompt]


def _import_script(name: str) -> ModuleType:
    path = SCRIPTS_DIR / f"{name}.py"
    if not path.is_file():
        raise ImportError(f"{path} is missing")
    scripts_dir = str(SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return importlib.import_module(name)


def _registry_shape_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "registry must be a JSON object"
    for section in ("endpoints", "models"):
        rows = payload.get(section)
        if not isinstance(rows, dict) or not all(
            isinstance(row, dict) for row in rows.values()
        ):
            return f"registry.{section} must be an object of objects"
    return None


def _row_status(model: Mapping[str, Any], endpoint: Mapping[str, Any]) -> str:
    if model.get("enabled") is not True or endpoint.get("enabled") is not True:
        return "disabled"
    return str(model.get("status"))


def _str_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _slot_rungs(registry: Mapping[str, Any], task_class: str) -> list[dict[str, Any]]:
    slots = registry.get("slots")
    if not isinstance(slots, dict):
        slots = {}
    order = [name for name in SLOT_NAMES if name != task_class]
    if task_class in SLOT_NAMES:
        order.insert(0, task_class)
    rungs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for slot in order:
        model_id = slots.get(slot)
        if not isinstance(model_id, str) or model_id in seen:
            continue
        model = registry["models"].get(model_id)
        if model is None:
            continue
        seen.add(model_id)
        endpoint_id = str(model.get("endpoint"))
        endpoint = registry["endpoints"].get(endpoint_id) or {}
        rungs.append(
            {
                "rung": slot,
                "ref": model_id,
                "kind": "model",
                "model_id": model_id,
                "endpoint": endpoint_id,
                "status": _row_status(model, endpoint),
                "source": "slots",
            }
        )
    return rungs


class InferenceClient:
    """Client for one inference-hub: ``/v1`` + ``/healthz`` over HTTP, registry read-only.

    ``base_url`` is the hub ROOT (``http://127.0.0.1:8901``); a trailing ``/v1`` is
    stripped. ``registry_path`` defaults to ``INFERENCE_HUB_REGISTRY`` or the repo's
    ``.agents/models.json``; ``policy_path`` defaults to the ``routing-policy.json``
    beside the registry. ``http`` is an injectable transport (see :data:`HttpTransport`).
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        registry_path: pathlib.Path | str | None = None,
        policy_path: pathlib.Path | str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        http: HttpTransport | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.timeout_s = float(timeout_s)
        self._http: HttpTransport = default_http if http is None else http
        registry = (
            registry_path or os.environ.get(REGISTRY_ENV) or DEFAULT_REGISTRY_PATH
        )
        self.registry_path = pathlib.Path(registry)
        self.policy_path = (
            pathlib.Path(policy_path)
            if policy_path is not None
            else self.registry_path.parent / "routing-policy.json"
        )
        self.poll_interval_s = DEFAULT_POLL_INTERVAL_S
        self.last_stream_mode: str | None = None
        self._sleep: Callable[[float], None] = time.sleep
        self._clock: Callable[[], float] = time.monotonic

    # -- transport ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> HttpResponse:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json, text/event-stream"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            return self._http(request, self.timeout_s if timeout is None else timeout)
        except (OSError, http.client.HTTPException) as error:
            raise _io_error(f"{method} {path}", error) from error

    def _request_json(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        context = f"{method} {path}"
        response = self._request(method, path, body, timeout=timeout)
        try:
            status, raw = _read_body(response, context)
        finally:
            response.close()
        payload = _parse_json(raw, status, context)
        _raise_for_error(status, payload)
        return payload

    @staticmethod
    def _chat_body(
        model: str,
        messages: Sequence[Mapping[str, Any]],
        kw: Mapping[str, Any],
        *,
        stream: bool,
    ) -> dict[str, Any]:
        _reject_kwargs(kw)
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty registry model id or alias")
        body: dict[str, Any] = {
            "model": model,
            "messages": [dict(message) for message in messages],
            **kw,
        }
        if stream:
            body["stream"] = True
        return body

    # -- /healthz and /v1 ------------------------------------------------------------
    def health(self) -> dict[str, Any] | None:
        """``GET /healthz`` as a dict, or None when the hub is down or answers oddly."""
        try:
            payload = self._request_json("GET", "/healthz", timeout=HEALTH_TIMEOUT_S)
        except InferenceClientError:
            return None
        return payload if isinstance(payload, dict) else None

    def models(self) -> list[dict[str, Any]]:
        """``GET /v1/models`` -> the ``data`` rows (the hub omits cursor-* and openrouter)."""
        payload = self._request_json("GET", "/v1/models")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise InferenceClientError(
                MALFORMED_RESPONSE, "GET /v1/models: expected {data: [...]}"
            )
        for item in data:
            if not isinstance(item, dict):
                raise InferenceClientError(
                    MALFORMED_RESPONSE, "GET /v1/models: data rows must be objects"
                )
        return data

    def chat(
        self, model: str, messages: Sequence[Mapping[str, Any]], **kw: Any
    ) -> dict[str, Any]:
        """``POST /v1/chat/completions``; the OpenAI ``chat.completion`` object.

        ``kw`` passes through (``max_tokens``, ``temperature``, ``tools``, ...).
        ``base_url`` / ``api_key`` / ``headers`` / ``provider`` raise ``ValueError``;
        an OpenAI error object raises :class:`InferenceClientError` whose ``code`` is
        the hub taxonomy class (or the HTTP status when the object carries none).
        """
        body = self._chat_body(model, messages, kw, stream=False)
        payload = self._request_json("POST", "/v1/chat/completions", body)
        if not isinstance(payload, dict):
            raise InferenceClientError(
                MALFORMED_RESPONSE, "POST /v1/chat/completions: expected a JSON object"
            )
        return payload

    def stream_chat(
        self, model: str, messages: Sequence[Mapping[str, Any]], **kw: Any
    ) -> Iterator[dict[str, Any]]:
        """Yield the SSE ``data:`` chunks of a streamed completion until ``[DONE]``.

        The request is sent on the first ``next()``; errors surface there. The hub
        emulates streaming from the full result and says so in
        ``X-Inference-Hub-Stream``, mirrored into ``last_stream_mode``.
        """
        body = self._chat_body(model, messages, kw, stream=True)
        context = "POST /v1/chat/completions (stream)"
        response = self._request("POST", "/v1/chat/completions", body)
        try:
            content_type = response.getheader("Content-Type") or ""
            if response.status >= 400 or not content_type.startswith(
                "text/event-stream"
            ):
                status, raw = _read_body(response, context)
                _raise_for_error(status, _parse_json(raw, status, context))
                raise InferenceClientError(
                    MALFORMED_RESPONSE, f"{context}: expected text/event-stream"
                )
            self.last_stream_mode = response.getheader("X-Inference-Hub-Stream")
            yield from _iter_sse(response, context)
        finally:
            response.close()

    def _chat_captured(
        self, model: str, messages: list[dict[str, Any]], kw: Mapping[str, Any]
    ) -> dict[str, Any]:
        try:
            return self.chat(model, messages, **kw)
        except InferenceClientError as error:
            payload = error.to_payload()
        except Exception as error:  # the fan-out contract: no item may escape
            payload = {
                "error": {
                    "code": CLIENT_ERROR,
                    "message": f"{type(error).__name__}: {error}",
                    "status": None,
                }
            }
        payload["error"]["model"] = model
        return payload

    def chat_many(
        self,
        prompt: str | Sequence[Mapping[str, Any]],
        models: Sequence[str],
        *,
        n: int = 1,
        **kw: Any,
    ) -> list[dict[str, Any]]:
        """Fan one prompt out to ``models`` (``n`` replicas each) on threads.

        The result keeps request order; a failed item is ``{"error": {"code",
        "message", "status", "model"}}`` and no exception escapes. The MCP face's
        ``chat_many`` additionally reports ``wall_ms`` / ``max_item_ms`` / ``sum_item_ms``.
        """
        _reject_kwargs(kw)
        if n < 1:
            raise ValueError("n must be >= 1")
        messages = _as_messages(prompt)
        targets = [model for model in models for _ in range(n)]
        if not targets:
            return []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(targets), MAX_FAN_OUT)
        ) as pool:
            return list(
                pool.map(
                    lambda model: self._chat_captured(model, messages, kw), targets
                )
            )

    def budget_status(self) -> dict[str, Any]:
        """Not on ``/v1``: budget lives on the MCP face (``tools/call budget_status``)."""
        raise InferenceClientError(
            UNSUPPORTED_CAPABILITY,
            "budget_status is an MCP-face tool, not a /v1 route: call "
            "`python .agents/scripts/inference_hub_stdio.py --call budget_status {}` "
            "or POST /mcp tools/call budget_status",
        )

    # -- lifecycle ---------------------------------------------------------------------
    def ensure_running(
        self,
        start_cmd: Sequence[str] | None = None,
        *,
        timeout_s: float = 20.0,
        popen: Callable[..., Any] = subprocess.Popen,
    ) -> bool:
        """Probe ``/healthz``; when down and ``start_cmd`` is given, spawn it once and poll.

        The child is detached (own session / process group, stdio to DEVNULL) so the
        hub outlives the TUI. Returns True once ``/healthz`` answers, False when the
        hub is down and nothing was started or the deadline passed.
        """
        if self.health() is not None:
            return True
        if not start_cmd:
            return False
        try:
            popen(
                list(start_cmd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_DETACH_KWARGS,
            )
        except OSError as error:
            raise InferenceClientError(
                HUB_UNREACHABLE, f"start_cmd failed: {type(error).__name__}: {error}"
            ) from error
        deadline = self._clock() + timeout_s
        while self.health() is None:
            if self._clock() >= deadline:
                return False
            self._sleep(self.poll_interval_s)
        return True

    # -- registry + policy (read-only, hub not needed) ---------------------------------
    def _registry(self) -> dict[str, Any]:
        try:
            models_mod: ModuleType | None = _import_script("models_control_plane")
        except ImportError:
            models_mod = None
        try:
            if models_mod is None:
                payload: Any = json.loads(
                    self.registry_path.read_text(encoding="utf-8")
                )
            else:
                payload = models_mod.load_registry(self.registry_path)
        except (OSError, ValueError) as error:
            raise InferenceClientError(
                REGISTRY_UNAVAILABLE,
                f"{self.registry_path}: {type(error).__name__}: {error}",
            ) from error
        problem = _registry_shape_error(payload)
        if problem is not None:
            raise InferenceClientError(
                REGISTRY_UNAVAILABLE, f"{self.registry_path}: {problem}"
            )
        return payload

    def registry_models(self) -> list[dict[str, Any]]:
        """Every registry model row, flattened; reads the file only (hub may be down)."""
        registry = self._registry()
        endpoints: Mapping[str, Any] = registry["endpoints"]
        rows: list[dict[str, Any]] = []
        for model_id, model in registry["models"].items():
            endpoint_id = str(model.get("endpoint"))
            endpoint: Mapping[str, Any] = endpoints.get(endpoint_id) or {}
            deny = set(_str_list(endpoint.get("denyCallers"))) | set(
                _str_list(model.get("denyCallers"))
            )
            rows.append(
                {
                    "id": str(model_id),
                    "endpoint": endpoint_id,
                    "remote_id": str(model.get("remoteId") or model_id),
                    "label": str(model.get("label") or ""),
                    "enabled": model.get("enabled") is True
                    and endpoint.get("enabled") is True,
                    "status": _row_status(model, endpoint),
                    "tier": model.get("tier"),
                    "tags": _str_list(model.get("tags")),
                    "deny_callers": sorted(deny),
                    "sidecar_only": endpoint.get("sidecarOnly") is True,
                }
            )
        return rows

    def route(self, task_class: str) -> list[dict[str, Any]]:
        """Ordered rungs for ``task_class``: the policy's P/A/C/E, else the slots.

        Policy records come from ``routing_policy.route`` (``rung``, ``ref``, ``kind``,
        ``model_id``, ``endpoint``, ``status``) plus ``source: "policy"``. When the
        policy file is missing or invalid the validator prints one ``FAILED:`` line on
        stderr and the registry ``slots`` are returned (``rung`` = slot name,
        ``source: "slots"``). An unknown class under a valid policy is a ``ValueError``.
        """
        registry = self._registry()
        try:
            policy_mod = _import_script("routing_policy")
        except ImportError as error:
            print(
                f"FAILED:{NAME} {error}; falling back to registry slots",
                file=sys.stderr,
            )
            return _slot_rungs(registry, task_class)
        policy, _source = policy_mod.load_policy_or_fallback(self.policy_path, registry)
        if policy is None:
            return _slot_rungs(registry, task_class)
        try:
            rungs: list[dict[str, Any]] = policy_mod.route(policy, registry, task_class)
        except policy_mod.PolicyError as error:
            raise ValueError(str(error)) from error
        for rung in rungs:
            rung["source"] = "policy"
        return rungs


# -- CLI ---------------------------------------------------------------------------------
def _run(client: InferenceClient, args: argparse.Namespace) -> tuple[Any, str]:
    command: str = args.command
    if command == "health":
        payload = client.health()
        if payload is None:
            raise InferenceClientError(HUB_UNREACHABLE, f"no hub at {client.base_url}")
        return payload, f"ok={payload.get('ok')}"
    if command == "models":
        rows = client.models()
        return rows, f"count={len(rows)}"
    if command == "registry-models":
        rows = client.registry_models()
        return rows, f"count={len(rows)}"
    if command == "chat":
        result = client.chat(args.model, [{"role": "user", "content": args.prompt}])
        return result, f"model={args.model}"
    rungs = client.route(args.task_class)
    sources = ",".join(sorted({str(rung.get("source")) for rung in rungs}))
    return (
        rungs,
        f"class={args.task_class} rungs={len(rungs)} source={sources or 'none'}",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inference_client", description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--registry", default=None, help="path to models.json")
    parser.add_argument("--policy", default=None, help="path to routing-policy.json")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("health", help="GET /healthz")
    commands.add_parser("models", help="GET /v1/models")
    commands.add_parser("registry-models", help="list models.json without the hub")
    chat = commands.add_parser("chat", help="POST /v1/chat/completions")
    chat.add_argument("--model", required=True)
    chat.add_argument("--prompt", required=True)
    route = commands.add_parser("route", help="ordered rungs for a task class")
    route.add_argument("task_class")
    args = parser.parse_args(argv)
    try:
        client = InferenceClient(
            args.base_url,
            registry_path=args.registry,
            policy_path=args.policy,
            timeout_s=args.timeout,
        )
        payload, summary = _run(client, args)
    except (InferenceClientError, ValueError) as error:
        print(f"FAILED:{NAME} {args.command} {error}")
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"SUCCESS:{NAME} {args.command} {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The opt-in ``answer`` lane: Vane (ex-Perplexica) as a self-hosted answer engine.

Gem-hunt program, Wave 3 (decisions G-2, G-4, G-5): a keyless *local-LLM*
cited-answer path that is **OFF by default** (0 RAM idle) and wired only when the
owner opts in -- ``ENABLE_VANE=1`` or a non-empty ``VANE_URL``. The adapter is
pure stdlib and in-process (no child, no new import at hub start); the heavy part
(Vane + the LLM it talks to) is started ON DEMAND with the compose kit in
``deploy/docker-compose.answer-engines.yml`` and evicted the same way. The base
URL is endpoint-agnostic (G-4): on-box today, one ``VANE_URL=https://...`` repoint
to an OVH box later, no rework.

Vane's API, read from the ``v1.12.2`` tag on 2026-09-02 (``docs/API/SEARCH.md``,
``src/app/api/{providers,search}/route.ts``, ``src/lib/models/types.ts``):

* ``GET /api/providers`` -> ``{providers: [{id, name, chatModels: [{name, key}],
  embeddingModels: [{name, key}]}]}``. The ``id`` is a UUID minted per install,
  so it DRIFTS between machines and re-installs -- which is why this adapter
  resolves ids on every call (cached 60 s) instead of pinning them in config,
  accepts provider/model NAMES as well as ids, and always REPORTS what it used.
* ``POST /api/search`` (non-streaming) <- ``{chatModel: {providerId, key},
  embeddingModel: {providerId, key}, optimizationMode: speed|balanced|quality,
  sources: [web|academic|discussions], query, history: [[human|assistant, text]],
  stream: false}`` -> ``{message, sources: [{content, metadata: {title, url}}]}``;
  400 ``{message: 'Missing sources or query'}``; 500 ``{message: 'Search error'}``.
  Note the API drift from Perplexica: ``focusMode: webSearch|academicSearch|...``
  became a ``sources`` array. The tool keeps ``focus`` as its argument and maps
  both vocabularies (``webSearch``->``web``, ``academicSearch``->``academic``,
  ``redditSearch``->``discussions``).

Honesty contract (same lattice as ``adapters.py``): the probe is ``GET
/api/providers``; ``probed`` when it answers, ``absent`` when it does not. Every
failure -- daemon down, timeout, 4xx/5xx, no provider or no embedding model
configured, an unknown provider/model name -- is a truthful ``isError`` naming the
cause. An answer is NEVER fabricated, an empty one is reported as empty, and
``.onion`` source URLs are passed through as strings only (never fetched; see
``docs/legal/onions-lane-envelope.md``).
"""

from __future__ import annotations

import json
import time
from typing import Callable

import onions
from adapters import (
    DEFAULT_TIMEOUT,
    NATIVE,
    PROBE_TIMEOUT,
    AdapterTool,
    Caller,
    SelfHostedAdapter,
    _flag_enabled,
    _lane_killed,
)

PLATFORM = "answer"
ENGINE = "vane"
TOOL_NAME = "selfhosted_answer"
ENABLE_VANE_ENV = "ENABLE_VANE"
VANE_URL_ENV = "VANE_URL"
VANE_TIMEOUT_ENV = "VANE_TIMEOUT_S"
DEFAULT_VANE_URL = "http://127.0.0.1:3000"
DEFAULT_TIMEOUT_S = 120.0  # an LLM answer, not a search hit: minutes, not seconds
MIN_TIMEOUT_S = 1.0
MAX_TIMEOUT_S = 3600.0
PROVIDERS_CACHE_TTL_S = 60
PROVIDERS_PATH = "/api/providers"
SEARCH_PATH = "/api/search"
OPTIMIZATION_MODES = ("speed", "balanced", "quality")
VANE_SOURCES = ("web", "academic", "discussions")
DEFAULT_FOCUS = "webSearch"
# Both vocabularies: Perplexica's focus modes and Vane 1.12's source names.
_FOCUS_TO_SOURCE = {
    "websearch": "web",
    "web": "web",
    "academicsearch": "academic",
    "academic": "academic",
    "redditsearch": "discussions",
    "reddit": "discussions",
    "discussions": "discussions",
    "discussion": "discussions",
}
_FOCUS_ALL = ("all", "*")
_HUMAN_ROLES = ("human", "user")
_ASSISTANT_ROLES = ("assistant", "ai")
_JSON_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
_GET_HEADERS = {"Accept": "application/json"}

_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "the question to answer (Vane searches, reads and cites)",
        },
        "focus": {
            "type": "string",
            "default": DEFAULT_FOCUS,
            "description": (
                "which Vane sources to search: webSearch | academicSearch | "
                "redditSearch (Perplexica names) or Vane's own web | academic | "
                "discussions; comma-join several, 'all' for every source"
            ),
        },
        "optimization": {
            "type": "string",
            "enum": list(OPTIMIZATION_MODES),
            "default": "balanced",
            "description": "speed = fastest answer, quality = best answer (slower)",
        },
        "history": {
            "type": "array",
            "default": [],
            "items": {"type": ["array", "object"]},
            "description": (
                "prior turns, oldest first, as [role, text] pairs (role human | "
                "assistant) or {role, content} objects; passed through to Vane"
            ),
        },
        "chat_provider": {
            "type": "string",
            "default": "",
            "description": (
                "chat provider: its id (UUID from GET /api/providers) or its name; "
                "empty = the first provider that has a chat model (reported back)"
            ),
        },
        "chat_model": {
            "type": "string",
            "default": "",
            "description": (
                "chat model key (e.g. 'llama3.2:3b') or display name; empty = the "
                "provider's first chat model (reported back)"
            ),
        },
        "embedding_provider": {
            "type": "string",
            "default": "",
            "description": (
                "embedding provider id or name; empty = the first provider that has "
                "an embedding model (reported back)"
            ),
        },
        "embedding_model": {
            "type": "string",
            "default": "",
            "description": (
                "embedding model key (e.g. 'nomic-embed-text') or display name; "
                "empty = the provider's first embedding model (reported back)"
            ),
        },
    },
    "required": ["query"],
}


class _AnswerError(Exception):
    """A truthful failure text raised from inside the multi-request call path."""


def resolve_timeout(environ) -> float:
    """``VANE_TIMEOUT_S`` as a float, clamped to [1, 3600]; anything unusable
    (unset, blank, non-numeric, zero, negative) is the 120 s default."""
    raw = str(environ.get(VANE_TIMEOUT_ENV) or "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_S
    if not value > 0:  # also rejects NaN
        return DEFAULT_TIMEOUT_S
    return min(max(value, MIN_TIMEOUT_S), MAX_TIMEOUT_S)


def _text(value) -> str | None:
    """A JSON scalar as text for the source list: strings verbatim, other scalars
    stringified, missing/None stays None. Never invents a value."""
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _model_list(raw) -> list[dict]:
    models: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        name = item.get("name")
        models.append(
            {"name": name if isinstance(name, str) else item["key"], "key": item["key"]}
        )
    return models


def _providers_from(parsed) -> list[dict] | None:
    """Normalize Vane's ``{providers: [...]}`` into ``[{id, name, chat_models,
    embedding_models}]``; ``None`` when the body is not that shape."""
    if not isinstance(parsed, dict) or not isinstance(parsed.get("providers"), list):
        return None
    providers: list[dict] = []
    for item in parsed["providers"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        name = item.get("name")
        providers.append(
            {
                "id": item["id"],
                "name": name if isinstance(name, str) else item["id"],
                "chat_models": _model_list(item.get("chatModels")),
                "embedding_models": _model_list(item.get("embeddingModels")),
            }
        )
    return providers


def _match_provider(providers: list[dict], want: str) -> dict | None:
    for provider in providers:
        if provider["id"] == want:
            return provider
    folded = want.casefold()
    for provider in providers:
        if provider["name"].casefold() == folded:
            return provider
    return None


def _match_model(models: list[dict], want: str) -> dict | None:
    for model in models:
        if model["key"] == want:
            return model
    folded = want.casefold()
    for model in models:
        if model["key"].casefold() == folded or model["name"].casefold() == folded:
            return model
    return None


# --------------------------------------------------------------------------- #
# argument validation -- before any request is spent
# --------------------------------------------------------------------------- #
def _parse_sources(focus) -> tuple[list[str], str]:
    """The caller's ``focus`` -> (Vane ``sources`` list, echo text)."""
    if focus is None:
        focus = ""
    if isinstance(focus, (list, tuple)):
        tokens = [str(t) for t in focus]
        echo = ",".join(tokens)
    elif isinstance(focus, str):
        tokens = focus.replace("+", ",").split(",")
        echo = focus
    else:
        raise ValueError("answer: 'focus' must be a string (or a list of strings)")
    sources: list[str] = []
    for token in tokens:
        key = token.strip().casefold()
        if not key:
            continue
        if key in _FOCUS_ALL:
            picked = list(VANE_SOURCES)
        elif key in _FOCUS_TO_SOURCE:
            picked = [_FOCUS_TO_SOURCE[key]]
        else:
            raise ValueError(
                f"answer: focus {token.strip()!r} has no Vane source; use webSearch | "
                f"academicSearch | redditSearch, or Vane's own "
                f"{'|'.join(VANE_SOURCES)} (comma-join several, or 'all')"
            )
        for source in picked:
            if source not in sources:
                sources.append(source)
    if not sources:
        sources = [_FOCUS_TO_SOURCE[DEFAULT_FOCUS.casefold()]]
        echo = echo.strip() or DEFAULT_FOCUS
    return sources, echo


def _parse_history(history) -> list[list[str]]:
    """Caller history -> Vane's ``[[role, text], ...]`` with role human|assistant."""
    if history is None:
        return []
    shape = (
        "answer: 'history' must be a list of [role, text] pairs (role human | "
        "assistant) or {role, content} objects"
    )
    if not isinstance(history, list):
        raise ValueError(shape)
    turns: list[list[str]] = []
    for item in history:
        if isinstance(item, dict):
            role, text = item.get("role"), item.get("content")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            role, text = item
        else:
            raise ValueError(shape)
        if not isinstance(role, str) or not isinstance(text, str):
            raise ValueError(shape)
        key = role.strip().casefold()
        if key in _HUMAN_ROLES:
            turns.append(["human", text])
        elif key in _ASSISTANT_ROLES:
            turns.append(["assistant", text])
        else:
            raise ValueError(
                f"answer: 'history' role {role!r} is not one of human | user | "
                f"assistant | ai"
            )
    return turns


def _parse_args(args: dict) -> dict:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("answer: 'query' is required (a non-empty string)")
    mode = args.get("optimization")
    mode = "balanced" if mode is None or mode == "" else mode
    if not isinstance(mode, str) or mode.strip().casefold() not in OPTIMIZATION_MODES:
        raise ValueError(
            f"answer: 'optimization' must be one of {'|'.join(OPTIMIZATION_MODES)}"
        )
    sources, focus_echo = _parse_sources(args.get("focus"))
    picks: dict[str, str] = {}
    for field in (
        "chat_provider",
        "chat_model",
        "embedding_provider",
        "embedding_model",
    ):
        value = args.get(field)
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"answer: '{field}' must be a string (id, key or name)")
        picks[field] = value.strip()
    return {
        "query": query.strip(),
        "optimization": mode.strip().casefold(),
        "sources": sources,
        "focus": focus_echo,
        "history": _parse_history(args.get("history")),
        **picks,
    }


class VaneAdapter(SelfHostedAdapter):
    """Front a Vane instance's ``/api/search`` as the ``selfhosted_answer`` tool.

    Keyless from the hub's point of view (Vane holds whatever LLM credentials it
    needs, by its own config); self-hosted and on-demand. ``timeout_s`` is the
    LLM budget for one answer (default 120 s, env ``VANE_TIMEOUT_S``); the
    provider directory is fetched with the short adapter default and cached for
    ``PROVIDERS_CACHE_TTL_S`` because its ids drift but not by the second.
    ``clock`` is injectable so tests can pin the cache without sleeping.
    """

    platform = PLATFORM
    label = "Vane (self-hosted answer engine)"
    prefix = "an"
    kind = "native"  # /api/search IS the answer contract; nothing is emulated
    health_path = PROVIDERS_PATH  # GET first: provider UUIDs drift (Lens 4)
    error_tag = "answer"

    def __init__(
        self,
        base_url: str,
        caller: Caller | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        clock: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(base_url, caller=caller)
        self.timeout_s = float(timeout_s)
        self._clock = clock or time.monotonic
        self._providers_cache: tuple[float, list[dict]] | None = None

    # ---- surface --------------------------------------------------------
    def _build_tools(self) -> list[AdapterTool]:
        return [
            AdapterTool(
                name=TOOL_NAME,
                description=(
                    "Cited answer from a self-hosted Vane (ex-Perplexica) answer engine "
                    "over its own SearXNG + an LLM you point it at: POST /api/search "
                    "(non-streaming). Returns {answer, sources[title, url, snippet], "
                    "providers_used, latency_ms, engine: 'vane'}. Provider/model ids "
                    "are resolved from GET /api/providers on every call (cached 60 s) "
                    "because they drift between installs; omit them to take the first "
                    "chat + first embedding provider/model, which is REPORTED back, or "
                    "pass ids or names. Opt-in lane (ENABLE_VANE=1 or VANE_URL), "
                    "LLM timeout VANE_TIMEOUT_S (default 120 s). Every failure -- "
                    "Vane down, timeout, HTTP error, no provider or embedding model "
                    "configured -- is a truthful error; an answer is never "
                    "fabricated. Source URLs are listed as strings only (a .onion "
                    "source is never fetched)."
                ),
                input_schema=_ANSWER_SCHEMA,
                path=SEARCH_PATH,
                realized_by=NATIVE,
            )
        ]

    def capabilities(self, probe: bool = False) -> dict:
        report = super().capabilities(probe=probe)
        report["engine"] = ENGINE
        report["timeout_s"] = self.timeout_s
        report["providers_cache_ttl_s"] = PROVIDERS_CACHE_TTL_S
        report["probe_path"] = PROVIDERS_PATH
        report["opt_in"] = (
            f"{ENABLE_VANE_ENV}=1 or a non-empty {VANE_URL_ENV} (default OFF; "
            f"{ENABLE_VANE_ENV}=0 is the kill switch)"
        )
        if probe and self._providers_cache is not None:
            report["providers"] = [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "chat_models": [m["key"] for m in p["chat_models"]],
                    "embedding_models": [m["key"] for m in p["embedding_models"]],
                }
                for p in self._providers_cache[1]
            ]
        return report

    # ---- probe: GET /api/providers -------------------------------------
    def probe(self) -> tuple[bool, str]:
        """One GET /api/providers: reachable iff it answers 2xx with the providers
        shape. The result warms the 60 s provider cache. Never raises."""
        if not self.base_url:
            return False, "no base URL configured"
        status, parsed, raw = self._caller(
            "GET",
            self.base_url + PROVIDERS_PATH,
            None,
            dict(_GET_HEADERS),
            PROBE_TIMEOUT,
        )
        if status == 0:
            return False, raw or "unreachable"
        if not (200 <= status < 300):
            return False, f"HTTP {status}: {raw[:120]}"
        providers = _providers_from(parsed)
        if providers is None:
            return False, (
                f"HTTP {status} but the body is not Vane's providers shape "
                f"({raw[:80]!r}); is {self.base_url} really Vane?"
            )
        self._providers_cache = (self._clock(), providers)
        chat = sum(len(p["chat_models"]) for p in providers)
        embedding = sum(len(p["embedding_models"]) for p in providers)
        note = (
            f"HTTP {status} ({len(providers)} providers, {chat} chat models, "
            f"{embedding} embedding models)"
        )
        if not providers or not chat or not embedding:
            note += (
                "; no LLM chat+embedding pair configured yet, so selfhosted_answer "
                "refuses truthfully until Vane is pointed at one (e.g. OLLAMA_BASE_URL)"
            )
        return True, note

    # ---- provider directory (cached 60 s) -------------------------------
    def _get_providers(self) -> tuple[list[dict], bool]:
        """(providers, served_from_cache); raises ``_AnswerError`` truthfully."""
        now = self._clock()
        if self._providers_cache is not None:
            fetched_at, providers = self._providers_cache
            if 0 <= now - fetched_at < PROVIDERS_CACHE_TTL_S:
                return providers, True
        self._providers_cache = None
        status, parsed, raw = self._caller(
            "GET",
            self.base_url + PROVIDERS_PATH,
            None,
            dict(_GET_HEADERS),
            DEFAULT_TIMEOUT,
        )
        if status == 0:
            raise _AnswerError(self._unreachable(raw))
        if not (200 <= status < 300):
            raise _AnswerError(
                f"{self.label} returned HTTP {status} for {PROVIDERS_PATH}: "
                f"{self._detail(parsed, raw)}. No answer is fabricated."
            )
        providers = _providers_from(parsed)
        if providers is None:
            raise _AnswerError(
                f"{self.label} answered HTTP {status} for {PROVIDERS_PATH} but the "
                f"body is not Vane's providers JSON ({raw[:120]!r}); is "
                f"{self.base_url} really Vane? No answer is fabricated."
            )
        self._providers_cache = (now, providers)
        return providers, False

    def _resolve(
        self, providers: list[dict], kind: str, want_provider: str, want_model: str
    ) -> dict:
        """Pick the ``kind`` (chat|embedding) provider+model, honouring explicit ids
        or names and otherwise taking the FIRST available; the pick is reported."""
        models_key = f"{kind}_models"
        names = ", ".join(p["name"] for p in providers) or "none"
        if not providers:
            raise _AnswerError(
                f"{self.label} at {self.base_url} reports no providers configured "
                f"(GET {PROVIDERS_PATH} is empty): point Vane at an LLM first (e.g. "
                f"OLLAMA_BASE_URL=http://host.docker.internal:11434 in "
                f"deploy/docker-compose.answer-engines.yml, or Vane's Settings) and "
                f"retry. No answer is fabricated."
            )
        if want_provider:
            provider = _match_provider(providers, want_provider)
            if provider is None:
                raise _AnswerError(
                    f"{kind} provider {want_provider!r} is not configured in Vane at "
                    f"{self.base_url}; configured providers: {names}. Ids drift "
                    f"between installs -- pass the name, or omit it to take the first "
                    f"available. No answer is fabricated."
                )
            candidates = [provider]
        else:
            candidates = [p for p in providers if p[models_key]]
        selected_by = "caller" if (want_provider or want_model) else "first-available"
        for provider in candidates:
            models = provider[models_key]
            model = _match_model(models, want_model) if want_model else None
            if model is None and not want_model and models:
                model = models[0]
            if model is not None:
                return {
                    "provider_id": provider["id"],
                    "provider": provider["name"],
                    "model_key": model["key"],
                    "model_name": model["name"],
                    "selected_by": selected_by,
                }
        if want_model:
            offered = (
                ", ".join(m["key"] for p in candidates for m in p[models_key]) or "none"
            )
            where = (
                f"provider {candidates[0]['name']!r}"
                if want_provider
                else f"any provider at {self.base_url}"
            )
            raise _AnswerError(
                f"{kind} model {want_model!r} is not offered by {where}; available "
                f"{kind} models: {offered}. Pass a key from GET {PROVIDERS_PATH} or "
                f"omit it to take the first. No answer is fabricated."
            )
        raise _AnswerError(
            f"no {kind} model is configured in Vane at {self.base_url} (providers: "
            f"{names}); Vane needs a chat model AND an embedding model (e.g. "
            f"nomic-embed-text via Ollama) to answer. No answer is fabricated."
        )

    # ---- truthful degradation helpers -----------------------------------
    def _unreachable(self, raw: str) -> str:
        if "timed out" in (raw or "").casefold():
            return (
                f"{self.label} at {self.base_url} did not answer within "
                f"{self.timeout_s:g} s ({raw}); LLM answers can be slow -- raise "
                f"{VANE_TIMEOUT_ENV} (default {DEFAULT_TIMEOUT_S:g}) or use "
                f"optimization='speed'. No answer is fabricated."
            )
        return (
            f"{self.label} at {self.base_url} not reachable ({raw}); start it "
            f"(deploy/run-answer-engines.sh up --vane) or point {VANE_URL_ENV} at a "
            f"running instance. No answer is fabricated."
        )

    @staticmethod
    def _detail(parsed, raw: str) -> str:
        if isinstance(parsed, dict):
            message = parsed.get("message")
            error = parsed.get("error")
            text = str(message) if message else ""
            if error:
                text += f" ({json.dumps(error, ensure_ascii=False)[:160]})"
            if text:
                return text
        return raw[:300] if raw else "(empty body)"

    # ---- result shaping ---------------------------------------------------
    @staticmethod
    def _shape_sources(raw_sources) -> list[dict]:
        shaped: list[dict] = []
        for item in raw_sources if isinstance(raw_sources, list) else []:
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata")
            meta = meta if isinstance(meta, dict) else {}
            snippet = item.get("content")
            if snippet is None:
                snippet = item.get("pageContent")  # the Perplexica-era field name
            shaped.append(
                {
                    "title": _text(meta.get("title")),
                    "url": _text(meta.get("url")),
                    "snippet": _text(snippet),
                }
            )
        return shaped

    # ---- the call path (always truthful) ----------------------------------
    def handle_call(self, name: str, arguments: dict) -> dict:
        tool = self._tool(name)
        if tool is None:
            return self._error(f"unknown answer tool {name!r}")
        if not self.base_url:
            return self._error(
                f"no Vane base URL configured: set {VANE_URL_ENV} (or {ENABLE_VANE_ENV}"
                f"=1 for the default {DEFAULT_VANE_URL}) and start it "
                f"(deploy/run-answer-engines.sh up --vane); {TOOL_NAME} stays absent "
                f"until it answers. No answer is fabricated."
            )
        try:
            spec = _parse_args(arguments or {})
            providers, cached = self._get_providers()
            chat = self._resolve(
                providers, "chat", spec["chat_provider"], spec["chat_model"]
            )
            embedding = self._resolve(
                providers,
                "embedding",
                spec["embedding_provider"],
                spec["embedding_model"],
            )
        except (ValueError, _AnswerError) as exc:
            return self._error(str(exc))
        body = {
            "chatModel": {"providerId": chat["provider_id"], "key": chat["model_key"]},
            "embeddingModel": {
                "providerId": embedding["provider_id"],
                "key": embedding["model_key"],
            },
            "optimizationMode": spec["optimization"],
            "sources": spec["sources"],
            "query": spec["query"],
            "history": spec["history"],
            "stream": False,
        }
        started = self._clock()
        status, parsed, raw = self._caller(
            "POST",
            self.base_url + SEARCH_PATH,
            json.dumps(body).encode("utf-8"),
            dict(_JSON_HEADERS),
            self.timeout_s,
        )
        latency_ms = int(round((self._clock() - started) * 1000))
        if status == 0:
            return self._error(self._unreachable(raw))
        if not (200 <= status < 300):
            return self._error(
                f"{self.label} returned HTTP {status} for {SEARCH_PATH}: "
                f"{self._detail(parsed, raw)}. No answer is fabricated."
            )
        if not isinstance(parsed, dict):
            return self._error(
                f"{self.label} answered HTTP {status} for {SEARCH_PATH} but the body "
                f"is not JSON ({raw[:120]!r}); no answer is fabricated."
            )
        message = parsed.get("message")
        answer = message if isinstance(message, str) else ""
        sources = self._shape_sources(parsed.get("sources"))
        onion_count = sum(1 for s in sources if onions.is_onion_url(s["url"]))
        notes = []
        if not answer.strip():
            notes.append(
                "Vane returned an empty answer (message empty); nothing is padded."
            )
        if onion_count:
            notes.append(
                f"{onion_count} source URL(s) point at .onion hosts: listed as strings "
                f"only, never fetched by this hub ({onions.ENVELOPE_DOC})."
            )
        if not notes:
            notes.append(
                "LLM-generated answer grounded in the listed sources; verify claims "
                "against them (citations like [1] index into sources)."
            )
        return self._ok(
            {
                "tool": TOOL_NAME,
                "engine": ENGINE,
                "base_url": self.base_url,
                "query": spec["query"],
                "focus": spec["focus"],
                "sources_used": spec["sources"],
                "optimization": spec["optimization"],
                "history_turns": len(spec["history"]),
                "answer": answer,
                "sources": sources,
                "onion_sources": onion_count,
                "providers_used": {"chat": chat, "embedding": embedding},
                "providers_cached": cached,
                "latency_ms": latency_ms,
                "note": " ".join(notes),
            }
        )


def build(environ) -> list[SelfHostedAdapter]:
    """The lane entry point ``lanes.py`` calls: ``[]`` unless opted in.

    ``ENABLE_VANE`` explicitly falsey is a kill switch that wins over a set URL;
    otherwise a truthy ``ENABLE_VANE`` (default URL) or a non-empty ``VANE_URL``
    wires exactly one ``VaneAdapter``. No network here -- wiring is free.
    """
    if _lane_killed(environ, ENABLE_VANE_ENV):
        return []
    url = str(environ.get(VANE_URL_ENV) or "").strip()
    if not url and not _flag_enabled(environ, ENABLE_VANE_ENV):
        return []
    return [VaneAdapter(url or DEFAULT_VANE_URL, timeout_s=resolve_timeout(environ))]

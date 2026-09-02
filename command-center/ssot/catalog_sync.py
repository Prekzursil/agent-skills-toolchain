#!/usr/bin/env python3
"""catalog_sync.py -- daily model/MCP catalog sync where THE DIFF IS THE PRODUCT.

Pulls the keyless public catalogs (models.dev, OpenRouter, the Hugging Face router,
the official MCP Registry) plus the loopback ``/v1/models`` of every ENABLED
loopback endpoint in ``.agents/models.json``, normalises each into one row shape,
merges them into ``state/catalog/index.json`` and diffs that index against the
previous run: new / vanished models, rows expiring inside 30 days, rows whose
upstream status is not live, upstream version moves, and hosts that no feed knows
any more (a decommissioned host such as ``api-inference.huggingface.co``).

Rules this script keeps:

* Feeds are INGESTED, never authoritative: the two registries
  (``.agents/agents.json``, ``.agents/models.json``) are read-only here.
* ETag / ``If-Modified-Since`` cache per feed; a 304 leaves the feed file untouched.
* Last-known-good on ANY failure (5xx, timeout, parse error): the previous rows are
  kept and the file is marked ``source_status: "stale"`` with an ``error``. Loopback
  feeds are optional: unreachable is RECORDED as ``unreachable``, not an error.
* An upstream outage is never a failure of this script. Exit 2 only for misuse or a
  bug; the last stdout line is exactly one ``SUCCESS:catalog-sync ...`` or
  ``FAILED:catalog-sync <reason>``.
* Network calls go through the module-level ``fetch`` callable so tests replace it
  with recorded fixtures (``fixtures/catalog/``). No secret is needed or sent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "state" / "catalog"
DEFAULT_REGISTRY = REPO_ROOT / ".agents" / "models.json"

SCHEMA_VERSION = 1
EXPIRY_WINDOW_DAYS = 30
DEFAULT_TIMEOUT_SECONDS = 20.0
LOOPBACK_TIMEOUT_SECONDS = 5.0
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
LIVE_STATUSES = frozenset({"live", "active"})
REPORT_ITEM_LIMIT = 10

# Closed row schema. ``version`` is carried so ``version_moves`` can be computed for
# the MCP Registry feed; every other key is optional and omitted when unknown.
MODEL_KEYS = (
    "id",
    "provider",
    "context",
    "pricing",
    "expiration_date",
    "status",
    "supports_tools",
    "supports_structured_output",
    "version",
)
PRICING_KEYS = ("input", "output")
DIFF_KINDS = (
    "new_models",
    "vanished_models",
    "expired",
    "status_not_live",
    "version_moves",
    "decommissioned_hosts",
)

OPENROUTER_HOST = "openrouter.ai"
HF_ROUTER_HOST = "router.huggingface.co"
MCP_REGISTRY_HOST = "registry.modelcontextprotocol.io"

JsonRows = list[dict[str, Any]]
Parser = Callable[[Any], tuple[JsonRows, list[str]]]


class CatalogSyncError(Exception):
    """Misuse or a bug -- the only way this script exits 2."""


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    parser: Parser
    optional: bool = False
    timeout: float = DEFAULT_TIMEOUT_SECONDS


@dataclass
class FeedResult:
    feed: str
    url: str
    status: str
    fetched_at: str | None
    models: JsonRows
    hosts: list[str]
    error: str | None = None

    def document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "feed": self.feed,
            "url": self.url,
            "fetched_at": self.fetched_at,
            "source_status": self.status,
            "hosts": self.hosts,
            "models": self.models,
        }
        if self.error is not None:
            doc["error"] = self.error
        return doc


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write_text(path: Path, content: str) -> None:
    """Publish text with an fsync + same-directory atomic replacement.

    Copied from ``.agents/scripts/mcp_control_plane.py`` (atomic_write_text) so this
    script stays a single stdlib file on the box.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def load_json_object(path: Path) -> dict[str, Any] | None:
    """The JSON object at ``path``, or None when absent, unreadable or not an object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def host_of(url: str) -> str | None:
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


def is_loopback(url: str) -> bool:
    return host_of(url) in LOOPBACK_HOSTS


def validate_url(url: str) -> None:
    """Only ``https://`` anywhere or ``http://`` on loopback may be fetched."""
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise CatalogSyncError(f"feed url is malformed: {url}") from exc
    if not parsed.hostname:
        raise CatalogSyncError(f"feed url has no host: {url}")
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS:
        return
    raise CatalogSyncError(f"feed url must be https or loopback http: {url}")


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_date(value: str) -> str | None:
    """``YYYY-MM-DD`` when the first ten characters parse as a date, else None."""
    try:
        return date.fromisoformat(value.strip()[:10]).isoformat()
    except ValueError:
        return None


def normalise_row(raw: Any) -> dict[str, Any] | None:
    """Project a parser row onto the closed ``MODEL_KEYS`` schema.

    Unknown keys are dropped, values are coerced, unusable values are omitted, and a
    row without a non-empty string ``id`` is discarded.
    """
    if not isinstance(raw, dict):
        return None
    model_id = raw.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        return None
    row: dict[str, Any] = {"id": model_id.strip()}
    provider = raw.get("provider")
    if isinstance(provider, str) and provider.strip():
        row["provider"] = provider.strip()
    context = _coerce_int(raw.get("context"))
    if context is not None:
        row["context"] = context
    pricing = raw.get("pricing")
    if isinstance(pricing, dict):
        prices = {
            key: price
            for key in PRICING_KEYS
            if (price := _coerce_float(pricing.get(key))) is not None
        }
        if prices:
            row["pricing"] = prices
    expiration = raw.get("expiration_date")
    if isinstance(expiration, str) and expiration.strip():
        row["expiration_date"] = _iso_date(expiration) or expiration.strip()
    status = raw.get("status")
    if isinstance(status, str) and status.strip():
        row["status"] = status.strip()
    for flag in ("supports_tools", "supports_structured_output"):
        if flag in raw:
            row[flag] = bool(raw[flag])
    version = raw.get("version")
    if version is not None:
        row["version"] = str(version)
    return row


def sort_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("feed", "")), str(row.get("provider", "")), str(row["id"]))


def row_key(row: Mapping[str, Any]) -> str:
    return "|".join(sort_key(row))


# ---------------------------------------------------------------------------
# Parsers: recorded upstream shape -> (rows, hosts)
# ---------------------------------------------------------------------------
def _require_object(payload: Any, feed: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CatalogSyncError(f"{feed}: payload is not a JSON object")
    return payload


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_models_dev(payload: Any) -> tuple[JsonRows, list[str]]:
    """``https://models.dev/api.json``: ``{provider: {api, env, models: {id: {...}}}}``."""
    providers = _require_object(payload, "models-dev")
    rows: JsonRows = []
    hosts: set[str] = set()
    for provider_id, provider in providers.items():
        if not isinstance(provider, dict):
            continue
        api = provider.get("api")
        host = host_of(api) if isinstance(api, str) else None
        if host:
            hosts.add(host)
        models = provider.get("models")
        for model_id, model in (models if isinstance(models, dict) else {}).items():
            if not isinstance(model, dict):
                continue
            limit = model.get("limit")
            cost = model.get("cost")
            row: dict[str, Any] = {
                "id": model_id,
                "provider": provider_id,
                "context": (limit or {}).get("context")
                if isinstance(limit, dict)
                else None,
                "pricing": cost if isinstance(cost, dict) else None,
                "status": model.get("status"),
                "supports_tools": bool(model.get("tool_call")),
            }
            if "structured_output" in model:
                row["supports_structured_output"] = model["structured_output"]
            rows.append(row)
    return rows, sorted(hosts)


def parse_openrouter(payload: Any) -> tuple[JsonRows, list[str]]:
    """``/api/v1/models``: ``{data: [{id, context_length, pricing, supported_parameters, expiration_date?}]}``.

    OpenRouter prices are USD per token; the row keeps USD per 1M tokens like the
    other feeds.
    """
    body = _require_object(payload, "openrouter")
    rows: JsonRows = []
    for entry in _as_list(body.get("data")):
        if not isinstance(entry, dict) or "id" not in entry:
            continue
        model_id = str(entry["id"])
        row: dict[str, Any] = {
            "id": model_id,
            "context": entry.get("context_length"),
            "expiration_date": entry.get("expiration_date"),
        }
        if "/" in model_id:
            row["provider"] = model_id.split("/", 1)[0]
        pricing = entry.get("pricing")
        if isinstance(pricing, dict):
            row["pricing"] = {
                "input": _per_million(pricing.get("prompt")),
                "output": _per_million(pricing.get("completion")),
            }
        params = entry.get("supported_parameters")
        if isinstance(params, list):
            row["supports_tools"] = "tools" in params
            row["supports_structured_output"] = "structured_outputs" in params
        rows.append(row)
    return rows, [OPENROUTER_HOST]


def _per_million(per_token: Any) -> float | None:
    value = _coerce_float(per_token)
    return None if value is None else round(value * 1_000_000, 6)


def parse_hf_router(payload: Any) -> tuple[JsonRows, list[str]]:
    """``/v1/models``: one row per ``(model, providers[])`` entry with status + supports_*."""
    body = _require_object(payload, "hf-router")
    rows: JsonRows = []
    for entry in _as_list(body.get("data")):
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        providers = [p for p in _as_list(entry.get("providers")) if isinstance(p, dict)]
        if not providers:
            rows.append({"id": entry["id"]})
            continue
        for provider in providers:
            rows.append(
                {
                    "id": entry["id"],
                    "provider": provider.get("provider"),
                    "context": provider.get("context_length"),
                    "pricing": provider.get("pricing"),
                    "status": provider.get("status"),
                    **{
                        flag: provider[flag]
                        for flag in ("supports_tools", "supports_structured_output")
                        if flag in provider
                    },
                }
            )
    return rows, [HF_ROUTER_HOST]


def parse_mcp_registry(payload: Any) -> tuple[JsonRows, list[str]]:
    """``/v0.1/servers``: ``{servers: [{server: {name, version}, _meta: {...: {status}}}]}``."""
    body = _require_object(payload, "mcp-registry")
    rows: JsonRows = []
    for entry in _as_list(body.get("servers")):
        if not isinstance(entry, dict):
            continue
        server = entry.get("server")
        if not isinstance(server, dict) or "name" not in server:
            continue
        meta = entry.get("_meta")
        official = (
            meta.get("io.modelcontextprotocol.registry/official")
            if isinstance(meta, dict)
            else None
        )
        rows.append(
            {
                "id": server["name"],
                "version": server.get("version"),
                "status": official.get("status")
                if isinstance(official, dict)
                else None,
            }
        )
    return rows, [MCP_REGISTRY_HOST]


def parse_openai_models(payload: Any) -> tuple[JsonRows, list[str]]:
    """OpenAI-shape ``/v1/models`` (the loopback endpoints). Loopback hosts are not
    catalog hosts, so a stopped daemon can never look like a decommissioned host."""
    body = _require_object(payload, "openai-models")
    rows: JsonRows = [
        {"id": entry["id"], "provider": entry.get("owned_by")}
        for entry in _as_list(body.get("data"))
        if isinstance(entry, dict) and "id" in entry
    ]
    return rows, []


FEEDS: tuple[Feed, ...] = (
    Feed("models-dev", "https://models.dev/api.json", parse_models_dev),
    Feed("openrouter", "https://openrouter.ai/api/v1/models", parse_openrouter),
    Feed("hf-router", "https://router.huggingface.co/v1/models", parse_hf_router),
    Feed(
        "mcp-registry",
        "https://registry.modelcontextprotocol.io/v0.1/servers?version=latest",
        parse_mcp_registry,
    ),
)


def loopback_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/models"


def loopback_feeds(registry: Mapping[str, Any]) -> list[Feed]:
    """One optional feed per ENABLED endpoint whose ``baseUrl`` is loopback."""
    feeds: list[Feed] = []
    endpoints = registry.get("endpoints")
    for endpoint_id, endpoint in (
        endpoints if isinstance(endpoints, dict) else {}
    ).items():
        if not isinstance(endpoint, dict) or not endpoint.get("enabled"):
            continue
        base_url = endpoint.get("baseUrl")
        if not isinstance(base_url, str) or not is_loopback(base_url):
            continue
        feeds.append(
            Feed(
                str(endpoint_id),
                loopback_url(base_url),
                parse_openai_models,
                optional=True,
                timeout=LOOPBACK_TIMEOUT_SECONDS,
            )
        )
    return feeds


# ---------------------------------------------------------------------------
# Transport (replaced by tests)
# ---------------------------------------------------------------------------
def fetch(
    url: str, headers: Mapping[str, str], timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> tuple[int, dict[str, str], bytes]:
    """GET ``url`` -> ``(status, headers, body)``. HTTP errors are returned as their
    status; transport failures (refused, timeout, DNS) raise ``OSError``."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "catalog-sync/1 (+stdlib)", **headers}
    )
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- feed URLs are the fixed public catalogs plus loopback endpoints from the registry; validate_url() rejects anything else before this call
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


# ---------------------------------------------------------------------------
# One feed: cache, fetch, normalise, last-known-good
# ---------------------------------------------------------------------------
def _feed_path(root: Path, feed: Feed) -> Path:
    return root / f"{feed.name}.json"


def _cache_path(root: Path, feed: Feed) -> Path:
    return root / ".cache" / f"{feed.name}.headers.json"


def _last_known_good(root: Path, feed: Feed) -> dict[str, Any] | None:
    previous = load_json_object(_feed_path(root, feed))
    if previous is None or not isinstance(previous.get("models"), list):
        return None
    return previous


def _carry_forward(
    feed: Feed, previous: dict[str, Any] | None, status: str, error: str
) -> FeedResult:
    """The last-known-good rows (or nothing) under a non-ok status."""
    return FeedResult(
        feed=feed.name,
        url=feed.url,
        status=status,
        fetched_at=previous.get("fetched_at") if previous else None,
        models=list(previous["models"]) if previous else [],
        hosts=list(previous.get("hosts") or []) if previous else [],
        error=error,
    )


def _conditional_headers(cache: dict[str, Any] | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if cache:
        if isinstance(cache.get("etag"), str):
            headers["If-None-Match"] = cache["etag"]
        if isinstance(cache.get("last_modified"), str):
            headers["If-Modified-Since"] = cache["last_modified"]
    return headers


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def sync_feed(
    feed: Feed, root: Path, *, offline: bool = False, now: str | None = None
) -> FeedResult:
    """Fetch one feed into ``root/<feed>.json`` honouring the cache and last-known-good.

    Returns the result that went into the file (or, for a 304, the untouched file).
    """
    validate_url(feed.url)
    now = now or utc_now_iso()
    previous = _last_known_good(root, feed)
    failure_status = "unreachable" if feed.optional else "stale"
    cache_path = _cache_path(root, feed)

    if offline:
        result = _carry_forward(feed, previous, "stale", "offline")
        atomic_write_json(_feed_path(root, feed), result.document())
        return result

    try:
        status, headers, body = fetch(
            feed.url, _conditional_headers(load_json_object(cache_path)), feed.timeout
        )
    except Exception as exc:  # transport failure: refused, timeout, reset, DNS
        result = _carry_forward(
            feed, previous, failure_status, f"{type(exc).__name__}: {exc}"
        )
        atomic_write_json(_feed_path(root, feed), result.document())
        return result

    if status == 304:
        if previous is not None:
            return FeedResult(
                feed=feed.name,
                url=feed.url,
                status="unchanged",
                fetched_at=previous.get("fetched_at"),
                models=list(previous["models"]),
                hosts=list(previous.get("hosts") or []),
            )
        cache_path.unlink(missing_ok=True)
        result = _carry_forward(
            feed, None, failure_status, "http 304 without a cached body"
        )
        atomic_write_json(_feed_path(root, feed), result.document())
        return result

    if not 200 <= status < 300:
        result = _carry_forward(feed, previous, failure_status, f"http {status}")
        atomic_write_json(_feed_path(root, feed), result.document())
        return result

    try:
        raw_rows, hosts = feed.parser(
            json.loads(body.decode("utf-8", errors="replace"))
        )
    except (ValueError, CatalogSyncError) as exc:
        result = _carry_forward(
            feed, previous, failure_status, f"parse: {type(exc).__name__}: {exc}"
        )
        atomic_write_json(_feed_path(root, feed), result.document())
        return result

    models = sorted(
        (row for row in map(normalise_row, raw_rows) if row is not None), key=sort_key
    )
    result = FeedResult(feed.name, feed.url, "ok", now, models, sorted(set(hosts)))
    atomic_write_json(_feed_path(root, feed), result.document())
    etag = _header(headers, "ETag")
    last_modified = _header(headers, "Last-Modified")
    if etag or last_modified:
        atomic_write_json(
            cache_path, {"url": feed.url, "etag": etag, "last_modified": last_modified}
        )
    else:
        cache_path.unlink(missing_ok=True)
    return result


# ---------------------------------------------------------------------------
# Index + diff
# ---------------------------------------------------------------------------
def build_index(results: Mapping[str, FeedResult], *, now: str) -> dict[str, Any]:
    rows: JsonRows = []
    hosts: set[str] = set()
    feeds: dict[str, Any] = {}
    by_feed: dict[str, int] = {}
    by_source_status: dict[str, int] = {}
    for name, result in results.items():
        rows.extend({"feed": name, **model} for model in result.models)
        hosts.update(result.hosts)
        entry: dict[str, Any] = {
            "source_status": result.status,
            "fetched_at": result.fetched_at,
            "count": len(result.models),
        }
        if result.error is not None:
            entry["error"] = result.error
        feeds[name] = entry
        by_feed[name] = len(result.models)
        by_source_status[result.status] = by_source_status.get(result.status, 0) + 1
    rows.sort(key=sort_key)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generated_at": now,
        "feeds": dict(sorted(feeds.items())),
        "hosts": sorted(hosts),
        "counts": {
            "total": len(rows),
            "by_feed": dict(sorted(by_feed.items())),
            "by_source_status": dict(sorted(by_source_status.items())),
        },
        "models": rows,
    }


def expiring_within(row: Mapping[str, Any], now_iso: str, *, days: int) -> bool:
    """True when ``expiration_date`` is a date on or before ``now + days`` (past included)."""
    value = row.get("expiration_date")
    if not isinstance(value, str):
        return False
    parsed = _iso_date(value)
    if parsed is None:
        return False
    today = date.fromisoformat(now_iso[:10])
    return date.fromisoformat(parsed) <= today + timedelta(days=days)


def diff_index(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """The product: what changed between two indexes.

    Transition kinds (reported once): ``new_models``, ``vanished_models``,
    ``version_moves``, ``decommissioned_hosts``. Standing-attention kinds (repeated
    every run while true): ``expired`` (expiration_date inside the 30-day window) and
    ``status_not_live`` (upstream status set and not live/active).
    """
    now = now or utc_now_iso()
    before = {row_key(row): row for row in _as_list((previous or {}).get("models"))}
    after = {row_key(row): row for row in _as_list(current.get("models"))}
    new_models = [after[key] for key in sorted(after.keys() - before.keys())]
    vanished = [before[key] for key in sorted(before.keys() - after.keys())]
    expired = [
        row
        for row in after.values()
        if expiring_within(row, now, days=EXPIRY_WINDOW_DAYS)
    ]
    not_live = [
        row
        for row in after.values()
        if isinstance(row.get("status"), str) and row["status"] not in LIVE_STATUSES
    ]
    moves: JsonRows = []
    for key in sorted(after.keys() & before.keys()):
        old, new = before[key].get("version"), after[key].get("version")
        if old is not None and new is not None and old != new:
            moves.append(
                {
                    "feed": after[key]["feed"],
                    "id": after[key]["id"],
                    "from": old,
                    "to": new,
                }
            )
    hosts_before = set(_as_list((previous or {}).get("hosts")))
    hosts_after = set(_as_list(current.get("hosts")))
    diff: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "generated_at": now,
        "new_models": new_models,
        "vanished_models": vanished,
        "expired": sorted(expired, key=sort_key),
        "status_not_live": sorted(not_live, key=sort_key),
        "version_moves": moves,
        "decommissioned_hosts": sorted(hosts_before - hosts_after),
    }
    diff["counts"] = {kind: len(diff[kind]) for kind in DIFF_KINDS}
    return diff


def _describe(item: Any) -> str:
    if isinstance(item, str):
        return item
    label = "/".join(
        part for part in (item.get("feed"), item.get("provider"), item["id"]) if part
    )
    extras = [
        f"{key}={item[key]}"
        for key in ("expiration_date", "status", "from", "to")
        if key in item
    ]
    return label + (f" [{', '.join(extras)}]" if extras else "")


def render_report(diff: Mapping[str, Any], index: Mapping[str, Any]) -> str:
    lines = [f"catalog-sync diff {diff.get('generated_at', '')}".rstrip()]
    for name, entry in sorted(index.get("feeds", {}).items()):
        lines.append(f"  {name}: {entry['source_status']} ({entry['count']} models)")
    for kind in DIFF_KINDS:
        items = list(diff.get(kind, []))
        lines.append(f"{kind}: {len(items)}")
        for item in items[:REPORT_ITEM_LIMIT]:
            lines.append(f"  - {_describe(item)}")
        if len(items) > REPORT_ITEM_LIMIT:
            lines.append(f"  ... {len(items) - REPORT_ITEM_LIMIT} more")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def load_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CatalogSyncError(f"registry not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise CatalogSyncError(f"registry is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise CatalogSyncError(f"registry is not a JSON object: {path}")
    return payload


def _stored_result(feed: Feed, root: Path) -> FeedResult | None:
    """A feed not synced this run still contributes its file to the merged index."""
    previous = _last_known_good(root, feed)
    if previous is None:
        return None
    return FeedResult(
        feed=feed.name,
        url=str(previous.get("url") or feed.url),
        status=str(previous.get("source_status") or "stale"),
        fetched_at=previous.get("fetched_at"),
        models=list(previous["models"]),
        hosts=list(previous.get("hosts") or []),
        error=previous.get("error"),
    )


def run(
    root: Path,
    registry_path: Path,
    feed_names: list[str] | None = None,
    *,
    offline: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Sync the selected feeds, rebuild the merged index, write the diff."""
    now = now or utc_now_iso()
    root = Path(root)
    if root.exists() and not root.is_dir():
        raise CatalogSyncError(f"root is not a directory: {root}")
    registry = load_registry(Path(registry_path))
    all_feeds = list(FEEDS) + loopback_feeds(registry)
    known = {feed.name for feed in all_feeds}
    selected = set(feed_names) if feed_names else known
    for name in sorted(selected - known):
        raise CatalogSyncError(f"unknown feed: {name}")

    previous_index = load_json_object(root / "index.json")
    results: dict[str, FeedResult] = {}
    synced: dict[str, FeedResult] = {}
    for feed in all_feeds:
        if feed.name in selected:
            result = sync_feed(feed, root, offline=offline, now=now)
            synced[feed.name] = result
            results[feed.name] = result
        else:
            stored = _stored_result(feed, root)
            if stored is not None:
                results[feed.name] = stored

    index = build_index(results, now=now)
    diff = diff_index(previous_index, index, now=now)
    atomic_write_json(root / "index.json", index)
    atomic_write_json(root / "last-diff.json", diff)

    counts = {
        "feeds": len(synced),
        "ok": sum(1 for r in synced.values() if r.status in ("ok", "unchanged")),
        "stale": sum(1 for r in synced.values() if r.status == "stale"),
        "unreachable": sum(1 for r in synced.values() if r.status == "unreachable"),
        "new": diff["counts"]["new_models"],
        "vanished": diff["counts"]["vanished_models"],
    }
    return {
        "generated_at": now,
        "root": str(root),
        "feeds": {name: index["feeds"][name] for name in sorted(synced)},
        "counts": counts,
        "index": {"total": index["counts"]["total"], "hosts": index["hosts"]},
        "diff": diff,
    }


def _success_line(counts: Mapping[str, int]) -> str:
    return (
        "SUCCESS:catalog-sync "
        f"feeds={counts['feeds']} ok={counts['ok']} stale={counts['stale']} "
        f"unreachable={counts['unreachable']} new={counts['new']} vanished={counts['vanished']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="catalog_sync.py",
        description="Daily catalog sync; the diff against the previous index is the product.",
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="state root")
    parser.add_argument(
        "--registry", type=Path, default=DEFAULT_REGISTRY, help=".agents/models.json"
    )
    parser.add_argument(
        "--feeds", default="", help="comma-separated subset of feed names"
    )
    parser.add_argument(
        "--offline", action="store_true", help="no network; last-known-good only"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    feed_names = [
        name.strip() for name in args.feeds.split(",") if name.strip()
    ] or None
    try:
        summary = run(args.root, args.registry, feed_names, offline=args.offline)
    except CatalogSyncError as exc:
        print(f"FAILED:catalog-sync {exc}")
        return 2
    except Exception as exc:  # a bug, not an outage: still one terminal line
        print(f"FAILED:catalog-sync {type(exc).__name__}: {exc}")
        return 2
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        index = load_json_object(Path(summary["root"]) / "index.json") or {}
        print(render_report(summary["diff"], index))
    print(_success_line(summary["counts"]))
    return 0


if __name__ == "__main__":  # pragma: no cover -- module entrypoint
    sys.exit(main())

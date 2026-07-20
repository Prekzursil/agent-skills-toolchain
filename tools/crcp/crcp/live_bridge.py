"""Persistent ChatGPT live polling bridge + shared HTTP status server.

The HTTP server exposes read-only status without authentication.  Every
mutation is protected by a shared secret and a per-client token bucket.
This process only consumes Codex credentials; it never refreshes OAuth.
"""

from __future__ import annotations

import hmac
import json
import math
import os
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .auth import codex_auth_status
from .bridge import ChatGPTBridge, export_conversation_pack
from .bus import DEFAULT_PROJECT, publish_envelope
from .envelope import utc_now
from .singleton import SingletonLockError, acquire_singleton_lock
from .spool import EventSpool, event_key


DEFAULT_HTTP_RATE_PER_MINUTE = 6.0
HTTP_TOKEN_HEADER = "X-CRCP-Token"
# Keep at most this many chatgpt_conv_* / envelope_* versions per conversation id.
DEFAULT_OUTBOX_MAX_VERSIONS = 5


def _crcp_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_update_time(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0
    return 0.0


def _positive_float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    if not math.isfinite(parsed) or parsed <= 0:
        return default
    return parsed


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_http_token(env: Mapping[str, str]) -> tuple[str | None, str | None]:
    """Load a shared HTTP token without returning it in diagnostic text."""
    token = env.get("CRCP_HTTP_TOKEN", "").strip()
    if token:
        return token, None

    token_file = env.get("CRCP_HTTP_TOKEN_FILE", "").strip()
    if not token_file:
        return None, None
    try:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        return None, f"token_file_unreadable:{type(exc).__name__}"
    if not token:
        return None, "token_file_empty"
    return token, None


class ClientTokenBucket:
    """Thread-safe token bucket keyed by the direct socket peer address."""

    def __init__(self, rate_per_minute: float = DEFAULT_HTTP_RATE_PER_MINUTE):
        if not math.isfinite(rate_per_minute) or rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive and finite")
        self.rate_per_minute = rate_per_minute
        self.capacity = max(1.0, rate_per_minute)
        self._refill_per_second = rate_per_minute / 60.0
        self._clients: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def consume(self, client: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        with self._lock:
            tokens, updated = self._clients.get(client, (self.capacity, current))
            tokens = min(self.capacity, tokens + max(0.0, current - updated) * self._refill_per_second)
            if tokens >= 1.0:
                self._clients[client] = (tokens - 1.0, current)
                allowed = True
                retry_after = 0
            else:
                self._clients[client] = (tokens, current)
                allowed = False
                retry_after = max(1, math.ceil((1.0 - tokens) / self._refill_per_second))

            # Bound memory when clients churn. Entries idle long enough to be
            # full have no state worth retaining.
            if len(self._clients) > 4096:
                stale_before = current - (self.capacity / self._refill_per_second)
                self._clients = {
                    key: state for key, state in self._clients.items() if state[1] >= stale_before
                }
                while len(self._clients) > 4096:
                    self._clients.pop(next(iter(self._clients)))
            return allowed, retry_after


class HttpMutationPolicy:
    """Fail-closed shared-token authentication plus per-client throttling."""

    def __init__(
        self,
        *,
        token: str | None,
        open_mode: bool,
        rate_per_minute: float,
        configuration_error: str | None = None,
    ):
        self._token = token
        self.open_mode = open_mode
        self.configuration_error = configuration_error
        self.rate_limiter = ClientTokenBucket(rate_per_minute)

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> "HttpMutationPolicy":
        values = os.environ if env is None else env
        token, error = _load_http_token(values)
        return cls(
            token=token,
            open_mode=_enabled(values.get("CRCP_HTTP_OPEN")),
            rate_per_minute=_positive_float(
                values.get("CRCP_HTTP_RATE_LIMIT_PER_MINUTE"),
                DEFAULT_HTTP_RATE_PER_MINUTE,
            ),
            configuration_error=error,
        )

    @property
    def mode(self) -> str:
        if self.open_mode:
            return "local_open"
        if self._token is not None:
            return "token"
        return "disabled"

    def authorize(self, client: str, supplied_token: str | None) -> tuple[int, int]:
        """Return ``(HTTP status, retry-after seconds)``; 204 means allowed."""
        allowed, retry_after = self.rate_limiter.consume(client)
        if not allowed:
            return 429, retry_after
        if self.open_mode:
            return 204, 0
        if self._token is None:
            return 503, 0
        candidate = supplied_token or ""
        if not hmac.compare_digest(candidate.encode("utf-8"), self._token.encode("utf-8")):
            return 401, 0
        return 204, 0


class LiveBridgeState:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {
            "conversations": {},
            "last_poll_at": None,
            "last_error": None,
            "polls": 0,
            "fetches": 0,
            "publishes": 0,
            "auth_reloads": 0,
        }
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.data, stream, indent=2, default=str)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
            try:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except BaseException:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise


class LiveBridgeService:
    """Poll conversations, fetch deltas, pack envelopes, and optionally publish."""

    def __init__(
        self,
        *,
        poll_interval: float = 60.0,
        outbox: Path | None = None,
        state_path: Path | None = None,
        project: str = DEFAULT_PROJECT,
        auto_publish: bool = True,
        list_limit: int = 30,
        http_host: str = "127.0.0.1",
        http_port: int = 8820,
        enable_http: bool = True,
        http_mutation_policy: HttpMutationPolicy | None = None,
        spool_path: Path | None = None,
        singleton_path: Path | None = None,
    ):
        root = _crcp_root()
        self.poll_interval = poll_interval
        self.outbox = outbox or (root / "outbox")
        self.state = LiveBridgeState(state_path or (root / "reports" / "live_bridge_state.json"))
        self.project = project
        self.auto_publish = auto_publish
        self.list_limit = list_limit
        self.http_host = http_host
        self.http_port = http_port
        self.enable_http = enable_http
        self.http_mutation_policy = http_mutation_policy or HttpMutationPolicy.from_environment()
        self.spool = EventSpool(spool_path or (root / "reports" / "spool.db"))
        self.singleton_path = singleton_path or (root / "reports" / "live_bridge.lock")
        self.bridge = ChatGPTBridge()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._http: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.status: dict[str, Any] = {
            "running": False,
            "started_at": None,
            "last_cycle": None,
            "auth": {},
        }

    def auth_snapshot(self) -> dict[str, Any]:
        snap = codex_auth_status()
        access = snap.get("access_token") or {}
        return {
            "status": snap.get("status"),
            "last_refresh": snap.get("last_refresh"),
            "last_refresh_age_days": snap.get("last_refresh_age_days"),
            "would_proactive_refresh_by_age": snap.get("would_proactive_refresh_by_age"),
            "access_seconds_until_exp": access.get("seconds_until_exp"),
            "access_expired": access.get("expired"),
            "within_5min_of_exp": access.get("within_5min_of_exp"),
            "file_mtime_utc": snap.get("file_mtime_utc"),
        }

    def _check_auth_reload(self) -> None:
        """Reload bridge credentials when auth.json mtime changes (token-consumer)."""
        from .credential_snapshot import is_stale_mtime

        auth_path = self.bridge.codex_home / "auth.json"
        if not auth_path.is_file():
            return
        known = (
            self.bridge._snapshot.mtime_ns
            if getattr(self.bridge, "_snapshot", None) is not None
            else None
        )
        if is_stale_mtime(auth_path, known):
            self.bridge.reload()
            self.state.data["auth_reloads"] = int(self.state.data.get("auth_reloads") or 0) + 1
            self.state.data["last_auth_reload_at"] = utc_now()
            self.state.save()

    def rotate_outbox(
        self,
        conversation_id: str,
        *,
        max_versions: int = DEFAULT_OUTBOX_MAX_VERSIONS,
    ) -> dict[str, int]:
        """Keep only the newest ``max_versions`` packs/envelopes for a conversation."""
        import re

        cid = re.sub(r"[^\w.\-]+", "_", str(conversation_id))[:80]
        removed = 0
        kept = 0
        for kind in ("chatgpt_conv", "envelope"):
            files = sorted(
                self.outbox.glob(f"{kind}_{cid}_*.json"),
                key=lambda p: p.name,
                reverse=True,
            )
            for i, path in enumerate(files):
                if i < max_versions:
                    kept += 1
                    continue
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
        return {"kept": kept, "removed": removed}

    def cycle_once(self) -> dict[str, Any]:
        """Run one poll cycle and return its summary.

        Delta gate (strict): compare list-endpoint ``update_time`` to the saved
        state file *before* any GET conversation or outbox write. Only fetch and
        publish when the remote timestamp is strictly newer than last seen.
        """
        with self._lock:
            self._check_auth_reload()
            summary: dict[str, Any] = {
                "at": utc_now(),
                "listed": 0,
                "skipped_unchanged": 0,
                "new_or_updated": [],
                "fetched": [],
                "spooled": [],
                "already_acked": [],
                "published": [],
                "errors": [],
                "rotated": [],
            }
            try:
                listing = self.bridge.list_conversations(offset=0, limit=self.list_limit)
                items = listing.get("items") or []
                summary["listed"] = len(items)
                summary["total"] = listing.get("total")
                known: dict[str, Any] = self.state.data.setdefault("conversations", {})
                for item in items:
                    cid = item.get("id")
                    if not cid:
                        continue
                    raw_update = item.get("update_time")
                    update_time = _parse_update_time(raw_update)
                    previous = known.get(cid) or {}
                    previous_time = _parse_update_time(previous.get("update_time"))
                    # Strict delta: never fetch/write when update_time is not newer.
                    # Also skip when both sides parse to 0 (missing timestamps) and
                    # we already have a checkpoint for this id.
                    if cid in known and update_time <= previous_time:
                        summary["skipped_unchanged"] = int(summary["skipped_unchanged"]) + 1
                        continue
                    if cid in known and update_time == 0.0 and previous_time == 0.0:
                        summary["skipped_unchanged"] = int(summary["skipped_unchanged"]) + 1
                        continue
                    summary["new_or_updated"].append(
                        {"id": cid, "title": item.get("title"), "update_time": raw_update}
                    )
                    try:
                        conversation = self.bridge.get_conversation(cid)
                        # Prefer conversation-body update_time when present so the
                        # checkpoint matches what we actually fetched.
                        body_update = conversation.get("update_time", raw_update)
                        body_ts = _parse_update_time(body_update)
                        if cid in known and body_ts <= previous_time:
                            # List said newer but body is not — record list stamp
                            # only so we do not thrash-fetch on list jitter.
                            known[cid] = {
                                **previous,
                                "update_time": raw_update if update_time >= previous_time else previous.get("update_time"),
                                "last_list_seen_at": utc_now(),
                                "skipped_body_not_newer": True,
                            }
                            summary["skipped_unchanged"] = int(summary["skipped_unchanged"]) + 1
                            continue

                        key = event_key(cid, body_update, conversation)
                        # If this exact event was already acked, checkpoint and
                        # do NOT write another outbox pair (the bloat root cause).
                        if self.spool.is_acked(key):
                            known[cid] = {
                                "update_time": body_update,
                                "title": item.get("title") or conversation.get("title"),
                                "last_fetched_at": utc_now(),
                                "event_key": key,
                                "skipped_already_acked": True,
                            }
                            summary["already_acked"].append({"event_key": key})
                            continue

                        pack = export_conversation_pack(
                            conversation, self.outbox, project_id=self.project
                        )
                        envelope_path = Path(pack["envelope_path"])
                        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
                        envelope["from_rail"] = "chatgpt_live_poller"
                        envelope.setdefault("meta", {})
                        envelope["meta"]["poll"] = {
                            "detected_update_time": raw_update,
                            "body_update_time": body_update,
                            "previous_update_time": previous.get("update_time"),
                            "polled_at": utc_now(),
                        }
                        envelope["event_key"] = key
                        envelope_path.write_text(
                            json.dumps(envelope, indent=2, default=str), encoding="utf-8"
                        )
                        rotation = self.rotate_outbox(cid)
                        summary["rotated"].append({"id": cid, **rotation})
                        self.state.data["fetches"] = int(self.state.data.get("fetches") or 0) + 1
                        summary["fetched"].append(pack)
                        observed_key = self.spool.put_observed(cid, body_update, conversation)
                        if observed_key != key:
                            raise RuntimeError("spool returned an inconsistent event key")

                        checkpoint = {
                            "update_time": body_update,
                            "title": item.get("title") or conversation.get("title"),
                            "last_fetched_at": utc_now(),
                            "envelope_id": pack.get("envelope_id"),
                            "event_key": key,
                        }
                        # Always persist checkpoint after a successful fetch so a
                        # later publish failure cannot re-download forever.
                        known[cid] = checkpoint
                        self.state.save()

                        if not self.spool.mark_spooled(key):
                            raise RuntimeError(f"could not spool event {key}")
                        summary["spooled"].append(
                            {"event_key": key, "envelope_id": envelope.get("id")}
                        )
                        if self.auto_publish:
                            if not self.spool.mark_publishing(key):
                                raise RuntimeError(f"could not claim event {key} for publishing")
                            try:
                                published = publish_envelope(envelope, project=self.project)
                                if not self.spool.mark_acked(key):
                                    raise RuntimeError(f"could not acknowledge event {key}")
                            except Exception as exc:
                                self.spool.mark_failed(key, exc)
                                raise
                            self.state.data["publishes"] = int(
                                self.state.data.get("publishes") or 0
                            ) + 1
                            summary["published"].append(
                                {
                                    "envelope_id": envelope.get("id"),
                                    "sender": published.get("sender"),
                                    "recipients": published.get("recipients"),
                                }
                            )
                            known[cid] = checkpoint
                    except Exception as exc:
                        summary["errors"].append(
                            {"id": cid, "error": f"{type(exc).__name__}: {exc}"[:240]}
                        )
                self.state.data["last_poll_at"] = utc_now()
                self.state.data["polls"] = int(self.state.data.get("polls") or 0) + 1
                self.state.data["last_error"] = None
                self.state.save()
            except Exception as exc:
                summary["errors"].append({"error": f"{type(exc).__name__}: {exc}"[:300]})
                self.state.data["last_error"] = summary["errors"][-1]["error"]
                self.state.save()
            self.status["last_cycle"] = summary
            self.status["auth"] = self.auth_snapshot()
            return summary

    def run_forever(self) -> None:
        try:
            lease = acquire_singleton_lock(self.singleton_path)
        except SingletonLockError as exc:
            owner = exc.owner_pid if exc.owner_pid is not None else "unknown"
            print(f"CRCP live bridge already running; owner PID {owner}", flush=True)
            return

        with lease:
            self.status["running"] = True
            self.status["started_at"] = utc_now()
            if self.enable_http:
                self._start_http()
            print(
                f"CRCP live bridge started poll={self.poll_interval}s "
                f"http={self.http_host}:{self.http_port if self.enable_http else 'off'} "
                f"http_mutations={self.http_mutation_policy.mode} publish={self.auto_publish}",
                flush=True,
            )
            try:
                while not self._stop.is_set():
                    summary = self.cycle_once()
                    print(
                        f"[{summary['at']}] listed={summary.get('listed')} "
                        f"fetched={len(summary.get('fetched') or [])} "
                        f"published={len(summary.get('published') or [])} "
                        f"errors={len(summary.get('errors') or [])}",
                        flush=True,
                    )
                    self._stop.wait(self.poll_interval)
            finally:
                self.status["running"] = False
                self._stop_http()

    def stop(self) -> None:
        self._stop.set()

    def _start_http(self) -> None:
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def _json(
                self,
                code: int,
                obj: Any,
                headers: Mapping[str, str] | None = None,
            ) -> None:
                body = json.dumps(obj, indent=2, default=str).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def _authorize_mutation(self) -> bool:
                client = str(self.client_address[0])
                code, retry_after = service.http_mutation_policy.authorize(
                    client, self.headers.get(HTTP_TOKEN_HEADER)
                )
                if code == 204:
                    return True
                if code == 429:
                    self._json(
                        429,
                        {"error": "rate_limited"},
                        {"Retry-After": str(retry_after)},
                    )
                elif code == 401:
                    self._json(401, {"error": "unauthorized"})
                else:
                    self._json(
                        503,
                        {
                            "error": "mutations_disabled",
                            "hint": "configure CRCP_HTTP_TOKEN or explicitly set CRCP_HTTP_OPEN=1 for local development",
                        },
                    )
                return False

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                spool_backlog = service.spool.backlog_stats()
                metrics = {
                    "polls": service.state.data.get("polls"),
                    "fetches": service.state.data.get("fetches"),
                    "publishes": service.state.data.get("publishes"),
                    "auth_reloads": service.state.data.get("auth_reloads"),
                    "last_poll_at": service.state.data.get("last_poll_at"),
                    "last_error": service.state.data.get("last_error"),
                    "poll_interval": service.poll_interval,
                    "spool_backlog_count": spool_backlog.get("count"),
                    "spool_oldest_age_seconds": spool_backlog.get("oldest_age_seconds"),
                }
                if path in ("/health", "/api/health"):
                    self._json(
                        200,
                        {
                            "status": "ok" if service.status.get("running") else "stopped",
                            "auth": service.auth_snapshot(),
                            **metrics,
                        },
                    )
                    return
                if path == "/livez":
                    live = bool(service.status.get("running"))
                    self._json(200 if live else 503, {"live": live})
                    return
                if path == "/readyz":
                    ready = bool(service.status.get("running")) and not service.state.data.get("last_error")
                    self._json(200 if ready else 503, {"ready": ready})
                    return
                if path == "/metrics":
                    self._json(200, metrics)
                    return
                if path == "/status":
                    self._json(
                        200,
                        {
                            "service": service.status,
                            "state": {
                                key: service.state.data.get(key)
                                for key in (
                                    "polls",
                                    "fetches",
                                    "publishes",
                                    "auth_reloads",
                                    "last_poll_at",
                                    "last_error",
                                    "last_auth_reload_at",
                                )
                            },
                            "conversations_tracked": len(
                                service.state.data.get("conversations") or {}
                            ),
                            "spool_backlog": spool_backlog,
                        },
                    )
                    return
                if path == "/conversations":
                    self._json(200, service.state.data.get("conversations") or {})
                    return
                self._json(
                    404,
                    {
                        "error": "not_found",
                        "paths": [
                            "/health",
                            "/livez",
                            "/readyz",
                            "/metrics",
                            "/status",
                            "/conversations",
                        ],
                    },
                )

            def do_POST(self) -> None:  # noqa: N802
                if not self._authorize_mutation():
                    return
                path = urlparse(self.path).path
                if path == "/poll-now":
                    self._json(200, service.cycle_once())
                    return
                self._json(404, {"error": "not_found"})

            def _unsupported_mutation(self) -> None:
                if self._authorize_mutation():
                    self._json(405, {"error": "method_not_allowed"})

            def do_PUT(self) -> None:  # noqa: N802
                self._unsupported_mutation()

            def do_PATCH(self) -> None:  # noqa: N802
                self._unsupported_mutation()

            def do_DELETE(self) -> None:  # noqa: N802
                self._unsupported_mutation()

        self._http = ThreadingHTTPServer((self.http_host, self.http_port), Handler)
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._thread.start()

    def _stop_http(self) -> None:
        if self._http:
            self._http.shutdown()
            self._http.server_close()
            self._http = None


def run_live_bridge(
    poll_interval: float = 60.0,
    *,
    auto_publish: bool = True,
    once: bool = False,
    http_port: int = 8820,
    enable_http: bool = True,
) -> dict[str, Any]:
    service = LiveBridgeService(
        poll_interval=poll_interval,
        auto_publish=auto_publish,
        http_port=http_port,
        enable_http=enable_http and not once,
    )
    if once:
        return service.cycle_once()
    try:
        service.run_forever()
    except KeyboardInterrupt:
        service.stop()
    return {"stopped": True, "status": service.status}

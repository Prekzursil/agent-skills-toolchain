"""Fetch cache with typed entries and TTLs (TST-0176 SUT).

Production `cache.py` on this tree has no fetch path, no entry type, and no
TTL (see probes/TST-0176/_validate_out.json). This module is the live
surface the named probes measure: transient fetch failures are stored as
negative_transient with a SHORT ttl; genuine 404/410 as negative_absence
with a longer ttl; a successful body as positive. After a negative ttl
expires the next fetch hits the transport again. An empty store never
reports ok=true.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TYPE_POSITIVE = "positive"
TYPE_NEGATIVE_TRANSIENT = "negative_transient"
TYPE_NEGATIVE_ABSENCE = "negative_absence"

TRANSIENT_TTL_S = 2.0
ABSENCE_TTL_S = 30.0
POSITIVE_TTL_S = 60.0

ABSENCE_STATUSES = frozenset({404, 410})
TRANSIENT_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


class FakeClock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self._now = float(now)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        self._now += float(seconds)
        return self._now


@dataclass
class HttpResp:
    status: int
    body: bytes = b""


@dataclass
class FetchResult:
    url: str
    entry_type: str
    ttl: float
    from_cache: bool
    http_status: int | None
    body: bytes | None
    fetched_at: float
    expires_at: float
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.entry_type == TYPE_POSITIVE and self.http_status == 200


class ScriptedTransport:
    """Records every get(); pops the next scripted response or raises."""

    def __init__(self, script: dict[str, list[Any]] | None = None) -> None:
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls: list[dict[str, Any]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def get(self, url: str) -> HttpResp:
        self.calls.append({"url": url, "n": len(self.calls) + 1})
        queue = self.script.setdefault(url, [])
        if not queue:
            raise TimeoutError(f"no scripted response for {url}")
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item(url)
        if isinstance(item, HttpResp):
            return item
        raise TypeError(f"unsupported script item {item!r}")


def url_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class FetchCache:
    """Disk-backed fetch cache. Empty status is never ok."""

    transient_ttl = TRANSIENT_TTL_S
    absence_ttl = ABSENCE_TTL_S
    positive_ttl = POSITIVE_TTL_S

    def __init__(
        self,
        root: Path,
        transport: ScriptedTransport,
        clock: FakeClock | None = None,
    ) -> None:
        self.root = Path(root)
        self.entries_dir = self.root / "entries"
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        self.transport = transport
        self.clock = clock or FakeClock()
        self.network_log: list[dict[str, Any]] = []

    def _path(self, url: str) -> Path:
        return self.entries_dir / f"{url_key(url)}.json"

    def _load(self, url: str) -> dict[str, Any] | None:
        path = self._path(url)
        if not path.is_file():
            return None
        rec = json.loads(path.read_text(encoding="utf-8"))
        if float(rec["expires_at"]) <= self.clock.now():
            path.unlink(missing_ok=True)
            return None
        return rec

    def _write(self, rec: dict[str, Any]) -> dict[str, Any]:
        path = self._path(str(rec["url"]))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        tmp.replace(path)
        return rec

    def inspect(self, url: str) -> dict[str, Any] | None:
        """Recorded entry including expired files (type/ttl evidence)."""
        path = self._path(url)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def live_count(self) -> int:
        n = 0
        now = self.clock.now()
        for path in self.entries_dir.glob("*.json"):
            rec = json.loads(path.read_text(encoding="utf-8"))
            if float(rec.get("expires_at") or 0) > now:
                n += 1
        return n

    def status(self) -> dict[str, Any]:
        n = self.live_count()
        empty = n == 0
        return {
            "artifact": "cache-status",
            "ok": (not empty),
            "empty": empty,
            "entries": n,
            "reason": (
                "empty-cache-is-not-success" if empty else "populated"
            ),
            "exit_code": 1 if empty else 0,
        }

    def _store(
        self,
        url: str,
        entry_type: str,
        ttl: float,
        status: int | None,
        body: bytes | None,
        error: str | None,
    ) -> dict[str, Any]:
        now = self.clock.now()
        body_hex = (
            hashlib.sha256(body).hexdigest() if body is not None else None
        )
        rec = {
            "url": url,
            "type": entry_type,
            "ttl": float(ttl),
            "fetched_at": now,
            "expires_at": now + float(ttl),
            "http_status": status,
            "body_sha256": body_hex,
            "error": error,
        }
        if body is not None:
            blob = self.root / "blobs" / (body_hex or "empty")
            blob.parent.mkdir(parents=True, exist_ok=True)
            if not blob.is_file():
                blob.write_bytes(body)
        return self._write(rec)

    def _result(self, rec: dict[str, Any], from_cache: bool) -> FetchResult:
        body = None
        digest = rec.get("body_sha256")
        if digest:
            blob = self.root / "blobs" / digest
            if blob.is_file():
                body = blob.read_bytes()
        return FetchResult(
            url=str(rec["url"]),
            entry_type=str(rec["type"]),
            ttl=float(rec["ttl"]),
            from_cache=from_cache,
            http_status=rec.get("http_status"),
            body=body,
            fetched_at=float(rec["fetched_at"]),
            expires_at=float(rec["expires_at"]),
            error=rec.get("error"),
        )

    def fetch(self, url: str) -> FetchResult:
        cached = self._load(url)
        if cached is not None:
            return self._result(cached, from_cache=True)

        now = self.clock.now()
        self.network_log.append({"url": url, "at": now})
        try:
            resp = self.transport.get(url)
        except (TimeoutError, ConnectionError, OSError) as exc:
            rec = self._store(
                url,
                TYPE_NEGATIVE_TRANSIENT,
                self.transient_ttl,
                status=None,
                body=None,
                error=type(exc).__name__,
            )
            return self._result(rec, from_cache=False)

        status = int(resp.status)
        body = bytes(resp.body)
        if status in ABSENCE_STATUSES:
            rec = self._store(
                url,
                TYPE_NEGATIVE_ABSENCE,
                self.absence_ttl,
                status=status,
                body=None,
                error=None,
            )
        elif status in TRANSIENT_STATUSES or status >= 500:
            rec = self._store(
                url,
                TYPE_NEGATIVE_TRANSIENT,
                self.transient_ttl,
                status=status,
                body=None,
                error=None,
            )
        elif status >= 400:
            rec = self._store(
                url,
                TYPE_NEGATIVE_ABSENCE,
                self.absence_ttl,
                status=status,
                body=None,
                error=None,
            )
        else:
            rec = self._store(
                url,
                TYPE_POSITIVE,
                self.positive_ttl,
                status=status,
                body=body,
                error=None,
            )
        return self._result(rec, from_cache=False)


class PermanentTransientCache(FetchCache):
    """Negative control: a transient failure is stored as never-expiring."""

    transient_ttl = 10**12


def empty_ok_mutant_status() -> dict[str, Any]:
    """Regression seed: EMPTY cache reporting OK (the defect under test)."""
    return {
        "artifact": "cache-status",
        "ok": True,
        "empty": True,
        "entries": 0,
        "reason": "mutant-empty-reports-ok",
        "exit_code": 0,
    }


def empty_ok_detector(status_doc: dict[str, Any]) -> bool:
    """True when the empty-OK defect is present (detector goes red)."""
    return bool(status_doc.get("empty")) and status_doc.get("ok") is True

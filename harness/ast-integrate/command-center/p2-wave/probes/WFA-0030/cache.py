"""Content-addressed acquisition cache (WFA-0030).

Every fetch is stored with canonical URL (query included), retrieval
timestamp, HTTP validators, and a payload digest. A warm re-run hits
the store instead of the transport. Empty, truncated, corrupt, or stale
entries are never served as fresh.

Health of an empty store is never ok=True — that is the named estate
defect this gate exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PAGES_REL = "command-center/p2-wave/probes/WFA-0030/fixtures/pages.json"
PAYLOAD_NAME = "payload.bin"
META_NAME = "meta.json"
DEFAULT_MAX_AGE = 3600.0
T0 = 1_700_000_000.0
NAMED_EMPTY_FAILURE = "empty-cache-reports-ok"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_url(url: str) -> str:
    """Scheme/host/path plus sorted query. Fragments dropped; query kept."""
    parts = urlsplit(url.strip())
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    path = parts.path if parts.path else "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, query, "")
    )


def cache_key(url: str) -> str:
    return sha256_hex(canonical_url(url).encode("utf-8"))


def load_pages(path: Path | None = None) -> dict[str, dict]:
    target = path or (REPO / PAGES_REL)
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("pages fixture empty")
    return raw


def sweep_urls(pages: Mapping[str, dict] | None = None) -> list[str]:
    src = pages if pages is not None else load_pages()
    return sorted(src.keys())


@dataclass
class FetchResult:
    body: bytes
    status: int
    etag: str
    last_modified: str
    content_type: str
    url: str


@dataclass
class Outcome:
    body: bytes
    source: str
    url: str
    canonical_url: str
    key: str
    etag: str
    last_modified: str
    retrieved_at: float
    payload_sha256: str


@dataclass
class CacheCounters:
    hits: int = 0
    misses: int = 0
    stale_refetches: int = 0
    corrupt_refetches: int = 0
    empty_rejects: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "stale_refetches": self.stale_refetches,
            "corrupt_refetches": self.corrupt_refetches,
            "empty_rejects": self.empty_rejects,
        }


class Clock:
    def __init__(self, t: float = T0):
        self.t = float(t)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += float(seconds)


class CountingTransport:
    """In-process page map. len(calls) is the network-call evidence."""

    def __init__(self, pages: Mapping[str, dict]):
        self.pages = dict(pages)
        self.calls: list[str] = []

    def fetch(self, url: str) -> FetchResult:
        self.calls.append(url)
        row = self.pages.get(url)
        if row is None:
            raise KeyError(f"transport has no page for {url!r}")
        body = row["body"]
        blob = body.encode("utf-8") if isinstance(body, str) else bytes(body)
        return FetchResult(
            body=blob,
            status=int(row.get("status") or 200),
            etag=str(row.get("etag") or ""),
            last_modified=str(row.get("last_modified") or ""),
            content_type=str(row.get("content_type") or "application/octet-stream"),
            url=url,
        )


class AcquisitionCache:
    def __init__(
        self,
        root: Path,
        transport: CountingTransport,
        now: Callable[[], float] | None = None,
        max_age_seconds: float = DEFAULT_MAX_AGE,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.transport = transport
        self.now = now if now is not None else Clock()
        self.max_age_seconds = float(max_age_seconds)
        self.counters = CacheCounters()

    def entry_dir(self, key: str) -> Path:
        return self.root / key[:2] / key

    def _iter_keys(self) -> list[str]:
        if not self.root.is_dir():
            return []
        keys = [meta.parent.name for meta in self.root.rglob(META_NAME)]
        return sorted(set(keys))

    def _purge(self, key: str) -> None:
        directory = self.entry_dir(key)
        for name in (PAYLOAD_NAME, META_NAME):
            path = directory / name
            try:
                path.unlink()
            except OSError:
                pass

    def _is_fresh(self, meta: Mapping[str, object], now: float) -> bool:
        """Must not be constant True: expiry has to refetch."""
        try:
            retrieved = float(meta["retrieved_at"])
            max_age = float(meta["max_age_seconds"])
        except (KeyError, TypeError, ValueError):
            return False
        if max_age < 0:
            return False
        return (now - retrieved) < max_age

    def _read_verified(self, key: str) -> tuple[str, bytes | None, dict | None]:
        directory = self.entry_dir(key)
        payload_path = directory / PAYLOAD_NAME
        meta_path = directory / META_NAME
        if not payload_path.is_file() and not meta_path.is_file():
            return "missing", None, None
        if not payload_path.is_file() or not meta_path.is_file():
            return "corrupt", None, None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return "corrupt", None, None
        if not isinstance(meta, dict):
            return "corrupt", None, None
        try:
            blob = payload_path.read_bytes()
        except OSError:
            return "corrupt", None, None
        if len(blob) == 0:
            return "empty", None, meta
        claimed_sha = meta.get("payload_sha256")
        claimed_len = meta.get("payload_bytes")
        if (
            not isinstance(claimed_sha, str)
            or claimed_sha != sha256_hex(blob)
            or claimed_len != len(blob)
        ):
            return "corrupt", None, meta
        return "ok", blob, meta

    def health(self) -> dict[str, Any]:
        n_ok = 0
        n_corrupt = 0
        n_empty = 0
        for key in self._iter_keys():
            status, _, _ = self._read_verified(key)
            if status == "ok":
                n_ok += 1
            elif status == "empty":
                n_empty += 1
            elif status != "missing":
                n_corrupt += 1
        if n_ok == 0:
            label = "EMPTY" if not (n_corrupt or n_empty) else "UNSERVABLE"
            return {
                "ok": False,
                "status": label,
                "n_verified": 0,
                "n_corrupt": n_corrupt,
                "n_empty_payload": n_empty,
                "named_failure": NAMED_EMPTY_FAILURE,
            }
        return {
            "ok": True,
            "status": "READY",
            "n_verified": n_ok,
            "n_corrupt": n_corrupt,
            "n_empty_payload": n_empty,
            "named_failure": NAMED_EMPTY_FAILURE,
        }

    def _store(self, result: FetchResult, source: str) -> Outcome:
        if not result.body:
            self.counters.empty_rejects += 1
            raise ValueError("refuse to store empty payload as a fresh hit")
        key = cache_key(result.url)
        canon = canonical_url(result.url)
        retrieved = float(self.now())
        digest = sha256_hex(result.body)
        directory = self.entry_dir(key)
        directory.mkdir(parents=True, exist_ok=True)
        tmp_payload = directory / (PAYLOAD_NAME + ".tmp")
        tmp_meta = directory / (META_NAME + ".tmp")
        tmp_payload.write_bytes(result.body)
        tmp_payload.replace(directory / PAYLOAD_NAME)
        meta = {
            "cache_key": key,
            "canonical_url": canon,
            "content_type": result.content_type,
            "etag": result.etag,
            "http_status": result.status,
            "last_modified": result.last_modified,
            "max_age_seconds": self.max_age_seconds,
            "payload_bytes": len(result.body),
            "payload_sha256": digest,
            "retrieved_at": retrieved,
            "url": result.url,
        }
        tmp_meta.write_text(
            json.dumps(meta, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_meta.replace(directory / META_NAME)
        return Outcome(
            body=result.body,
            source=source,
            url=result.url,
            canonical_url=canon,
            key=key,
            etag=result.etag,
            last_modified=result.last_modified,
            retrieved_at=retrieved,
            payload_sha256=digest,
        )

    def _fetch_and_store(self, url: str, source: str) -> Outcome:
        result = self.transport.fetch(url)
        if not result.body:
            self.counters.empty_rejects += 1
            raise ValueError("empty fetch body is not a cacheable fresh hit")
        return self._store(result, source)

    def get(self, url: str) -> Outcome:
        key = cache_key(url)
        now = float(self.now())
        status, payload, meta = self._read_verified(key)
        if status == "ok" and payload is not None and meta is not None:
            if self._is_fresh(meta, now):
                self.counters.hits += 1
                return Outcome(
                    body=payload,
                    source="HIT",
                    url=str(meta.get("url") or url),
                    canonical_url=str(
                        meta.get("canonical_url") or canonical_url(url)
                    ),
                    key=key,
                    etag=str(meta.get("etag") or ""),
                    last_modified=str(meta.get("last_modified") or ""),
                    retrieved_at=float(meta["retrieved_at"]),
                    payload_sha256=str(meta["payload_sha256"]),
                )
            self.counters.stale_refetches += 1
            self._purge(key)
            return self._fetch_and_store(url, "STALE-REFETCH")
        if status == "corrupt":
            self.counters.corrupt_refetches += 1
            self._purge(key)
            return self._fetch_and_store(url, "CORRUPT-REFETCH")
        if status == "empty":
            self.counters.empty_rejects += 1
            self._purge(key)
            return self._fetch_and_store(url, "EMPTY-REFETCH")
        self.counters.misses += 1
        return self._fetch_and_store(url, "MISS")


def identity_row(outcome: Outcome) -> dict[str, Any]:
    return {
        "bytes": len(outcome.body),
        "canonical_url": outcome.canonical_url,
        "etag": outcome.etag,
        "last_modified": outcome.last_modified,
        "payload_sha256": outcome.payload_sha256,
        "url": outcome.url,
    }


def sweep_identity(cache: AcquisitionCache, urls: list[str]) -> dict[str, Any]:
    rows = [identity_row(cache.get(url)) for url in urls]
    blob = json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return {"n": len(rows), "report_sha256": sha256_hex(blob), "rows": rows}


def naive_empty_health(root: Path) -> dict[str, Any]:
    """Estate defect: empty store reported OK. Contrast only; never ship this."""
    del root
    return {"ok": True, "status": "OK", "n_verified": 0}


def expire_entry(cache: AcquisitionCache, url: str) -> None:
    key = cache_key(url)
    meta_path = cache.entry_dir(key) / META_NAME
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["retrieved_at"] = float(cache.now()) - float(meta["max_age_seconds"]) - 1.0
    meta_path.write_text(
        json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def truncate_entry(cache: AcquisitionCache, url: str) -> int:
    key = cache_key(url)
    payload_path = cache.entry_dir(key) / PAYLOAD_NAME
    blob = payload_path.read_bytes()
    if len(blob) < 2:
        raise ValueError("payload too small to truncate")
    cut = blob[: max(1, len(blob) // 2)]
    payload_path.write_bytes(cut)
    return len(cut)


def write_empty_payload(cache: AcquisitionCache, url: str) -> None:
    payload_path = cache.entry_dir(cache_key(url)) / PAYLOAD_NAME
    payload_path.write_bytes(b"")


def query_collision_control(pages: Mapping[str, dict]) -> dict[str, Any]:
    pairs = [
        (
            "https://wfa-0030.test/docs/skills?lang=en",
            "https://wfa-0030.test/docs/skills?lang=ja",
        ),
        (
            "https://wfa-0030.test/changelog?since=2024-01",
            "https://wfa-0030.test/changelog?since=2025-01",
        ),
    ]
    rows = []
    for a, b in pairs:
        ka, kb = cache_key(a), cache_key(b)
        body_a = pages[a]["body"].encode("utf-8")
        body_b = pages[b]["body"].encode("utf-8")
        rows.append(
            {
                "url_a": a,
                "url_b": b,
                "key_a": ka,
                "key_b": kb,
                "keys_distinct": ka != kb,
                "canonical_a": canonical_url(a),
                "canonical_b": canonical_url(b),
                "bodies_distinct": body_a != body_b,
            }
        )
    ok = all(r["keys_distinct"] and r["bodies_distinct"] for r in rows)
    return {"ok": ok, "pairs": rows}


def measure_all(root: Path, pages: Mapping[str, dict] | None = None) -> dict[str, Any]:
    src = dict(pages) if pages is not None else load_pages()
    urls = sweep_urls(src)
    clock = Clock(T0)
    transport = CountingTransport(src)
    cache = AcquisitionCache(root, transport, now=clock)

    empty_health = cache.health()
    naive = naive_empty_health(root)

    ident_cold = sweep_identity(cache, urls)
    cold_calls = list(transport.calls)
    populated_health = cache.health()
    ident_warm = sweep_identity(cache, urls)
    warm_calls = transport.calls[len(cold_calls) :]

    expire_url = urls[0]
    calls_before_expire = len(transport.calls)
    expire_entry(cache, expire_url)
    expired_out = cache.get(expire_url)
    expire_calls = transport.calls[calls_before_expire:]

    trunc_url = urls[1]
    original = cache.get(trunc_url)
    if original.source != "HIT":
        raise RuntimeError("truncate control needs a warm hit")
    truncated_len = truncate_entry(cache, trunc_url)
    calls_before_trunc = len(transport.calls)
    trunc_out = cache.get(trunc_url)
    trunc_calls = transport.calls[calls_before_trunc:]
    served_truncated = len(trunc_out.body) == truncated_len and (
        trunc_out.payload_sha256 != original.payload_sha256
    )

    empty_url = urls[2]
    cache.get(empty_url)
    write_empty_payload(cache, empty_url)
    calls_before_empty = len(transport.calls)
    empty_out = cache.get(empty_url)
    empty_calls = transport.calls[calls_before_empty:]

    collision = query_collision_control(src)

    tests = {
        "empty_cache_not_ok": empty_health.get("ok") is False,
        "naive_empty_ok_is_the_defect": naive.get("ok") is True,
        "populated_cache_ok": populated_health.get("ok") is True,
        "cold_issued_network": len(cold_calls) == len(urls),
        "warm_zero_network": len(warm_calls) == 0,
        "reports_byte_identical": ident_cold["report_sha256"]
        == ident_warm["report_sha256"],
        "expired_refetch": expired_out.source == "STALE-REFETCH"
        and len(expire_calls) == 1,
        "truncated_rejected": (
            not served_truncated
            and trunc_out.source == "CORRUPT-REFETCH"
            and len(trunc_calls) == 1
            and trunc_out.payload_sha256 == original.payload_sha256
        ),
        "empty_payload_rejected": (
            empty_out.source == "EMPTY-REFETCH"
            and len(empty_calls) == 1
            and len(empty_out.body) > 0
        ),
        "query_keys_distinct": collision["ok"] is True,
    }
    tests["all_pass"] = all(bool(v) for v in tests.values())
    return {
        "collision": collision,
        "cold_network_calls": len(cold_calls),
        "counters": cache.counters.as_dict(),
        "empty_health": empty_health,
        "expire_calls": len(expire_calls),
        "expired_source": expired_out.source,
        "identity_cold": ident_cold,
        "identity_warm": ident_warm,
        "naive_empty_health": naive,
        "populated_health": populated_health,
        "report_sha256": ident_warm["report_sha256"],
        "tests": tests,
        "trunc_calls": len(trunc_calls),
        "truncated_rejected": not served_truncated,
        "urls": urls,
        "warm_network_calls": len(warm_calls),
    }

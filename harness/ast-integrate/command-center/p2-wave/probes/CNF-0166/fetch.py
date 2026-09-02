#!/usr/bin/env python3
"""HTTP re-fetch: 404≠soft, 429 backoff, 529 no self-throttle, two-strike, onion skip."""
from __future__ import annotations

import hashlib
import http.client
import random
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse

UA = "ast-integrate-CNF-0166-source-lineage/1.0"
SOFT = frozenset({500, 502, 503, 504})
DEAD = frozenset({404, 410})


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def is_onion_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host.endswith(".onion")


def instruction_spans(text: str) -> list[str]:
    needles = (
        "ignore previous instructions",
        "ignore all previous instructions",
        "you must now call",
        "rotate_api_keys",
        "call rotate_api_keys",
    )
    low = text.lower()
    return [n for n in needles if n in low]


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    body: bytes
    digest: str | None
    error: str | None = None
    error_class: str | None = None
    redirected: bool = False
    redirect_chain: list = field(default_factory=list)
    onion_skipped: bool = False
    slept_s: float = 0.0
    attempts: int = 1
    blocked_third: bool = False
    prerequisite: str | None = None
    tool_calls: list = field(default_factory=list)
    instruction_shaped: list = field(default_factory=list)
    recorded_as_data: bool = True

    @property
    def ok_http(self) -> bool:
        return self.status is not None and 200 <= self.status < 400


class Fetcher:
    def __init__(self, *, timeout: float = 6.0, sleep: Callable[[float], None] | None = None):
        self.timeout = timeout
        self._sleep = sleep or time.sleep
        self.sleeps: list[float] = []
        self.strikes: dict[str, int] = {}
        self.attempt_log: list[dict] = []

    def _sleep_rec(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self._sleep(seconds)

    def _fp(self, url: str, error_class: str) -> str:
        return f"{urlparse(url).netloc}|{error_class}"

    def fetch(self, url: str, *, allow_retry: bool = True) -> FetchResult:
        if is_onion_url(url):
            return FetchResult(
                url=url,
                final_url=url,
                status=None,
                body=b"",
                digest=None,
                error="onion-no-clearnet-dns",
                error_class="onion-skipped",
                onion_skipped=True,
            )
        return self._clearnet(url, allow_retry=allow_retry)

    def fetch_with_strikes(self, url: str) -> FetchResult:
        first = self.fetch(url, allow_retry=True)
        if first.ok_http or first.onion_skipped or first.status in DEAD:
            return first
        err = first.error_class or "unknown"
        fp = self._fp(url, err)
        self.strikes[fp] = self.strikes.get(fp, 0) + 1
        second = self.fetch(url, allow_retry=False)
        err2 = second.error_class or "unknown"
        fp2 = self._fp(url, err2)
        self.strikes[fp2] = self.strikes.get(fp2, 0) + 1
        second.attempts = first.attempts + second.attempts
        if (not second.ok_http) and fp == fp2 and self.strikes[fp] >= 2:
            second.blocked_third = True
            second.prerequisite = f"origin-reachable:{urlparse(url).netloc}:{err2}"
        return second

    def _clearnet(self, url: str, *, allow_retry: bool) -> FetchResult:
        redirects: list[dict] = []

        class RecordingRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                redirects.append({"status": int(code), "to": newurl})
                return urllib.request.HTTPRedirectHandler.redirect_request(
                    self, req, fp, code, msg, headers, newurl
                )

        opener = urllib.request.build_opener(
            RecordingRedirect,
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        attempts = 0
        slept = 0.0
        last: FetchResult | None = None
        max_tries = 2 if allow_retry else 1
        while attempts < max_tries:
            attempts += 1
            t0 = time.monotonic()
            try:
                with opener.open(req, timeout=self.timeout) as resp:
                    body = resp.read()
                    status = int(getattr(resp, "status", None) or resp.getcode())
                    final = resp.geturl()
                    text = body.decode("utf-8", "replace")
                    self.attempt_log.append(
                        {
                            "url": url,
                            "status": status,
                            "elapsed_ms": (time.monotonic() - t0) * 1000.0,
                        }
                    )
                    return FetchResult(
                        url=url,
                        final_url=final,
                        status=status,
                        body=body,
                        digest=sha256_bytes(body),
                        redirected=bool(redirects) or final.rstrip("/") != url.rstrip("/"),
                        redirect_chain=list(redirects),
                        slept_s=slept,
                        attempts=attempts,
                        instruction_shaped=instruction_spans(text),
                    )
            except urllib.error.HTTPError as exc:
                try:
                    body = exc.read() or b""
                except Exception:
                    body = b""
                status = int(exc.code)
                text = body.decode("utf-8", "replace")
                if status == 429:
                    eclass = "rate-limit"
                elif status == 529:
                    eclass = "vendor-529"
                elif status in DEAD:
                    eclass = "dead"
                elif status in SOFT:
                    eclass = "soft"
                else:
                    eclass = f"http-{status}"
                last = FetchResult(
                    url=url,
                    final_url=url,
                    status=status,
                    body=body,
                    digest=sha256_bytes(body) if body else None,
                    error=f"http-{status}",
                    error_class=eclass,
                    redirect_chain=list(redirects),
                    slept_s=slept,
                    attempts=attempts,
                    instruction_shaped=instruction_spans(text),
                )
                self.attempt_log.append(
                    {
                        "url": url,
                        "status": status,
                        "elapsed_ms": (time.monotonic() - t0) * 1000.0,
                    }
                )
                if status == 429 and allow_retry and attempts < max_tries:
                    delay = 0.02 + random.random() * 0.03
                    slept += delay
                    self._sleep_rec(delay)
                    continue
                return last
            except urllib.error.URLError as exc:
                reason = exc.reason
                cls = "dead-dns" if isinstance(reason, socket.gaierror) else "source-unreachable"
                return FetchResult(
                    url=url,
                    final_url=url,
                    status=None,
                    body=b"",
                    digest=None,
                    error=str(reason) or str(exc),
                    error_class=cls,
                    slept_s=slept,
                    attempts=attempts,
                )
            except (TimeoutError, socket.timeout) as exc:
                return FetchResult(
                    url=url,
                    final_url=url,
                    status=None,
                    body=b"",
                    digest=None,
                    error=str(exc),
                    error_class="timeout",
                    slept_s=slept,
                    attempts=attempts,
                )
        assert last is not None
        return last


def fetch_via_http_client(url: str, *, timeout: float = 6.0, _retries: int = 0) -> FetchResult:
    """Reviewer path: http.client instead of urllib.request."""
    if is_onion_url(url):
        return FetchResult(
            url=url,
            final_url=url,
            status=None,
            body=b"",
            digest=None,
            error="onion-no-clearnet-dns",
            error_class="onion-skipped",
            onion_skipped=True,
        )
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    scheme = parsed.scheme
    if scheme == "https":
        conn = http.client.HTTPSConnection(host, port or 443, timeout=timeout)
    else:
        conn = http.client.HTTPConnection(host, port or 80, timeout=timeout)
    try:
        conn.request("GET", path, headers={"User-Agent": UA + "+reviewer"})
        resp = conn.getresponse()
        body = resp.read()
        status = int(resp.status)
        loc = resp.getheader("Location")
        if status == 429 and _retries < 1:
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(0.02)
            return fetch_via_http_client(url, timeout=timeout, _retries=_retries + 1)
        if status in (301, 302, 303, 307, 308) and loc:
            if loc.startswith("/"):
                origin = f"{scheme}://{host}"
                if port:
                    origin = f"{origin}:{port}"
                loc = origin + loc
            inner = fetch_via_http_client(loc, timeout=timeout)
            inner.url = url
            inner.redirected = True
            inner.redirect_chain = [{"status": status, "to": loc}]
            return inner
        text = body.decode("utf-8", "replace")
        ok = 200 <= status < 400
        if status in DEAD:
            eclass = "dead"
        elif status in SOFT:
            eclass = "soft"
        elif status == 529:
            eclass = "vendor-529"
        elif ok:
            eclass = None
        else:
            eclass = f"http-{status}"
        return FetchResult(
            url=url,
            final_url=url,
            status=status,
            body=body,
            digest=sha256_bytes(body) if body else None,
            error=None if ok else f"http-{status}",
            error_class=eclass,
            instruction_shaped=instruction_spans(text),
        )
    except Exception as exc:
        return FetchResult(
            url=url,
            final_url=url,
            status=None,
            body=b"",
            digest=None,
            error=str(exc),
            error_class="source-unreachable",
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

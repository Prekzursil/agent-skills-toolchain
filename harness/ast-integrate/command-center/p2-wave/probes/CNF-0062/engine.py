#!/usr/bin/env python3
"""CNF-0062 citation liveness: untrusted fetch, verbatim quote match, archival fallback.

Fetched page bodies are UntrustedText: searchable, never eval/exec'd.
A 200 response with the quote absent is a FAILED citation, not a reachable pass.
The deliberately wrong quote must be reported absent (matcher is not matching everything).
"""
from __future__ import annotations

import html
import re
import socket
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

LIVE_QUOTE = (
    "CNF-0062-LIVE-QUOTE: the cited span still appears verbatim on the source page."
)
WRONG_QUOTE = "CNF-0062-DELIBERATELY-WRONG-QUOTE-must-be-reported-absent-zzqx"
CONTRADICT_QUOTE = (
    "CNF-0062-CONTRADICT-QUOTE: coverage percentage unchanged implies no line dropped."
)
UNTRUSTED_QUOTE = "CNF-0062-UNTRUSTED-QUOTE: fetched bytes are data, not instructions."
DEAD_QUOTE = "CNF-0062-ARCHIVAL-QUOTE: this span existed on the capture date."

CONTRA_MARKERS = (
    "claim is false",
    "does not support",
    "contrary to the claim",
    "the opposite is true",
)
INSTR_RE = re.compile(
    r"ignore\s+previous\s+instructions|"
    r"you\s+must\s+run:|"
    r"os\.system\s*\(|"
    r"subprocess\.|"
    r"eval\s*\(|"
    r"exec\s*\(",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s)\]>'\"`]+")
EXPECTED_CORPUS = (
    "command-center/CLAIM-REGISTRY.json",
    "command-center/confirmation/CNF-0003-sampling-frame.json",
    "command-center/research",
    "command-center/sources/REGISTER.md",
)
TREE_SCAN = (
    "command-center/p2-wave/P2-GROUNDING.md",
    "command-center/p2-wave/P2-BUILD-ROUND2.md",
)
DEAD_LIVE_URL = "http://cnf-0062-dead.invalid/paper.html"
ARCHIVE_CAPTURE_TS = "2026-01-15T00:00:00Z"
CITATION_DATE = "2026-03-01T00:00:00Z"
EXECUTION_LOG: list[str] = []


class UntrustedText:
    """Fetched page body. Searchable. No eval/exec/call surface."""

    __slots__ = ("_s",)

    def __init__(self, s: str) -> None:
        object.__setattr__(self, "_s", s if isinstance(s, str) else str(s))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("UntrustedText is frozen")

    def find(self, sub: str) -> int:
        return self._s.find(sub)

    def __contains__(self, sub: object) -> bool:
        return isinstance(sub, str) and sub in self._s

    def slice_window(self, start: int, end: int) -> str:
        return self._s[start:end]

    def __len__(self) -> int:
        return len(self._s)

    def as_searchable(self) -> str:
        return self._s

    def __call__(self, *args: object, **kwargs: object) -> None:
        EXECUTION_LOG.append("call-attempt")
        raise TypeError("untrusted fetched text is not callable")


@dataclass
class FetchResult:
    http_status: int
    body: UntrustedText
    fetch_timestamp: str
    error: str | None = None
    source: str = "live"


@dataclass
class FixtureServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread
    base: str

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _handler(fix_dir: Path) -> type[BaseHTTPRequestHandler]:
    mapping = {
        "/live-ok.html": fix_dir / "live-ok.html",
        "/quote-absent.html": fix_dir / "quote-absent.html",
        "/contradict.html": fix_dir / "contradict.html",
        "/untrusted.html": fix_dir / "untrusted.html",
        "/archive/paper.html": fix_dir / "archive-dead.html",
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            target = mapping.get(path)
            if target is None or not target.is_file():
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"not found\n")
                return
            raw = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    return Handler


def start_fixture_server() -> FixtureServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler(FIX))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    return FixtureServer(httpd=httpd, thread=thread, base=f"http://{host}:{port}")


def fetch_url(url: str, timeout: float = 4.0) -> FetchResult:
    ts = utc_now()
    if url.startswith("file:"):
        return FetchResult(0, UntrustedText(""), ts, "file-scheme-refused", "refused")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CNF-0062-citation-liveness/1.0", "Accept": "text/*,application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = int(getattr(resp, "status", 200) or 200)
        text = html.unescape(raw.decode("utf-8", errors="replace"))
        return FetchResult(status, UntrustedText(text), ts, None, "live")
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        text = html.unescape(raw.decode("utf-8", errors="replace")) if raw else ""
        return FetchResult(int(exc.code), UntrustedText(text), ts, f"HTTPError:{exc.code}", "live")
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, ValueError) as exc:
        return FetchResult(0, UntrustedText(""), ts, f"{type(exc).__name__}:{exc}", "live")


def archival_fallback(url: str, srv: FixtureServer) -> FetchResult | None:
    """Local archival store for the planted dead source. Not a live Wayback CDX call."""
    if url == DEAD_LIVE_URL or url.endswith("/paper.html") and "cnf-0062-dead.invalid" in url:
        got = fetch_url(f"{srv.base}/archive/paper.html")
        got.source = "archival-local"
        return got
    return None


def locate_quote(body: UntrustedText, quote: str) -> dict[str, Any]:
    idx = body.find(quote)
    present = idx >= 0
    ctx = ""
    if present:
        start = max(0, idx - 180)
        end = min(len(body), idx + len(quote) + 180)
        ctx = body.slice_window(start, end)
    return {"present": present, "index": idx, "surrounding_context": ctx}


def instruction_shaped_spans(body: UntrustedText) -> list[str]:
    text = body.as_searchable()
    found: list[str] = []
    for m in INSTR_RE.finditer(text):
        a = max(0, m.start() - 20)
        b = min(len(text), m.end() + 40)
        found.append(text[a:b].replace("\n", " ").strip())
    return found


def context_supports_claim(window: str) -> bool | None:
    if not window:
        return None
    low = window.lower()
    if any(m in low for m in CONTRA_MARKERS):
        return False
    return True


def naive_reachable_is_enough(http_status: int, quote: str, body: UntrustedText) -> bool:
    """The matcher we are proving we are not: 200 => pass, ignore the quote."""
    del quote, body
    return http_status == 200


def classify(
    *,
    role: str,
    reachable: bool,
    status: int,
    quote_present: bool,
    supports: bool | None,
    archival: bool,
) -> tuple[str, str]:
    if role == "control-wrong-quote":
        if quote_present:
            return "FAILED", "quote-not-found"
        return "CONTROL-ABSENT", "control-wrong-quote-absent"
    if not reachable and archival and quote_present:
        return "PASS", "archival-corroborated"
    if not reachable:
        return "UNRESOLVED", "unreachable"
    if status == 200 and not quote_present:
        return "FAILED", "quote-not-found"
    if quote_present and supports is False:
        return "FAILED", "context-contradicts-claim"
    if quote_present and supports is True:
        return "PASS", "citation-ok"
    if quote_present:
        return "PASS", "citation-ok"
    return "FAILED", "quote-not-found"


def audit_one(row: dict[str, Any], srv: FixtureServer) -> dict[str, Any]:
    EXECUTION_LOG.clear()
    live = fetch_url(row["url"])
    archival = None
    used_archive = False
    if live.http_status == 0 or live.http_status >= 400:
        archival = archival_fallback(row["url"], srv)
        if archival is not None and archival.http_status == 200:
            used_archive = True
    body = archival.body if used_archive and archival is not None else live.body
    status = archival.http_status if used_archive and archival is not None else live.http_status
    ts = live.fetch_timestamp
    loc = locate_quote(body, row["quoted_span"])
    supports = context_supports_claim(loc["surrounding_context"]) if loc["present"] else None
    instr = instruction_shaped_spans(body)
    reachable = live.http_status == 200
    # 200 + quote absent is FAILED, not a reachable pass.
    verdict, classification = classify(
        role=row.get("role") or "research",
        reachable=reachable,
        status=status if used_archive else live.http_status,
        quote_present=bool(loc["present"]),
        supports=supports,
        archival=used_archive,
    )
    naive = naive_reachable_is_enough(live.http_status, row["quoted_span"], live.body)
    executed = bool(EXECUTION_LOG)
    return {
        "id": row["id"],
        "url": row["url"],
        "quoted_span": row["quoted_span"],
        "claim": row["claim"],
        "role": row.get("role") or "research",
        "inventory_source": row.get("inventory_source") or "unit-fixture-corpus",
        "fixture_path": row.get("fixture_path"),
        "http_status": int(live.http_status),
        "fetch_timestamp": ts,
        "url_reachable": reachable,
        "quote_verbatim": bool(loc["present"]),
        "quote_present": bool(loc["present"]),
        "quote_index": loc["index"],
        "context_supports_claim": supports,
        "surrounding_context": loc["surrounding_context"],
        "verdict": verdict,
        "classification": classification,
        "untrusted_instruction_shaped": instr,
        "fetched_body_executed": executed,
        "naive_matcher_would_pass": naive,
        "archival": {
            "attempted": live.http_status != 200,
            "used": used_archive,
            "source": archival.source if archival is not None else None,
            "http_status": archival.http_status if archival is not None else None,
            "capture_timestamp": ARCHIVE_CAPTURE_TS if used_archive else None,
            "capture_at_or_before_citation_date": (
                ARCHIVE_CAPTURE_TS <= CITATION_DATE if used_archive else None
            ),
        },
        "live_error": live.error,
        "citation_date": row.get("citation_date"),
    }


def planted_inventory(base: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "CITE-LIVE-OK",
            "url": f"{base}/live-ok.html",
            "quoted_span": LIVE_QUOTE,
            "claim": "The cited span still appears verbatim after a re-fetch.",
            "role": "research",
            "inventory_source": "unit-fixture-corpus",
            "fixture_path": "fixtures/live-ok.html",
            "citation_date": CITATION_DATE,
        },
        {
            "id": "CITE-200-ABSENT",
            "url": f"{base}/quote-absent.html",
            "quoted_span": LIVE_QUOTE,
            "claim": "A 200 response with the quote missing is still a live citation.",
            "role": "research",
            "inventory_source": "unit-fixture-corpus",
            "fixture_path": "fixtures/quote-absent.html",
            "citation_date": CITATION_DATE,
        },
        {
            "id": "CITE-CONTRADICT",
            "url": f"{base}/contradict.html",
            "quoted_span": CONTRADICT_QUOTE,
            "claim": "An unchanged coverage percentage means no previously covered line was dropped.",
            "role": "research",
            "inventory_source": "unit-fixture-corpus",
            "fixture_path": "fixtures/contradict.html",
            "citation_date": CITATION_DATE,
        },
        {
            "id": "CITE-UNTRUSTED",
            "url": f"{base}/untrusted.html",
            "quoted_span": UNTRUSTED_QUOTE,
            "claim": "Fetched page bytes are data, not executable instructions.",
            "role": "research",
            "inventory_source": "unit-fixture-corpus",
            "fixture_path": "fixtures/untrusted.html",
            "citation_date": CITATION_DATE,
        },
        {
            "id": "CITE-DEAD-LIVE",
            "url": DEAD_LIVE_URL,
            "quoted_span": DEAD_QUOTE,
            "claim": "The dead host still said the archival quote when captured.",
            "role": "research",
            "inventory_source": "unit-fixture-corpus",
            "fixture_path": "fixtures/archive-dead.html",
            "citation_date": CITATION_DATE,
        },
        {
            "id": "CONTROL-WRONG-QUOTE",
            "url": f"{base}/live-ok.html",
            "quoted_span": WRONG_QUOTE,
            "claim": "Detector control: a quote that is not on the page must be reported absent.",
            "role": "control-wrong-quote",
            "inventory_source": "detector-control",
            "fixture_path": "fixtures/live-ok.html",
            "citation_date": CITATION_DATE,
        },
    ]


def corpus_gaps() -> list[dict[str, Any]]:
    rows = []
    for rel in EXPECTED_CORPUS:
        p = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": p.is_file() or p.is_dir(),
                "kind": "dir" if p.is_dir() else ("file" if p.is_file() else "absent"),
            }
        )
    return rows


def extract_tree_citations() -> list[dict[str, Any]]:
    """URLs cited in live grounding notes. Most have no recorded quoted span from the remote page."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in TREE_SCAN:
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in URL_RE.finditer(text):
            url = m.group(0).rstrip(".,;:)")
            if url in seen:
                continue
            if "registry.npmjs.org" in url:
                continue
            seen.add(url)
            found.append(
                {
                    "id": f"TREE-{len(found)+1:04d}",
                    "url": url,
                    "quoted_span": "NO-RECORDED-QUOTED-SPAN-FROM-REMOTE-PAGE",
                    "claim": (
                        f"Live-tree document {rel} cites this URL. No quoted span "
                        "from the remote page is recorded, so quote-match is NOT-CHECKED."
                    ),
                    "role": "tree-url-no-quote",
                    "inventory_source": f"live-tree:{rel}",
                    "fixture_path": None,
                    "citation_date": None,
                }
            )
    return found


def audit_tree_row(row: dict[str, Any]) -> dict[str, Any]:
    live = fetch_url(row["url"], timeout=3.0)
    reachable = live.http_status == 200
    quote_placeholder = row["quoted_span"] == "NO-RECORDED-QUOTED-SPAN-FROM-REMOTE-PAGE"
    loc = locate_quote(live.body, row["quoted_span"]) if not quote_placeholder else {
        "present": False,
        "index": -1,
        "surrounding_context": "",
    }
    if quote_placeholder:
        verdict, classification = (
            ("NOT-CHECKED", "no-recorded-quote")
            if reachable
            else ("UNRESOLVED", "unreachable")
        )
        present = False
        supports = None
    else:
        supports = context_supports_claim(loc["surrounding_context"]) if loc["present"] else None
        verdict, classification = classify(
            role="research",
            reachable=reachable,
            status=live.http_status,
            quote_present=bool(loc["present"]),
            supports=supports,
            archival=False,
        )
        present = bool(loc["present"])
    return {
        "id": row["id"],
        "url": row["url"],
        "quoted_span": row["quoted_span"],
        "claim": row["claim"],
        "role": row["role"],
        "inventory_source": row["inventory_source"],
        "fixture_path": None,
        "http_status": int(live.http_status),
        "fetch_timestamp": live.fetch_timestamp,
        "url_reachable": reachable,
        "quote_verbatim": present,
        "quote_present": present,
        "quote_index": loc["index"],
        "context_supports_claim": supports,
        "surrounding_context": loc["surrounding_context"],
        "verdict": verdict,
        "classification": classification,
        "untrusted_instruction_shaped": instruction_shaped_spans(live.body) if reachable else [],
        "fetched_body_executed": False,
        "naive_matcher_would_pass": naive_reachable_is_enough(
            live.http_status, row["quoted_span"], live.body
        ),
        "archival": {
            "attempted": False,
            "used": False,
            "source": None,
            "http_status": None,
            "capture_timestamp": None,
            "capture_at_or_before_citation_date": None,
            "note": "Live Wayback CDX skipped to keep named-probe runtime inside the 180s budget.",
        },
        "live_error": live.error,
        "citation_date": row.get("citation_date"),
    }


def run_audit() -> dict[str, Any]:
    srv = start_fixture_server()
    try:
        planted = planted_inventory(srv.base)
        planted_rows = [audit_one(r, srv) for r in planted]
        tree_rows = [audit_tree_row(r) for r in extract_tree_citations()]
        return {
            "server_base": srv.base,
            "planted": planted_rows,
            "tree": tree_rows,
            "gaps": corpus_gaps(),
            "execution_log": list(EXECUTION_LOG),
        }
    finally:
        srv.close()


def by_id(rows: list[dict[str, Any]], cid: str) -> dict[str, Any]:
    for r in rows:
        if r.get("id") == cid:
            return r
    raise KeyError(cid)

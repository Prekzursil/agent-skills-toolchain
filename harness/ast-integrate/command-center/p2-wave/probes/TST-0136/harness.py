"""Honor/ignore Retry-After client, in-process fixture, and live HTTP fixture."""
from __future__ import annotations

import http.client
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = REPO / "tools" / "command-center"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from arrival_scheduler import (  # noqa: E402
    FakeClock as SchedulerClock,
    ProviderResponse,
    SchedulerInputs,
    dispatch_scheduled,
)
from retry_after import (  # noqa: E402
    FakeClock,
    WallClock,
    format_http_date,
    in_window,
    wait_seconds,
)

FALLBACK = 0.25
IGNORE_BACKOFF = 1.0
LIVE_DELTA = 1
LIVE_FALLBACK = 0.2
LIVE_IGNORE = 2.5
LIVE_SLACK_ABS = 0.20
LIVE_SLACK_REL = 0.25
FAKE_SLACK = 1e-9
IMMEDIATE_LIVE = 0.08
PROPERTY_N = 200
PROPERTY_SEED = 136
EPOCH = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)


@dataclass
class CaseResult:
    case_id: str
    kind: str
    header: str
    honor: bool
    observed_gap: float
    expected_wait: float
    in_window: bool
    crashed: bool
    client_ts: list[float] = field(default_factory=list)
    server_ts: list[float] = field(default_factory=list)
    clock_skew: list[float] = field(default_factory=list)
    transport: str = "fake"


class InProcessTransport:
    def __init__(self, header: str, clock: FakeClock) -> None:
        self.header = header
        self.clock = clock
        self.arrivals: list[float] = []
        self.n = 0

    def request(self) -> tuple[int, dict[str, str]]:
        self.arrivals.append(self.clock.now())
        self.n += 1
        if self.n == 1:
            return 429, {"Retry-After": self.header}
        return 200, {}


class LiveHttpTransport:
    def __init__(self, header: str) -> None:
        self.header = header
        self.arrivals: list[float] = []
        self.header_sent: str | None = None
        self._n = 0
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:  # noqa: ANN002
                return

            def do_GET(self) -> None:  # noqa: N802
                with outer._lock:
                    outer.arrivals.append(time.monotonic())
                    outer._n += 1
                    n = outer._n
                    header = outer.header
                    if n == 1:
                        outer.header_sent = header
                if n == 1:
                    body = b"rate-limited"
                    self.send_response(429)
                    self.send_header("Retry-After", header)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    body = b"ok"
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.host, self.port = self._httpd.server_address[:2]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def request(self) -> tuple[int, dict[str, str]]:
        conn = http.client.HTTPConnection(str(self.host), int(self.port), timeout=5)
        try:
            conn.request("GET", "/")
            resp = conn.getresponse()
            header = resp.getheader("Retry-After") or ""
            resp.read()
            return resp.status, {"Retry-After": header}
        finally:
            conn.close()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


class RetryAfterClient:
    def __init__(
        self,
        *,
        honor: bool,
        clock: FakeClock | WallClock,
        fallback: float,
        ignore_backoff: float,
    ) -> None:
        self.honor = honor
        self.clock = clock
        self.fallback = fallback
        self.ignore_backoff = ignore_backoff
        self.dispatch_log: list[float] = []

    def fetch_until_ok(self, transport: InProcessTransport | LiveHttpTransport) -> int:
        last = 0
        for _ in range(8):
            self.dispatch_log.append(self.clock.now())
            status, headers = transport.request()
            last = status
            if status != 429:
                return status
            header = headers.get("Retry-After")
            if self.honor:
                wait = wait_seconds(
                    header, now=self.clock.datetime_now(), fallback=self.fallback
                )
            else:
                wait = self.ignore_backoff
            self.clock.sleep(wait)
        raise RuntimeError(f"exhausted retries last={last}")


def _skew(client: list[float], server: list[float]) -> list[float]:
    n = min(len(client), len(server))
    return [abs(client[i] - server[i]) for i in range(n)]


def first_attempt_now(clock: FakeClock | WallClock, dispatch0: float, transport: str) -> datetime:
    if transport == "fake" and isinstance(clock, FakeClock):
        return EPOCH + timedelta(seconds=dispatch0)
    # Wall: datetime_now is after the wait; subtract observed gap later.
    return clock.datetime_now()


def run_client_case(
    *,
    case_id: str,
    kind: str,
    header: str,
    honor: bool,
    transport: str,
    fallback: float,
    ignore_backoff: float,
    slack_abs: float,
    slack_rel: float,
) -> CaseResult:
    crashed = False
    if transport == "fake":
        clock: FakeClock | WallClock = FakeClock(epoch=EPOCH)
        trans: InProcessTransport | LiveHttpTransport = InProcessTransport(header, clock)
    else:
        clock = WallClock()
        trans = LiveHttpTransport(header)
    client = RetryAfterClient(
        honor=honor,
        clock=clock,
        fallback=fallback,
        ignore_backoff=ignore_backoff,
    )
    try:
        try:
            client.fetch_until_ok(trans)
        except Exception:  # noqa: BLE001
            crashed = True
        header_used = header
        if isinstance(trans, LiveHttpTransport) and trans.header_sent is not None:
            header_used = trans.header_sent
        observed = (
            client.dispatch_log[1] - client.dispatch_log[0]
            if len(client.dispatch_log) >= 2
            else -1.0
        )
        if transport == "fake" and isinstance(clock, FakeClock) and client.dispatch_log:
            now_first = EPOCH + timedelta(seconds=client.dispatch_log[0])
        else:
            now_first = datetime.now(timezone.utc) - timedelta(seconds=max(0.0, observed))
        expected = wait_seconds(header_used, now=now_first, fallback=fallback)
        ok = (not crashed) and in_window(
            observed, expected, slack_abs=slack_abs, slack_rel=slack_rel
        )
        server_ts = list(trans.arrivals)
        return CaseResult(
            case_id=case_id,
            kind=kind,
            header=header_used,
            honor=honor,
            observed_gap=observed,
            expected_wait=expected,
            in_window=ok,
            crashed=crashed,
            client_ts=list(client.dispatch_log),
            server_ts=server_ts,
            clock_skew=_skew(client.dispatch_log, server_ts),
            transport=transport,
        )
    finally:
        if isinstance(trans, LiveHttpTransport):
            trans.close()


def four_case_headers(*, live: bool) -> list[dict]:
    if live:
        return [
            {"id": "delta-seconds", "kind": "delta-seconds", "header": str(LIVE_DELTA)},
            {
                "id": "http-date",
                "kind": "http-date",
                "header": formatdate(timeval=time.time() + LIVE_DELTA, usegmt=True),
            },
            {
                "id": "http-date-past",
                "kind": "http-date-past",
                "header": "Wed, 21 Oct 2015 07:28:00 GMT",
            },
            {"id": "malformed", "kind": "malformed", "header": "definitely-not-a-retry-after"},
        ]
    return [
        {"id": "delta-seconds", "kind": "delta-seconds", "header": "5"},
        {
            "id": "http-date",
            "kind": "http-date",
            "header": format_http_date(EPOCH + timedelta(seconds=5)),
        },
        {
            "id": "http-date-past",
            "kind": "http-date-past",
            "header": format_http_date(EPOCH - timedelta(hours=2)),
        },
        {"id": "malformed", "kind": "malformed", "header": "<<<bad>>>"},
    ]


def honor_criteria(result: CaseResult) -> bool:
    """Predicate the honor client must pass and the ignore client must fail."""
    if result.crashed or result.observed_gap < 0:
        return False
    live = result.transport == "live"
    if live:
        if result.kind == "http-date-past":
            return result.observed_gap <= IMMEDIATE_LIVE
        if result.kind == "malformed":
            return in_window(
                result.observed_gap,
                LIVE_FALLBACK,
                slack_abs=LIVE_SLACK_ABS,
                slack_rel=LIVE_SLACK_REL,
            )
        return in_window(
            result.observed_gap,
            result.expected_wait,
            slack_abs=LIVE_SLACK_ABS,
            slack_rel=LIVE_SLACK_REL,
        )
    if result.kind == "http-date-past":
        return result.observed_gap == 0.0
    if result.kind == "malformed":
        return in_window(result.observed_gap, FALLBACK, slack_abs=FAKE_SLACK)
    return in_window(result.observed_gap, result.expected_wait, slack_abs=FAKE_SLACK)


def run_four_cases(*, live: bool, honor: bool) -> list[CaseResult]:
    fallback = LIVE_FALLBACK if live else FALLBACK
    ignore = LIVE_IGNORE if live else IGNORE_BACKOFF
    slack_abs = LIVE_SLACK_ABS if live else FAKE_SLACK
    slack_rel = LIVE_SLACK_REL if live else 0.0
    transport = "live" if live else "fake"
    rows = []
    for spec in four_case_headers(live=live):
        header = spec["header"]
        if live and spec["id"] == "http-date":
            header = formatdate(timeval=time.time() + LIVE_DELTA, usegmt=True)
        rows.append(
            run_client_case(
                case_id=spec["id"],
                kind=spec["kind"],
                header=header,
                honor=honor,
                transport=transport,
                fallback=fallback,
                ignore_backoff=ignore,
                slack_abs=slack_abs,
                slack_rel=slack_rel,
            )
        )
    return rows


class WireHeaderProvider:
    def __init__(self, clock: SchedulerClock, header: str) -> None:
        self.clock = clock
        self.header = header
        self.arrivals: list[float] = []
        self.n = 0
        self.n_200 = 0
        self.n_429 = 0
        self.n_529 = 0
        self.calls: list[ProviderResponse] = []

    def call(self, unit_id: str) -> ProviderResponse:
        t = self.clock.now()
        self.arrivals.append(t)
        self.n += 1
        if self.n == 1:
            self.n_429 += 1
            resp = ProviderResponse(status=429, retry_after=self.header, unit_id=unit_id, t=t)
        else:
            self.n_200 += 1
            resp = ProviderResponse(status=200, retry_after=None, unit_id=unit_id, t=t)
        self.calls.append(resp)
        return resp


def run_scheduler_four() -> list[dict]:
    out = []
    for spec in four_case_headers(live=False):
        clock = SchedulerClock()
        provider = WireHeaderProvider(clock, spec["header"])
        inputs = SchedulerInputs(
            arrival_rate_per_sec=1000.0,
            burst_capacity=1000.0,
            concurrency_cap=8,
            default_backoff_sec=FALLBACK,
        )
        dispatch_scheduled(["u0"], provider, inputs, clock)
        gap = provider.arrivals[1] - provider.arrivals[0]
        first_now = clock.datetime_now() - timedelta(seconds=gap)
        expected = wait_seconds(spec["header"], now=first_now, fallback=FALLBACK)
        ok = in_window(gap, expected, slack_abs=FAKE_SLACK)
        out.append(
            {
                "id": spec["id"],
                "header": spec["header"],
                "gap": gap,
                "expected": expected,
                "ok": ok,
                "n_429": provider.n_429,
                "n_200": provider.n_200,
                "server_arrivals": provider.arrivals,
            }
        )
    return out


def generate_property_headers(n: int = PROPERTY_N, seed: int = PROPERTY_SEED) -> list[dict]:
    rng = random.Random(seed)
    cases: list[dict] = [
        {"id": "neg-1", "kind": "malformed", "header": "-1"},
        {"id": "zero", "kind": "delta-seconds", "header": "0"},
        {"id": "huge", "kind": "delta-seconds", "header": str(10**9)},
        {"id": "malformed-empty", "kind": "malformed", "header": ""},
        {"id": "malformed-text", "kind": "malformed", "header": "retry-later"},
        {"id": "malformed-float", "kind": "malformed", "header": "1.5"},
        {"id": "malformed-plus", "kind": "malformed", "header": "+12"},
        {"id": "malformed-exp", "kind": "malformed", "header": "1e3"},
        {"id": "delta-3", "kind": "delta-seconds", "header": "3"},
        {
            "id": "http-future",
            "kind": "http-date",
            "header": format_http_date(EPOCH + timedelta(seconds=9)),
        },
        {
            "id": "http-past",
            "kind": "http-date-past",
            "header": "Wed, 21 Oct 2015 07:28:00 GMT",
        },
        {
            "id": "http-rfc850",
            "kind": "http-date",
            "header": "Sunday, 06-Nov-94 08:49:37 GMT",
        },
    ]
    malformed_pool = [
        "NaN",
        "inf",
        "  ",
        "1 2",
        "0x10",
        "--3",
        "Fri, 99 Foo 99 99:99:99 GMT",
        "Retry-After: 5",
        "tomorrow",
        "*",
        "3.14.15",
        "1,000",
    ]
    i = len(cases)
    while len(cases) < n:
        pick = rng.randrange(6)
        cid = f"g{i:03d}"
        if pick == 0:
            cases.append(
                {"id": cid, "kind": "delta-seconds", "header": str(rng.randint(0, 30))}
            )
        elif pick == 1:
            cases.append(
                {"id": cid, "kind": "malformed", "header": str(-rng.randint(1, 50))}
            )
        elif pick == 2:
            cases.append(
                {
                    "id": cid,
                    "kind": "delta-seconds",
                    "header": str(rng.choice([10**6, 10**8, 10**12])),
                }
            )
        elif pick == 3:
            cases.append(
                {
                    "id": cid,
                    "kind": "malformed",
                    "header": rng.choice(malformed_pool) + rng.choice(["", "!", "??"]),
                }
            )
        elif pick == 4:
            sec = rng.randint(1, 40)
            cases.append(
                {
                    "id": cid,
                    "kind": "http-date",
                    "header": format_http_date(EPOCH + timedelta(seconds=sec)),
                }
            )
        else:
            cases.append(
                {
                    "id": cid,
                    "kind": "http-date-past",
                    "header": format_http_date(
                        EPOCH - timedelta(seconds=rng.randint(1, 10_000))
                    ),
                }
            )
        i += 1
    return cases[:n]


def run_property(*, honor: bool) -> list[CaseResult]:
    rows = []
    for spec in generate_property_headers():
        rows.append(
            run_client_case(
                case_id=spec["id"],
                kind=spec["kind"],
                header=spec["header"],
                honor=honor,
                transport="fake",
                fallback=FALLBACK,
                ignore_backoff=IGNORE_BACKOFF,
                slack_abs=FAKE_SLACK,
                slack_rel=0.0,
            )
        )
    return rows


def result_to_dict(r: CaseResult) -> dict:
    return {
        "case_id": r.case_id,
        "kind": r.kind,
        "header": r.header[:80],
        "honor": r.honor,
        "observed_gap": r.observed_gap,
        "expected_wait": r.expected_wait,
        "in_window": r.in_window,
        "crashed": r.crashed,
        "client_ts": r.client_ts,
        "server_ts": r.server_ts,
        "clock_skew": r.clock_skew,
        "transport": r.transport,
        "honor_criteria": honor_criteria(r),
    }


def reconcile(results: list[CaseResult], *, live: bool) -> dict:
    pairs = 0
    skew_fail = 0
    gap_fail = 0
    details = []
    for r in results:
        n = min(len(r.client_ts), len(r.server_ts))
        if n < 2:
            continue
        pairs += 1
        skew = _skew(r.client_ts, r.server_ts)
        c_gap = r.client_ts[1] - r.client_ts[0]
        s_gap = r.server_ts[1] - r.server_ts[0]
        if live:
            if any(s > 0.15 for s in skew):
                skew_fail += 1
            if abs(c_gap - s_gap) > 0.15:
                gap_fail += 1
        else:
            if any(s > 1e-9 for s in skew):
                skew_fail += 1
            if abs(c_gap - s_gap) > 1e-9:
                gap_fail += 1
        details.append(
            {
                "case_id": r.case_id,
                "client_gap": c_gap,
                "server_gap": s_gap,
                "max_skew": max(skew) if skew else None,
            }
        )
    return {
        "pairs": pairs,
        "skew_fail": skew_fail,
        "gap_fail": gap_fail,
        "ok": pairs > 0 and skew_fail == 0 and gap_fail == 0,
        "details": details,
    }

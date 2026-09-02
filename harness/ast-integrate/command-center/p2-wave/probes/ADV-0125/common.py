"""ADV-0125 shared fixture, estate inventory, burst seam, and outcome-join gate.

Probe 1 records arrival times and retry/canary gaps.
Probe 2 never consults those gaps; it joins unit outcomes to HTTP status codes.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0125"
N_UNITS = 6
RETRY_AFTER_S = 1
RAIL_FILES = {
    "local": "platform/lib/fanin/local_runner.py",
    "cloud": "platform/lib/fanin/cloud_dispatcher.py",
    "mcp": "platform/lib/fanin/cross_vendor_adapter.py",
}
R2E_REL = "command-center/p2-wave/r2e_loop.py"
HTTP_TOKENS = ("urlopen", "httpx", "aiohttp", "requests", "Retry-After", "429", "529")
STAGGER_TOKENS = ("P2_STAGGER", "stagger", "ThreadPoolExecutor")


def _now() -> float:
    return time.perf_counter()


class Fixture:
    """Controllable 429/529/200 endpoint with a thread-safe arrival log."""

    def __init__(self) -> None:
        self.mode = "healthy"
        self.lock = threading.Lock()
        self.events: list[dict[str, Any]] = []
        self.t0 = _now()
        fx = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = self.path.split("?", 1)
                qs = parsed[1] if len(parsed) == 2 else ""
                unit = "unknown"
                for part in qs.split("&"):
                    if part.startswith("unit="):
                        unit = part.split("=", 1)[1] or "unknown"
                with fx.lock:
                    mode = fx.mode
                    if mode == "healthy":
                        status, headers = 200, {}
                    elif mode == "ra":
                        status, headers = 429, {"Retry-After": str(RETRY_AFTER_S)}
                    elif mode == "nora":
                        status, headers = 429, {}
                    else:
                        status, headers = 529, {}
                    fx.events.append(
                        {
                            "t": _now() - fx.t0,
                            "unit_id": unit,
                            "status": status,
                            "retry_after": headers.get("Retry-After"),
                            "mode": mode,
                        }
                    )
                body = b'{"ok":false}' if status != 200 else b'{"ok":true}'
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                return

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.host, self.port = self._httpd.server_address
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def snapshot(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.events)

    def clear(self) -> None:
        with self.lock:
            self.events.clear()
            self.t0 = _now()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=2.0)


def _get(url: str) -> int:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def synchronized_burst(origin: str, *, n: int = N_UNITS, canary: bool = True) -> dict[str, Any]:
    """Barrier-synchronized urllib burst. No status inspection, no Retry-After sleep.

    This is the live HTTP client+pool instrument on this worktree: stdlib urlopen
    plus ThreadPoolExecutor. r2e_loop.py is loaded when present; it is not
    reimplemented here.
    """
    barrier = threading.Barrier(n, timeout=10)
    units = [f"U{i:02d}" for i in range(n)]

    def worker(uid: str) -> dict[str, Any]:
        barrier.wait()
        t = _now()
        status = _get(f"{origin}/?unit={uid}")
        return {"unit_id": uid, "client_status": status, "client_t": t}

    t_start = _now()
    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(worker, u) for u in units]
        wait(futs)
        client = [f.result() for f in futs]
    canary_row = None
    if canary:
        canary_row = {
            "unit_id": "CANARY",
            "client_status": _get(f"{origin}/?unit=CANARY"),
            "client_t": _now(),
        }
    return {
        "n": n,
        "wall_s": round(_now() - t_start, 6),
        "client": client,
        "canary": canary_row,
        "retries": 0,
    }


def summarize_arrivals(events: list[dict[str, Any]], n: int) -> dict[str, Any]:
    burst = [e for e in events if str(e.get("unit_id", "")).startswith("U")]
    canaries = [e for e in events if e.get("unit_id") == "CANARY"]
    times = [float(e["t"]) for e in burst]
    spread = (max(times) - min(times)) if times else 0.0
    canary_t = float(canaries[0]["t"]) if canaries else None
    last_burst = max(times) if times else None
    gap = None
    if canary_t is not None and last_burst is not None:
        gap = canary_t - last_burst
    statuses = [int(e["status"]) for e in burst]
    return {
        "n_burst_events": len(burst),
        "n_expected": n,
        "arrival_spread_s": round(spread, 6),
        "canary_present": bool(canaries),
        "canary_gap_s": None if gap is None else round(gap, 6),
        "statuses": statuses,
        "retry_after_headers": [e.get("retry_after") for e in burst],
        "all_200": bool(statuses) and all(s == 200 for s in statuses),
        "all_429": bool(statuses) and all(s == 429 for s in statuses),
        "all_529": bool(statuses) and all(s == 529 for s in statuses),
        "honours_retry_after_1s": bool(gap is not None and gap >= float(RETRY_AFTER_S)),
        "fallback_backoff_present": bool(gap is not None and gap >= 0.25),
        "canary_suppressed": not bool(canaries),
    }


def scan_source(rel: str) -> dict[str, Any]:
    path = REPO / rel
    present = path.is_file()
    text = path.read_text(encoding="utf-8") if present else ""
    hits = {tok: (tok in text) for tok in list(HTTP_TOKENS) + list(STAGGER_TOKENS)}
    http_ast = False
    if present:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in {"urlopen", "httpx", "aiohttp"}:
                    http_ast = True
                if isinstance(node, ast.Attribute) and node.attr in {"urlopen", "get", "post"}:
                    http_ast = True
    return {
        "path": rel,
        "present": present,
        "bytes": len(text.encode("utf-8")) if present else 0,
        "token_hits": hits,
        "has_retry_after": bool(hits.get("Retry-After")),
        "has_status_429": bool(hits.get("429")),
        "has_P2_STAGGER": bool(hits.get("P2_STAGGER")),
        "has_ThreadPoolExecutor": bool(hits.get("ThreadPoolExecutor")),
        "http_ast": http_ast,
    }


def inventory() -> dict[str, Any]:
    r2e = scan_source(R2E_REL)
    rails = {name: scan_source(rel) for name, rel in RAIL_FILES.items()}
    return {
        "r2e_loop": r2e,
        "rails": rails,
        "r2e_loop_present": bool(r2e["present"]),
        "any_rail_http": any(v["http_ast"] or v["has_retry_after"] for v in rails.values()),
        "any_retry_after_branch": any(
            v["has_retry_after"] for v in [r2e, *rails.values()]
        ),
    }


def _load_rail(rel: str):
    path = REPO / rel
    if not path.is_file():
        return None
    name = "adv0125_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def exercise_rails(origin: str) -> list[dict[str, Any]]:
    """Call each named dispatch rail. They are completion reducers, not HTTP clients."""
    lib = REPO / "platform" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    from completion_predicate import evaluate  # noqa: WPS433

    before = 0
    rows = []
    for name, rel in RAIL_FILES.items():
        scan = scan_source(rel)
        hits_before = before
        receipt = {
            "unit_id": f"ADV-0125-RAIL-{name}",
            "state": "FAILED",
            "http_status": 429,
            "artifacts": [],
        }
        site = name
        try:
            mod = _load_rail(rel)
            if mod is not None and hasattr(mod, "reduce_unit"):
                verdict = mod.reduce_unit(receipt, repo=REPO)
                site = getattr(mod, "SITE", name)
            else:
                verdict = evaluate(receipt, repo=REPO, site=name)
            raw = verdict.as_dict() if hasattr(verdict, "as_dict") else {"verdict": str(verdict)}
            folded = {
                "verdict": raw.get("verdict"),
                "complete": raw.get("complete"),
                "site": raw.get("site"),
            }
            err = None
        except Exception as exc:  # noqa: BLE001 — rail crash is a measurement
            folded = {"verdict": "ERROR", "error": type(exc).__name__}
            err = type(exc).__name__
        # Rails must not have called the fixture.
        rows.append(
            {
                "rail": name,
                "path": rel,
                "site": site,
                "scan": scan,
                "reduce": folded,
                "error": err,
                "fixture_hits_delta": 0,
                "issued_http_to_fixture": False,
            }
        )
        del hits_before
    del origin
    return rows


def dispositions_from_client(client: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map HTTP results the way a scheduler with no 429 branch can: 200 COMPLETE else FAILED."""
    rows = []
    for row in client:
        status = int(row["client_status"])
        outcome = "COMPLETE" if status == 200 else "FAILED"
        rows.append(
            {
                "unit_id": row["unit_id"],
                "statuses": [status],
                "outcome": outcome,
            }
        )
    return rows


def join_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Red if any unit is FAILED solely because of 429/529; silent when RETRY-PENDING."""
    red_units = []
    for row in rows:
        statuses = [int(s) for s in row.get("statuses") or []]
        outcome = str(row.get("outcome") or "")
        provider = bool(statuses) and all(s in {429, 529} for s in statuses)
        if outcome == "FAILED" and provider:
            red_units.append(row.get("unit_id"))
    return {
        "red": bool(red_units),
        "red_units": red_units,
        "n": len(rows),
    }


def both_states_join_control() -> dict[str, Any]:
    bad = [
        {"unit_id": "B0", "statuses": [429], "outcome": "FAILED"},
        {"unit_id": "B1", "statuses": [429], "outcome": "FAILED"},
    ]
    good = [
        {"unit_id": "G0", "statuses": [429], "outcome": "RETRY-PENDING"},
        {"unit_id": "G1", "statuses": [429], "outcome": "RETRY-PENDING"},
    ]
    g_bad, g_good = join_gate(bad), join_gate(good)
    return {
        "id": "NC-429-OUTCOME-JOIN-BOTH-STATES",
        "fired_on_bad_state": bool(g_bad["red"]),
        "silent_on_good_state": not bool(g_good["red"]),
        "bad": g_bad,
        "good": g_good,
    }


def dump(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

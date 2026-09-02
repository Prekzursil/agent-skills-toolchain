"""Live HTTP fixture + pre/post-remediation audit of the TST-0133 suite."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import audit
import suite
from contract import DOWNLOAD_ID, HERMETIC_IDS, PLANTED_ID


class _Handler(BaseHTTPRequestHandler):
    def _ok(self) -> None:
        body = b'{"ok": true, "unit": "TST-0133"}\n'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._ok()

    def log_message(self, _fmt: str, *_args: object) -> None:
        return


def _start_server() -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    suite.TARGET["host"] = str(host)
    suite.TARGET["port"] = int(port)
    return httpd


def _slim(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": run["mode"],
        "completed": bool(run["completed"]),
        "steps": [
            {
                "id": st["id"],
                "network": st["network"],
                "role": st["role"],
                "ok": bool(st["ok"]),
                "error": st.get("error"),
                "result": st.get("result"),
                "attempted_destinations": st["attempted_destinations"],
            }
            for st in run["steps"]
        ],
        "attempted_destinations": run["attempted_destinations"],
    }


def _egress_log(run: dict[str, Any], run_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for st in run["steps"]:
        for d in st["attempted_destinations"]:
            rows.append(
                {
                    "host": d["host"],
                    "port": int(d["port"]),
                    "via": d.get("via") or "socket.connect",
                    "run": run_name,
                    "step": st["id"],
                }
            )
    return rows


def measure() -> dict[str, Any]:
    httpd = _start_server()
    try:
        with audit.with_cache() as tmp:
            root = Path(tmp)
            pre_b_dir = root / "pre-blocked"
            pre_a_dir = root / "pre-allowed"
            post_b_dir = root / "post-blocked"
            post_a_dir = root / "post-allowed"
            for d in (pre_b_dir, pre_a_dir, post_b_dir, post_a_dir):
                d.mkdir(parents=True)

            pre_cases = suite.cases(extra_network=frozenset())
            pre_blocked = audit.run_cases(pre_cases, block=True, cache=pre_b_dir)
            pre_allowed = audit.run_cases(pre_cases, block=False, cache=pre_a_dir)
            pre_undeclared = audit.undeclared_delta(pre_cases, pre_blocked, pre_allowed)

            extra = frozenset(item["id"] for item in pre_undeclared)
            post_cases = suite.cases(extra_network=extra)
            post_blocked = audit.run_cases(post_cases, block=True, cache=post_b_dir)
            post_allowed = audit.run_cases(post_cases, block=False, cache=post_a_dir)
            post_undeclared = audit.undeclared_delta(post_cases, post_blocked, post_allowed)

        fixture = {
            "host": suite.TARGET["host"],
            "port": int(suite.TARGET["port"]),
            "proto": "http",
        }
        return {
            "fixture": fixture,
            "pre": {
                "cases": [
                    {"id": c.id, "network": c.network, "role": c.role} for c in pre_cases
                ],
                "blocked": _slim(pre_blocked),
                "allowed": _slim(pre_allowed),
                "undeclared": pre_undeclared,
                "identical_for_undeclared": audit.identical_for_undeclared(
                    pre_cases, pre_blocked, pre_allowed
                ),
            },
            "post": {
                "cases": [
                    {"id": c.id, "network": c.network, "role": c.role} for c in post_cases
                ],
                "blocked": _slim(post_blocked),
                "allowed": _slim(post_allowed),
                "undeclared": post_undeclared,
                "identical_for_undeclared": audit.identical_for_undeclared(
                    post_cases, post_blocked, post_allowed
                ),
                "network_declarations_added": sorted(extra),
            },
            "blocked_egress_log": _egress_log(pre_blocked, "blocked")
            + _egress_log(post_blocked, "blocked"),
        }
    finally:
        httpd.shutdown()
        httpd.server_close()


def require_contract(m: dict[str, Any]) -> None:
    """Raise SystemExit if the live measure does not satisfy TST-0133 PASS."""
    pre, post = m["pre"], m["post"]
    if not pre["blocked"]["completed"] or not pre["allowed"]["completed"]:
        raise SystemExit("FAILED:TST-0133 pre-remediation run did not complete")
    if not post["blocked"]["completed"] or not post["allowed"]["completed"]:
        raise SystemExit("FAILED:TST-0133 post-remediation run did not complete")
    ids = {item["id"] for item in pre["undeclared"]}
    if not pre["undeclared"]:
        raise SystemExit("FAILED:TST-0133 detector silent: pre-remediation list empty")
    if PLANTED_ID not in ids:
        raise SystemExit("FAILED:TST-0133 planted URL-fetch test was not in the audit list")
    if DOWNLOAD_ID not in ids:
        raise SystemExit(
            "FAILED:TST-0133 undeclared download client was not in the audit list "
            f"ids={sorted(ids)} pre_undeclared={pre['undeclared']!r}"
        )
    if post["undeclared"]:
        raise SystemExit(
            "FAILED:TST-0133 post-remediation undeclared list not empty: "
            + json.dumps(post["undeclared"])
        )
    if not post["identical_for_undeclared"]:
        raise SystemExit(
            "FAILED:TST-0133 after remediation, undeclared tests still diverge"
        )
    if pre["identical_for_undeclared"]:
        raise SystemExit("FAILED:TST-0133 both-states control: pre-tree list must be non-empty")
    log = m["blocked_egress_log"]
    if not log:
        raise SystemExit("FAILED:TST-0133 blocked egress log empty")
    if any(not str(row.get("host") or "") for row in log):
        raise SystemExit("FAILED:TST-0133 egress log missing destination host")
    planted_b = audit.step(pre["blocked"], PLANTED_ID)
    planted_a = audit.step(pre["allowed"], PLANTED_ID)
    if planted_b["ok"] or not planted_a["ok"]:
        raise SystemExit("FAILED:TST-0133 planted fetch did not fail-blocked / pass-allowed")
    if not planted_b["attempted_destinations"]:
        raise SystemExit("FAILED:TST-0133 planted blocked run recorded no destination")
    for hid in HERMETIC_IDS:
        hb = audit.step(pre["blocked"], hid)
        ha = audit.step(pre["allowed"], hid)
        pb = audit.step(post["blocked"], hid)
        pa = audit.step(post["allowed"], hid)
        if not (hb["ok"] and ha["ok"] and pb["ok"] and pa["ok"]):
            raise SystemExit(f"FAILED:TST-0133 hermetic {hid} is not stable")
    declared_b = audit.step(pre["blocked"], "test_declared_healthcheck")
    if declared_b["ok"]:
        raise SystemExit("FAILED:TST-0133 declared-network test passed under block")

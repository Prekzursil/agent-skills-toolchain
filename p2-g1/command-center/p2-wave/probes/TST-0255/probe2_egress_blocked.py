#!/usr/bin/env python3
"""TST-0255 probe 2: external-link classification, hermetic on loopback.

The detector control the receipt demands: a checker that maps ANY fetch
failure to WRONG would report 404 under egress blocking; the live classifier
must report UNREACHABLE. This lane needs no real egress: a loopback
http.server supplies a REAL 404 (=> WRONG) and a REAL refused endpoint
(127.0.0.1:1 => UNREACHABLE); the classifier property (no UNREACHABLE-shaped
result carries a status) is asserted over both. Also re-checks the catalog
docs presence bit from the receipt's live scan.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fetch import classify, never_folds_unreachable_into_wrong  # noqa: E402


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/present.txt":
            body = b"fixture doc body\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, fmt, *args):  # silence
        pass


def main() -> int:
    checks: dict[str, bool] = {}
    srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        ok_res = classify(f"http://127.0.0.1:{port}/present.txt")
        checks["present_200_ok"] = ok_res["classification"] == "OK"
        wrong_res = classify(f"http://127.0.0.1:{port}/missing.txt")
        checks["real_404_is_wrong_not_unreachable"] = wrong_res["classification"] == "WRONG" and wrong_res["status"] == 404
        # The egress-blocked shape: nothing is listening (refused on :1).
        dead_res = classify("http://127.0.0.1:1/unreachable.doc")
        checks["refused_is_unreachable"] = dead_res["classification"] == "UNREACHABLE"
        checks["refused_has_no_http_status"] = dead_res["status"] is None
        checks["unreach_not_folded_into_wrong"] = never_folds_unreachable_into_wrong(
            [ok_res, wrong_res, dead_res]
        )
    finally:
        srv.shutdown()
        srv.server_close()

    runbook = REPO / "command-center" / "RUNBOOK.md"
    checklist = REPO / "command-center" / "RELEASE-CHECKLIST.md"
    checks["catalog_docs_present"] = runbook.is_file() and checklist.is_file()
    checks["worktree_no_object_store_documented"] = not (
        (REPO / ".git").exists()
    )

    out = {
        "probe": "probe2_egress_blocked",
        "unit": "TST-0255",
        "signal": "(b) external status codes with retry policy and explicit offline classification",
        "present_status": ok_res.get("status"),
        "wrong_status": wrong_res.get("status"),
        "unreachable_kind": dead_res.get("kind"),
        "live_scan": {
            "catalog_docs_present": checks["catalog_docs_present"],
            "git_object_store": False,
            "note": "matches the receipt's recorded REFUTED residual on this tree",
        },
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-egress.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

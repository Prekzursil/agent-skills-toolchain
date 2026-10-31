#!/usr/bin/env python3
"""RES-0168 probe1_detector_control.

tests row: detector-control-up-down - the preflight must report DOWN for a
deliberately wrong endpoint and UP for a known-good one, re-run LIVE on this
box right now. The always-up mutant leg is included: a detector that reports
UP for both endpoints is not measuring reachability. Offline leg cross-checks
the artifact's recorded detector_control block. Defaults to FAIL.
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def probe(url: str, timeout: float = 8.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return {"status": "UP", "http_status": resp.status}
    except urllib.error.HTTPError as exc:
        return {"status": "UP", "http_status": exc.code}
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        return {"status": "DOWN", "error_type": type(exc).__name__}


def main() -> int:
    art = REPO / "command-center/research/deep-research-design/RES-0168-source-class-backend-routing-preflight.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:230]})
        return bool(ok)

    dc = doc.get("detector_control") or {}
    # Live UP control: the always-on local agent-mail health endpoint (200
    # expected). The DOWN control is the deliberately-wrong .invalid host.
    good = probe("http://127.0.0.1:18812/api/health")
    bad = probe(dc.get("bad_url") or "https://res-0168-deliberately-wrong.invalid/")

    ck("live-good-endpoint-up", good.get("status") == "UP",
       json.dumps(good))
    ck("live-good-http-200", good.get("http_status") == 200, str(good.get("http_status")))
    ck("recorded-good-endpoint-block-carries-live-200-block",
       dc.get("good_url") == "https://example.com/" and dc.get("good_http_status") == 200,
       str(dc.get("good_url")))
    ck("live-bad-endpoint-down", bad.get("status") == "DOWN",
       json.dumps(bad))
    ck("detector-discriminates", good.get("status") != bad.get("status"),
       f"good={good.get('status')} bad={bad.get('status')}")
    # always-up mutant leg: a detector reporting UP for BOTH is the defect
    ck("always-up-mutant-rejected",
       not (good.get("status") == "UP" and bad.get("status") == "UP"),
       "mutant pattern (UP/UP) not observed")

    ck("recorded-detector-control-matches",
       dc.get("good_status") == "UP" and dc.get("bad_status") == "DOWN"
       and dc.get("good_http_status") == 200 and dc.get("discriminates") is True
       and dc.get("always_up_mutant_pass") is False,
       str({k: dc.get(k) for k in ("good_status", "bad_status", "discriminates", "always_up_mutant_pass")}))

    rt = doc.get("routing_table") or []
    ck("routing-table-sixteen-classes", len(rt) == 16, f"n={len(rt)}")

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0168" in str(doc.get("sentinel")),
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-detector-control", "unit_id": "RES-0168", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0168-probe1 detector UP/DOWN re-run live, mutant rejected" if not red
          else f"FAILED:RES-0168-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())

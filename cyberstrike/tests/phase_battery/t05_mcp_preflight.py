#!/usr/bin/env python3
"""T-5 MCP preflight - t=0 dead-list with a firing detector control.

Proposal S8: at session start the config's MCP surface is probed once and a
dead-list is produced BEFORE any tool routing trusts it (audit CS-05/06: 24/34
servers outside any checklist; routing names unmounted tools).

What this test gates (deterministic, localhost-only):
  1. cyberstrike.json parses; mcp section entries are all type=remote with a
     127.0.0.1 URL inside the estate band 31100-31140 (exceptions allowed:
     9876, 18765) - the CONTEXT.new.md truth row ("35 servers, band 31100-31140,
     exceptions [9876, 18765]") must match the json.
  2. DETECTOR CONTROL (both-states): a TCP connect to a port that MUST be
     closed (31198 - inside the numeric neighborhood but unallocated) reports
     dead. Without this leg, an all-dead report could mean a broken probe
     (single-signal-verification rule 3: verify the detector can fire).
  3. Live TCP connect (250 ms timeout, connect-only, no data sent, loopback
     only - no Bolt/Okta/Databricks egress) to every configured server; the
     dead list is a HIT LOG FINDING for the operator, not a test failure -
     servers being down is a preflight RESULT, the test failing means the
     preflight could not produce one.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO, SUCCESS, FAILED, VerdictRecorder, read_text,
)

BAND = (31100, 31140)
ALLOWED_EXCEPTIONS = {9876, 18765}   # 18765 = basic-memory (wired 2026-09-22)
CONTROL_PORT = 31198          # must be closed - proves the probe can fire
EXPECTED_SERVER_COUNT = 35    # CONTEXT.new.md truth row


def tcp_alive(port: int, host: str = "127.0.0.1", timeout: float = 0.25) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    try:
        cfg = json.loads(read_text(REPO / "cyberstrike.json"))
    except Exception as e:
        rec.record("T-5", FAILED, reason=f"cyberstrike.json unparseable: {e}",
                   anchors=[REPO / "cyberstrike.json"])
        return FAILED

    mcp = cfg.get("mcp", {})
    findings: list[dict] = []
    for name, ent in sorted(mcp.items()):
        url = ent.get("url", "")
        p = urlparse(url)
        port = p.port or (443 if p.scheme == "https" else 80)
        host = p.hostname or ""
        in_band = BAND[0] <= port <= BAND[1] or port in ALLOWED_EXCEPTIONS
        loopback = host in ("127.0.0.1", "localhost", "::1")
        if not (ent.get("type") == "remote" and loopback and in_band):
            findings.append({"server": name, "issue": "outside-band-or-nonlocal",
                             "url": f"{p.scheme}://{host}:{port}"})
        alive = tcp_alive(port) if loopback else False
        rec.hit("T-5", "probe", server=name, port=port, alive=alive,
                in_band=in_band)
        if not alive:
            findings.append({"server": name, "issue": "dead-at-t0", "port": port})

    # bolt-lab rides the bolt: section (:3001) - probed, informational
    bolt = cfg.get("bolt", {}).get("bolt-lab", {})
    if bolt.get("url"):
        bp = urlparse(bolt["url"]).port or 80
        rec.hit("T-5", "probe", server="bolt-lab(bolt-section)", port=bp,
                alive=tcp_alive(bp), in_band=False,
                note="bolt: section, informational")

    control_fired = not tcp_alive(CONTROL_PORT)
    count_ok = len(mcp) == EXPECTED_SERVER_COUNT
    rec.hit("T-5", "detector_control", port=CONTROL_PORT,
            expected="closed", observed="closed" if control_fired else "OPEN",
            fires=control_fired)
    if not count_ok:
        rec.hit("T-5", "count_mismatch", configured=len(mcp),
                expected=EXPECTED_SERVER_COUNT)

    # Scope note: config-shape findings FAIL the gate; dead servers are hits.
    shape_failures = [f for f in findings if f["issue"] != "dead-at-t0"]
    gate_ok = control_fired and count_ok and not shape_failures
    rec.record("T-5", SUCCESS if gate_ok else FAILED,
               details={
                   "servers_configured": len(mcp),
                   "dead_at_t0": [f["server"] for f in findings
                                  if f["issue"] == "dead-at-t0"],
                   "shape_failures": shape_failures,
                   "detector_control_port": CONTROL_PORT,
                   "note": "dead-at-t0 is a preflight finding (hit-log), not "
                           "a gate failure; gate = detector fires + config "
                           "shape + truth-row count",
               },
               anchors=[REPO / "cyberstrike.json", REPO / "CONTEXT.new.md"],
               reason=None if gate_ok else "preflight could not produce a "
                                           "trustworthy dead-list")
    return SUCCESS if gate_ok else FAILED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args()
    with VerdictRecorder(meta={"test": "T-5"}) as rec:
        status = run(rec)
        print(f"T-5 {status}")
        return 0 if status == SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Probe 2: observe sockets from outside the client process (ss /proc/net/tcp)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ssrf_lib as L  # noqa: E402

LIB = HERE / "ssrf_lib.py"


def _spawn_fetch(url: str, timeout: float) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.Popen(
        [sys.executable, "-B", str(LIB), "fetch", url, str(timeout)],
        cwd=str(L.REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _watch(ip: str, port: int, proc: subprocess.Popen, window_s: float) -> dict:
    key = L.ipv4_proc_key(ip, port)
    ss_blob: list[str] = []
    proc_hits = 0
    deadline = time.time() + window_s
    while time.time() < deadline:
        keys = L.proc_tcp_keys()
        if key in keys:
            proc_hits += 1
        line = L.ss_lines(ip, port)
        if line.strip():
            ss_blob.append(line.strip())
        time.sleep(0.05)
    try:
        out, err = proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    return {
        "dst": f"{ip}:{port}",
        "proc_tcp_key": key,
        "proc_tcp_hits": proc_hits,
        "ss_samples": ss_blob[:8],
        "ss_saw": bool(ss_blob),
        "child_rc": proc.returncode,
        "child_stdout": (out or "")[:800],
        "child_stderr": (err or "")[:400],
        "observed": proc_hits > 0 or bool(ss_blob),
    }


def run() -> dict:
    with L.FixturePair() as fx:
        public = fx.url("/public")
        loopback = fx.url("/redir-loopback")
        metadata = fx.url("/redir-metadata")
        child_pub = _spawn_fetch(public, 2.0)
        pub_watch = _watch("127.0.0.1", fx.fx_port, child_pub, 1.2)
        child_lb = _spawn_fetch(loopback, 2.0)
        lb_watch = _watch("127.0.0.1", fx.sink_port, child_lb, 1.4)
        child_meta = _spawn_fetch(metadata, 1.4)
        meta_watch = _watch("169.254.169.254", 80, child_meta, 1.5)
        sink_hits = fx.state.snapshot()["sink_hits"]
    pub_ok = pub_watch["observed"] and L.PUBLIC_CANARY in str(
        pub_watch.get("child_stdout") or ""
    )
    loopback_observed = bool(lb_watch["observed"] or sink_hits > 0)
    metadata_observed = bool(meta_watch["observed"])
    if not pub_ok:
        meta_verdict = "NOT-CHECKED"
        lb_verdict = "NOT-CHECKED"
    else:
        lb_verdict = "CONFIRMED" if loopback_observed else "REFUTED"
        if metadata_observed:
            meta_verdict = "CONFIRMED"
        elif loopback_observed:
            meta_verdict = "PARTIAL"
        else:
            meta_verdict = "REFUTED"
    passed = pub_ok and loopback_observed
    return {
        "probe": "probe2-socket-observe",
        "unit_id": "ADV-0032",
        "public_control_observed": pub_ok,
        "loopback_sink_observed": loopback_observed,
        "metadata_syn_observed": metadata_observed,
        "sink_hits": sink_hits,
        "watch_public": pub_watch,
        "watch_loopback": lb_watch,
        "watch_metadata": meta_watch,
        "targets": [
            {"id": "socket:loopback-sink-after-redirect", "verdict": lb_verdict},
            {
                "id": "socket:link-local-metadata-after-redirect",
                "verdict": meta_verdict,
            },
        ],
        "pass": passed,
        "third_party_requests": 0,
        "oracle": "ss and/or /proc/net/tcp sampled in the parent, not the urllib client",
    }


def main() -> int:
    payload = run()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:ADV-0032-probe2 socket observation")
        return 1
    print(
        "SUCCESS:ADV-0032-probe2 out-of-process sockets; "
        f"loopback={payload['loopback_sink_observed']} "
        f"metadata={payload['metadata_syn_observed']} "
        "public control observed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

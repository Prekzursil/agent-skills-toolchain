#!/usr/bin/env python3
"""Probe 1: point each fetch stage at the local fixture; record redirect chase."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ssrf_lib as L  # noqa: E402


def run() -> dict:
    rows: list[dict] = []
    with L.FixturePair() as fx:
        public = fx.url("/public")
        loopback = fx.url("/redir-loopback")
        metadata = fx.url("/redir-metadata")
        for stage in L.STAGES:
            fetch = stage["fetch"]
            ctrl = fetch(public)
            public_ok = bool(ctrl.get("ok")) and L.PUBLIC_CANARY in str(ctrl.get("body") or "")
            sink_before = fx.state.snapshot()["sink_hits"]
            atk = fetch(loopback)
            sink_after = fx.state.snapshot()["sink_hits"]
            chased_loopback = sink_after > sink_before or L.SINK_CANARY in str(
                atk.get("body") or ""
            )
            meta = fetch(metadata)
            meta_blob = " ".join(
                [
                    str(meta.get("error") or ""),
                    str(meta.get("final_url") or ""),
                    str(meta.get("body") or ""),
                ]
            )
            chased_meta = (
                "169.254.169.254" in meta_blob
                or bool(meta.get("imds_body_redacted"))
                or "[REDACTED-LINK-LOCAL-IMDS]" in meta_blob
            )
            if chased_loopback or chased_meta:
                verdict = "CONFIRMED"
            elif not public_ok:
                verdict = "NOT-CHECKED"
            else:
                verdict = "REFUTED"
            rows.append(
                {
                    "id": stage["id"],
                    "path": stage["path"],
                    "verdict": verdict,
                    "public_ok": public_ok,
                    "public": ctrl,
                    "loopback_chase": chased_loopback,
                    "loopback": atk,
                    "metadata_chase": chased_meta,
                    "metadata": meta,
                    "sink_delta": sink_after - sink_before,
                }
            )
        guard_before = fx.state.snapshot()["sink_hits"]
        g_pub = L.guarded_fetch(public)
        g_lb = L.guarded_fetch(loopback)
        guard_after = fx.state.snapshot()["sink_hits"]
        guard_public_ok = bool(g_pub.get("ok")) and L.PUBLIC_CANARY in str(
            g_pub.get("body") or ""
        )
        guard_silent = guard_after == guard_before
        spdx = L.inspect_spdx_controls()
        census = L.census_urlopen(L.REPO / "tools")
    public_all = all(r["public_ok"] for r in rows)
    any_ssrf = any(r["verdict"] == "CONFIRMED" for r in rows)
    detector_ok = public_all and any_ssrf and guard_public_ok and guard_silent
    return {
        "probe": "probe1-redirect-follow",
        "unit_id": "ADV-0032",
        "public_control_all_stages": public_all,
        "guard_public_ok": guard_public_ok,
        "guard_silent_on_loopback_redirect": guard_silent,
        "guard_loopback": g_lb,
        "stages": rows,
        "spdx_controls": spdx,
        "tools_urlopen_census": census,
        "detector_both_states": detector_ok,
        "pass": detector_ok,
        "third_party_requests": 0,
    }


def main() -> int:
    payload = run()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:ADV-0032-probe1 redirect-follow control or detector")
        return 1
    n_conf = sum(1 for r in payload["stages"] if r["verdict"] == "CONFIRMED")
    print(
        "SUCCESS:ADV-0032-probe1 fixture redirect follow; "
        f"public control ok; {n_conf} stages chased private/loopback; "
        "guarded comparator silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

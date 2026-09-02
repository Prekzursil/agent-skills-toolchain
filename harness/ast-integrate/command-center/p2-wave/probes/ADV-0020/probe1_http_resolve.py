#!/usr/bin/env python3
"""Probe 1: HTTP-resolve every cited URL; record status, final URL, quote containment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib_adv0020 import dump_json, live_probe  # noqa: E402

OUT = HERE / "probe1-live.json"


def main() -> int:
    result = live_probe()
    public = dict(result)
    dump_json(OUT, public)
    n = result["n_corpus"]
    print(f"n_corpus={n} unique_urls={result['n_unique_urls']} controls={result['n_controls']}")
    print(
        f"http_200={result['n_http_200']} containing={result['n_live_containing']} "
        f"mismatch={result['n_live_mismatch']} unquoted={result['n_live_unquoted']} "
        f"dead={result['n_dead_or_error']} resolve_rate={result['resolve_rate']}"
    )
    print(f"all_healthy_including_controls={result['all_healthy_including_controls']}")
    live_ctrl = next(r for r in result["rows"] if r["id"] == "CTRL-LIVE-CONTAINING")
    dead_ctrl = next(r for r in result["rows"] if r["id"] == "CTRL-DEAD")
    mis_ctrl = next(r for r in result["rows"] if r["id"] == "CTRL-LIVE-MISMATCH")
    print(
        f"CTRL-LIVE status={live_ctrl['http_status']} "
        f"quote_in_body={live_ctrl['quote_in_live_body']} kind={live_ctrl['kind']}"
    )
    print(
        f"CTRL-DEAD status={dead_ctrl['http_status']} "
        f"quote_in_body={dead_ctrl['quote_in_live_body']} kind={dead_ctrl['kind']}"
    )
    print(
        f"CTRL-MISMATCH status={mis_ctrl['http_status']} "
        f"quote_in_body={mis_ctrl['quote_in_live_body']} kind={mis_ctrl['kind']}"
    )
    summary = {
        "probe": result["probe"],
        "unit_id": result["unit_id"],
        "n_corpus": result["n_corpus"],
        "n_unique_urls": result["n_unique_urls"],
        "n_http_200": result["n_http_200"],
        "n_live_containing": result["n_live_containing"],
        "n_live_mismatch": result["n_live_mismatch"],
        "n_dead_or_error": result["n_dead_or_error"],
        "resolve_rate": result["resolve_rate"],
        "all_healthy_including_controls": result["all_healthy_including_controls"],
        "live_control_kind": live_ctrl["kind"],
        "dead_control_kind": dead_ctrl["kind"],
        "mismatch_control_kind": mis_ctrl["kind"],
        "pass": (
            live_ctrl["kind"] == "live-containing"
            and dead_ctrl["kind"] == "dead-or-error"
            and mis_ctrl["kind"] == "live-mismatch"
            and not result["all_healthy_including_controls"]
        ),
    }
    print(json.dumps(summary, sort_keys=True, default=str))
    if live_ctrl["kind"] != "live-containing":
        print("FAILED:ADV-0020-probe1 live-control-not-containing")
        return 1
    if dead_ctrl["kind"] != "dead-or-error":
        print("FAILED:ADV-0020-probe1 dead-control-not-flagged")
        return 1
    if mis_ctrl["kind"] != "live-mismatch":
        print("FAILED:ADV-0020-probe1 mismatch-control-not-detected")
        return 1
    if result["all_healthy_including_controls"]:
        print("FAILED:ADV-0020-probe1 100-percent-healthy-bot-filter-suspect")
        return 1
    print("SUCCESS:ADV-0020-probe1 live HTTP resolve with planted controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

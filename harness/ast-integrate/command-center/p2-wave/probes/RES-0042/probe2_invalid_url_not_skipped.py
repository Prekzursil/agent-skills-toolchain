#!/usr/bin/env python3
"""Probe 2: deliberately invalid URL is UNRESOLVABLE, never skipped.

Mechanically different from probe 1: this probe does not re-resolve the
catalog fleet. It only checks the planted .invalid URL against the honest
resolver, the naive skipper mutant, and the live artifact control row.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from mappings import INVALID_URL, OUT_REL, SENTINEL, UNIT  # noqa: E402
from resolve import is_planted_invalid, naive_skip_invalid, resolve_url  # noqa: E402
from schema_local import domain  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not is_planted_invalid(INVALID_URL):
        return fail("planted URL not classified as invalid")

    honest = resolve_url(INVALID_URL)
    print(
        "honest skipped={sk} resolvable={rs} status={st} http_status={hs} error={er}".format(
            sk=honest.get("skipped"),
            rs=honest.get("resolvable"),
            st=honest.get("status"),
            hs=honest.get("http_status"),
            er=honest.get("error"),
        )
    )
    if honest.get("skipped") is True:
        return fail("honest resolver skipped the invalid URL")
    if honest.get("resolvable") is True:
        return fail("invalid URL reported resolvable")
    if str(honest.get("status") or "") != "UNRESOLVABLE":
        return fail(f"status={honest.get('status')} want=UNRESOLVABLE")
    if int(honest.get("http_status") or 0) != 0:
        return fail(f"http_status={honest.get('http_status')} want=0")

    live = "https://github.com/github/github-mcp-server"
    remaining = naive_skip_invalid([INVALID_URL, live])
    print(f"naive remaining={remaining}")
    if INVALID_URL in remaining:
        return fail("naive skipper did not drop the planted invalid URL")
    if live not in remaining:
        return fail("naive skipper dropped a live URL (control silent)")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    ctrl = domain(doc).get("control_invalid_url") or {}
    if ctrl.get("skipped") is True:
        return fail("artifact skipped the invalid URL")
    if ctrl.get("status") != "UNRESOLVABLE" or ctrl.get("resolvable") is True:
        return fail(f"artifact control {ctrl.get('status')}")
    if ctrl.get("url") != INVALID_URL:
        return fail("artifact control URL mismatch")
    for key in ("final_url", "http_status", "last_release_date", "snapshot_timestamp"):
        if ctrl.get(key) in (None, ""):
            return fail(f"artifact control missing {key}")
    # Artifact must not omit the control the way the naive skipper would.
    skipped_ids = [
        r.get("server_id")
        for r in (domain(doc).get("servers") or [])
        if isinstance(r, dict) and r.get("server_id") == "CONTROL-INVALID-URL"
    ]
    print(f"control_in_servers_array={bool(skipped_ids)} (optional)")
    print(
        f"SUCCESS:{UNIT}-probe2 invalid-url UNRESOLVABLE not-skipped "
        f"naive-dropped={ctrl.get('naive_skipper_dropped_it')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

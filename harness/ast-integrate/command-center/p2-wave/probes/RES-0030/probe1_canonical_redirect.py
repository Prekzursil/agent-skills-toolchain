#!/usr/bin/env python3
"""Named probe 1: live canonical URL + redirect chain vs the research artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from canonical import resolve_canonical  # noqa: E402
from constants import (  # noqa: E402
    CANONICAL_FULL_NAME,
    CANONICAL_HTML,
    OUTPUT_REL,
    REPO,
    SENTINEL,
    SHORT_SENTINEL,
    UNIT_ID,
)

ART = REPO / OUTPUT_REL


def main() -> int:
    live = resolve_canonical()
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0030-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:RES-0030-probe1 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:RES-0030-probe1 not an object")
        return 1
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:RES-0030-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0030-probe1 self-declared", doc.get("state"))
        return 1
    if SENTINEL not in text or SHORT_SENTINEL not in text:
        print("FAILED:RES-0030-probe1 sentinel-absent")
        return 1
    art_url = str(doc.get("canonical_repo_url") or "").rstrip("/")
    if art_url != CANONICAL_HTML:
        print(f"FAILED:RES-0030-probe1 canonical_repo_url={art_url}")
        return 1
    if live["canonical_repo_url"] != art_url:
        print("FAILED:RES-0030-probe1 live/artifact canonical mismatch")
        return 1
    chain = doc.get("redirect_chain") or doc.get("html_redirect_chain") or []
    if not isinstance(chain, list) or len(chain) < 2:
        print("FAILED:RES-0030-probe1 redirect_chain missing")
        return 1
    hop0, hop1 = chain[0], chain[1]
    if hop0.get("status") != 301 or "aaif-goose/goose" not in str(hop0.get("location") or hop0.get("to") or ""):
        print(f"FAILED:RES-0030-probe1 hop0 not 301 to canonical: {hop0}")
        return 1
    if hop1.get("status") != 200:
        print(f"FAILED:RES-0030-probe1 hop1 not 200: {hop1}")
        return 1
    live0 = live["html_redirect_chain"][0]
    live1 = live["html_redirect_chain"][1]
    if live0.get("status") != 301 or live1.get("status") != 200:
        print("FAILED:RES-0030-probe1 live html chain drifted")
        return 1
    api_chain = doc.get("api_redirect_chain") or []
    if not api_chain or api_chain[0].get("status") != 301:
        print(f"FAILED:RES-0030-probe1 api_redirect_chain missing 301: {api_chain[:1]}")
        return 1
    if str(846698999) not in str(api_chain[0].get("location") or ""):
        print("FAILED:RES-0030-probe1 api 301 not numeric-id")
        return 1
    if live["canonical_full_name"] != CANONICAL_FULL_NAME:
        print("FAILED:RES-0030-probe1 live full_name")
        return 1
    ctrl = live.get("control") or {}
    if not ctrl.get("canonical_html_no_location") or ctrl.get("canonical_html_status") != 200:
        print(f"FAILED:RES-0030-probe1 canonical control {ctrl}")
        return 1

    out = {
        "probe": "probe1-canonical-redirect",
        "unit_id": UNIT_ID,
        "pass": True,
        "canonical_repo_url": CANONICAL_HTML,
        "html_redirect_chain": live["html_redirect_chain"],
        "api_redirect_chain": live["api_redirect_chain"],
        "control_canonical_no_redirect": True,
        "artifact_matches_live": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        f"canonical={CANONICAL_HTML} html_301={live0.get('location')} "
        f"api_301={live['api_redirect_chain'][0].get('location')}"
    )
    print(f"SUCCESS:{UNIT_ID}-probe1 canonical URL and redirect chain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

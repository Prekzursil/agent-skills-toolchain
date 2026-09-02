#!/usr/bin/env python3
"""Probe 1: every measured-fact claim has two independent rails.

Rails must carry permalink, fetch_timestamp, HTTP status, and sha256 of the
captured bytes. A one-rail claim is E3 and must not be cited as measured fact.
Quoted spans must occur in the captured bytes. Live sha256 must match the
artifact. The catalog completion sentinel must be present.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0106.json"
SENTINEL = (
    "SUCCESS:RES-0106 in the receipt AND a specified never-selected detector "
    "with its data source and its stated false-alarm case"
)
RAIL_FIELDS = ("permalink", "fetch_timestamp", "http_status", "sha256")
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:RES-0106-probe1 {msg}")
    return 1


def quote_in_capture(raw: bytes, quoted: str) -> bool:
    if quoted.encode("utf-8") in raw:
        return True
    try:
        return quoted in raw.decode("utf-8")
    except UnicodeDecodeError:
        return False


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text or "SUCCESS:RES-0106" not in text:
        return fail("sentinel absent")
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 3:
        return fail("claims missing")

    measured = 0
    e3 = 0
    for claim in claims:
        cid = claim.get("id")
        rails = claim.get("rails") or []
        if not isinstance(rails, list):
            return fail(f"{cid} rails not a list")
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        for i, rail in enumerate(rails):
            for field in RAIL_FIELDS:
                if not rail.get(field) and rail.get(field) != 0:
                    return fail(f"{cid} rail[{i}] missing {field}")
            if int(rail.get("http_status") or 0) != 200:
                return fail(f"{cid} rail[{i}] http_status={rail.get('http_status')}")
            cap_rel = str(rail.get("capture_file") or "")
            cap = REPO / cap_rel
            if not cap.is_file():
                return fail(f"{cid} rail[{i}] capture missing {cap_rel}")
            raw = cap.read_bytes()
            live = hashlib.sha256(raw).hexdigest()
            if live != str(rail.get("sha256")):
                return fail(f"{cid} rail[{i}] sha256 mismatch")
            quoted = str(rail.get("quoted_span") or "")
            if len(quoted) < 8:
                return fail(f"{cid} rail[{i}] quoted_span too short")
            if not quote_in_capture(raw, quoted):
                return fail(f"{cid} rail[{i}] quoted_span absent from capture")
        grade = str(claim.get("grade") or "")
        cited = bool(claim.get("cite_as_measured_fact"))
        if cited:
            if grade == "E3" or len(rails) < 2:
                return fail(f"{cid} cited as measured fact without two rails")
            if "structured-api" not in kinds or "prose" not in kinds:
                return fail(f"{cid} rails not API+prose")
            if str(claim.get("verdict")) != "CONFIRMED":
                return fail(f"{cid} cited as fact but verdict!={claim.get('verdict')}")
            measured += 1
        else:
            if grade == "E3":
                if len(rails) >= 2:
                    return fail(f"{cid} marked E3 but has two rails")
                e3 += 1
            if cited:
                return fail(f"{cid} cite_as_measured_fact true in non-cited branch")

    det = doc.get("never_selected_detector") or {}
    if not isinstance(det, dict) or not det.get("id"):
        return fail("never_selected_detector missing")
    fa = det.get("false_alarm_case") or {}
    if str(fa.get("capability_id") or "") != "debug.dump_internal_state":
        return fail("false-alarm capability_id missing")
    reads = json.dumps(det)
    if "catalog" not in reads.lower() or "golden" not in reads.lower():
        return fail("detector data source incomplete")
    if "when_it_runs" not in det or not det.get("when_it_runs"):
        return fail("when_it_runs missing")
    for pid in det.get("prior_art_claim_ids") or []:
        hit = next((c for c in claims if c.get("id") == pid), None)
        if hit is None:
            return fail(f"prior_art {pid} missing")
        if not hit.get("cite_as_measured_fact"):
            return fail(f"prior_art {pid} is not measured fact")

    print(
        f"measured_fact_claims={measured} e3_quarantined={e3} "
        f"detector={det.get('id')} false_alarm={fa.get('capability_id')}"
    )
    print("SUCCESS:RES-0106-probe1 two-rail evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

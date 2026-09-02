#!/usr/bin/env python3
"""Named probe 1: re-verify one real Sigstore signature end to end.

Does not trust the research artifact's boolean; it re-runs ECDSA over DSSE PAE
against the frozen wheel and provenance, then checks the artifact transcript
matches those live measurements and contains the catalog sentinel.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from verify_signature import (  # noqa: E402
    EXPECTED_IDENTITY,
    EXPECTED_ISSUER,
    EXPECTED_LOG_INDEX,
    EXPECTED_WHEEL_SHA256,
    verify_transcript,
)

ART = REPO / "command-center/research/RES-0048.json"
SENTINEL = (
    "SUCCESS:RES-0048 in the receipt AND one end-to-end verified signature "
    "transcript plus a named list of what it does not prevent"
)


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:RES-0048-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    live = verify_transcript()
    print(
        f"live e2e_ok={live['e2e_ok']} dsse={live['dsse']['verified']} "
        f"wheel={live['artifact']['sha256'][:16]} "
        f"identity={live['certificate']['san_uri']!s:.80} "
        f"logIndex={live['rekor']['log_index']}"
    )
    if not live["e2e_ok"]:
        return fail("live transcript not e2e_ok", live["checks"])
    if live["artifact"]["sha256"] != EXPECTED_WHEEL_SHA256:
        return fail("wheel digest drift", live["artifact"])
    if live["certificate"]["san_uri"] != EXPECTED_IDENTITY:
        return fail("identity drift", live["certificate"])
    if live["certificate"]["oidc_issuer"] != EXPECTED_ISSUER:
        return fail("issuer drift", live["certificate"])
    if live["rekor"]["log_index"] != EXPECTED_LOG_INDEX:
        return fail("rekor index drift", live["rekor"])
    if live["statement"]["predicate"] is not None:
        return fail("predicate unexpectedly non-null", live["statement"])

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    tr = doc.get("signature_transcript") or {}
    if tr.get("e2e_ok") is not True:
        return fail("artifact transcript e2e_ok is not true")
    if (tr.get("artifact") or {}).get("sha256") != live["artifact"]["sha256"]:
        return fail("artifact transcript wheel sha256 mismatch")
    if (tr.get("dsse") or {}).get("verified") is not True:
        return fail("artifact transcript dsse not verified")
    if (tr.get("certificate") or {}).get("san_uri") != EXPECTED_IDENTITY:
        return fail("artifact transcript identity mismatch")
    if (tr.get("rekor") or {}).get("payload_hash") != live["rekor"]["payload_hash"]:
        return fail("artifact transcript rekor payload hash mismatch")
    attacks = doc.get("does_not_prevent") or []
    if len(attacks) < 2:
        return fail("artifact missing named does_not_prevent list")
    print("transcript-match=True attacks_named=" + str(len(attacks)))
    print("SUCCESS:RES-0048-probe1 end-to-end verified signature transcript")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

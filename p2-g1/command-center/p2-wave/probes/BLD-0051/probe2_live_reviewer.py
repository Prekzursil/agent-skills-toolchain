#!/usr/bin/env python3
"""Probe 2: independent reviewer of the live shipped receipt.

Greps for the synthetic canary body and for unexpected high-entropy strings.
Does not print credential values. Confirms live-path markers and safety flags.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402

ART = REPO / C.OUT_REL
HEX64 = re.compile(r"\b[a-f0-9]{64}\b")
MARKER = re.compile(r"\[REDACTED:[^\]]+\]")
TOKENISH = re.compile(r"[A-Za-z0-9_\-+=]{24,}")


def entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {ch: s.count(ch) / len(s) for ch in set(s)}
    return -sum(p * math.log2(p) for p in freq.values())


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0051-probe2 receipt missing")
        return 1
    raw = ART.read_bytes().replace(b"\r\n", b"\n")
    text = raw.decode("utf-8")
    if C.CANARY in text:
        print("FAILED:BLD-0051-probe2 canary body in receipt")
        return 1
    want = hashlib.sha256(C.CANARY.encode("utf-8")).hexdigest()
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0051-probe2 self-declared {doc.get('state')}")
        return 1
    if C.SENTINEL not in text:
        print("FAILED:BLD-0051-probe2 sentinel missing")
        return 1
    stored = (doc.get("redaction") or {}).get("canary_sha256")
    if stored != want:
        print("FAILED:BLD-0051-probe2 canary sha256 mismatch")
        return 1
    proof = doc.get("live_path_proof") or {}
    if proof.get("redactor_on") is not True or proof.get("canary_body_absent") is not True:
        print("FAILED:BLD-0051-probe2 live-path flags")
        return 1
    if not MARKER.search(text):
        print("FAILED:BLD-0051-probe2 no redaction markers in receipt")
        return 1
    safety = doc.get("safety") or {}
    if safety.get("credential_values_written") is not False:
        print("FAILED:BLD-0051-probe2 safety.credential_values_written")
        return 1
    if safety.get("rotation_performed") is not False:
        print("FAILED:BLD-0051-probe2 rotation was claimed")
        return 1
    if len(doc.get("writers") or []) < 7:
        print("FAILED:BLD-0051-probe2 writers short")
        return 1
    if len(doc.get("egress_map") or []) < 7:
        print("FAILED:BLD-0051-probe2 egress_map short")
        return 1
    if len(doc.get("credential_sources") or []) < 5:
        print("FAILED:BLD-0051-probe2 sources short")
        return 1
    for name in C.ENV_NAMES:
        val = os.environ.get(name)
        if val and len(val) >= 12 and val in text:
            print(f"FAILED:BLD-0051-probe2 env value of {name} in receipt")
            return 1
    suspicious = []
    for tok in TOKENISH.findall(text):
        if HEX64.fullmatch(tok):
            continue
        if tok.startswith("[REDACTED"):
            continue
        if tok == C.CANARY_ID or tok.startswith("BLD0051"):
            continue
        if (
            entropy(tok) >= 4.5
            and any(ch.isupper() for ch in tok)
            and any(ch.islower() for ch in tok)
            and any(ch.isdigit() for ch in tok)
        ):
            suspicious.append(tok[:12] + "…")
    if suspicious:
        print("FAILED:BLD-0051-probe2 unexpected high-entropy strings")
        print(json.dumps({"count": len(suspicious), "prefixes": suspicious[:8]}))
        return 1
    print(
        json.dumps(
            {
                "canary_absent": True,
                "markers_present": True,
                "live_redactor_on": True,
                "sha_ok": True,
                "writers": len(doc["writers"]),
                "sources": len(doc["credential_sources"]),
                "egress_cells": len(doc["egress_map"]),
                "high_entropy_unexpected": 0,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0051-probe2 live receipt reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

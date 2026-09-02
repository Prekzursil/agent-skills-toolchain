#!/usr/bin/env python3
"""Probe 1: fabricated-expertise fixture must fail the evidence bar.

Mechanism: evidence_bar() over bound claims. Scores come from the pointed
probe file; the assertion string is ignored. A good claim on the same tag
must PASS so a universal-fail bar cannot satisfy this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import expertise as E  # noqa: E402

CLAIMS = HERE / "fixtures" / "claims"


def load_claim(name: str) -> dict:
    return E.bind_live_hashes(E.load_json(CLAIMS / name), E.REPO)


def main() -> int:
    good = load_claim("good-cryptographer.json")
    fabricated = load_claim("fabricated.json")
    below = load_claim("below-baseline.json")
    confident = load_claim("unanswerable-confident.json")
    mismatch = load_claim("hash-mismatch.json")
    tls = load_claim("tls-only.json")

    g = E.evidence_bar(good, "cryptography")
    f = E.evidence_bar(fabricated, "cryptography")
    b = E.evidence_bar(below, "cryptography")
    c = E.evidence_bar(confident, "cryptography")
    h = E.evidence_bar(mismatch, "cryptography")
    t_crypto = E.evidence_bar(tls, "cryptography")
    t_tls = E.evidence_bar(tls, "tls")
    unknown = E.evidence_bar(good, "universal-expert")

    print(
        json.dumps(
            {
                "good": {"pass": g["pass"], "reason": g["reason"], "margin": g.get("margin")},
                "fabricated": {"pass": f["pass"], "reason": f["reason"]},
                "below_baseline": {"pass": b["pass"], "reason": b["reason"]},
                "unanswerable_confident": {"pass": c["pass"], "reason": c["reason"]},
                "hash_mismatch": {"pass": h["pass"], "reason": h["reason"]},
                "tls_on_cryptography": {"pass": t_crypto["pass"], "reason": t_crypto["reason"]},
                "tls_on_tls": {"pass": t_tls["pass"], "reason": t_tls["reason"]},
                "unknown_tag": {"pass": unknown["pass"], "reason": unknown["reason"]},
            },
            sort_keys=True,
        )
    )

    fail = False
    if g["pass"] is not True or int(g.get("margin") or 0) <= 0:
        print(f"FAILED:CNL-0015-probe1 good claim did not pass bar: {g}")
        fail = True
    if f["pass"] is not False or f["reason"] not in {"self-assertion-only", "no-evidence"}:
        print(f"FAILED:CNL-0015-probe1 fabricated did not fail bar: {f}")
        fail = True
    if b["pass"] is not False or b["reason"] not in {"at-or-below-baseline", "all-evidence-rejected"}:
        print(f"FAILED:CNL-0015-probe1 below-baseline did not fail: {b}")
        fail = True
    if c["pass"] is not False or c["reason"] not in {"unanswerable-not-idk", "all-evidence-rejected"}:
        print(f"FAILED:CNL-0015-probe1 unanswerable-confident did not fail: {c}")
        fail = True
    if h["pass"] is not False or h["reason"] not in {"hash-mismatch", "all-evidence-rejected"}:
        print(f"FAILED:CNL-0015-probe1 hash-mismatch did not fail: {h}")
        fail = True
    if t_crypto["pass"] is not False or t_crypto["reason"] != "tag-not-claimed":
        print(f"FAILED:CNL-0015-probe1 tls claim weighted as cryptography: {t_crypto}")
        fail = True
    if t_tls["pass"] is not True:
        print(f"FAILED:CNL-0015-probe1 tls claim failed its own tag: {t_tls}")
        fail = True
    if unknown["pass"] is not False or unknown["reason"] != "unknown-tag":
        print(f"FAILED:CNL-0015-probe1 unknown tag not fail-closed: {unknown}")
        fail = True
    if g.get("assertion_is_load_bearing") is True:
        print("FAILED:CNL-0015-probe1 assertion became load-bearing")
        fail = True

    # Vacuity: stripping evidence from the good claim must flip PASS -> FAIL.
    stripped = json.loads(json.dumps(good))
    stripped["evidence"] = []
    s = E.evidence_bar(stripped, "cryptography")
    print(f"stripped_good pass={s['pass']} reason={s['reason']}")
    if s["pass"] is not False:
        print("FAILED:CNL-0015-probe1 stripped good claim still passed")
        fail = True

    if fail:
        print("FAILED:CNL-0015-probe1 fabricated-expertise evidence bar")
        return 1
    print(
        "fabricated_fail=True good_pass=True below_fail=True "
        "confident_fail=True hash_fail=True tls_not_crypto=True"
    )
    print("SUCCESS:CNL-0015-probe1 fabricated-expertise fails the evidence bar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

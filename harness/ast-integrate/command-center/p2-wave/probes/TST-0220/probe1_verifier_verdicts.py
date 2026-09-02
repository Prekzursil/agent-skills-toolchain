#!/usr/bin/env python3
"""Probe 1: live marketplace.sign.verify_package per-case verdicts.

Rejects unsigned, untrusted-key, and content-tampered; accepts the signed twin.
Naive mutants accept the three bad cases so the honest path is shown live.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import (  # noqa: E402
    EXPECTED,
    build_fixtures,
    honest_verdicts,
    naive_matrix,
    public_meta,
)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAILED:TST-0220-probe1 {msg}")


def main() -> int:
    fx = build_fixtures()
    honest = honest_verdicts(fx)
    naive = naive_matrix(fx)
    meta = public_meta(fx)

    _need(meta["ids_distinct"], "trusted and untrusted key ids collided")
    _need(meta["payload_sha256"] != meta["tampered_sha256"], "tamper did not change digest")

    for name, want in EXPECTED.items():
        got = honest[name]
        _need(
            got["accepted"] is want["accepted"],
            f"{name} accepted={got['accepted']} want={want['accepted']}",
        )
        _need(
            got["reason"] == want["reason"],
            f"{name} reason={got['reason']!r} want={want['reason']!r}",
        )

    _need(honest["valid_twin"]["accepted"] is True, "both-states: valid twin must verify")
    _need(honest["unsigned"]["reason"] == "unsigned", "unsigned not distinguished")
    _need(honest["untrusted_key"]["reason"] == "untrusted-key", "untrusted not distinguished")
    _need(
        honest["content_tampered"]["reason"] == "content-tampered",
        "mutation control: flipped byte not content-tampered",
    )
    _need(
        honest["content_tampered"]["payload_sha256"] != honest["valid_twin"]["payload_sha256"],
        "tampered payload digest matches twin",
    )
    _need(
        honest["content_tampered"]["record_digest"] == honest["valid_twin"]["record_digest"],
        "tamper case must keep the original signature digest",
    )
    _need(
        honest["untrusted_key"]["record_key_id"] == meta["untrusted_id"],
        "untrusted case not signed by the untrusted key id",
    )
    _need(
        honest["valid_twin"]["record_key_id"] == meta["trusted_id"],
        "valid twin not signed by trusted key id",
    )

    _need(naive["unsigned_valid_by_absence"]["accepted"] is True, "naive unsigned did not fire")
    _need(naive["untrusted_ignore_trust"]["accepted"] is True, "naive untrusted did not fire")
    _need(naive["tampered_skip_payload"]["accepted"] is True, "naive tampered did not fire")
    _need(
        naive["valid_twin_still_accepted_by_unsigned_naive"]["accepted"] is True,
        "naive broke the good state",
    )

    doc = {
        "probe": "probe1-verifier-verdicts",
        "unit_id": "TST-0220",
        "pass": True,
        "implementation": "tools/marketplace/sign.py:verify_package",
        "meta": meta,
        "honest": honest,
        "naive": {
            "unsigned_accepted": naive["unsigned_valid_by_absence"]["accepted"],
            "untrusted_accepted": naive["untrusted_ignore_trust"]["accepted"],
            "tampered_accepted": naive["tampered_skip_payload"]["accepted"],
        },
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        "SUCCESS:TST-0220-probe1 verifier rejects unsigned/untrusted/tampered; "
        "valid twin accepted; naive mutants fire"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 1 (IMP-0063): both catalog evidence signals in ONE run.

(1) signature verification succeeds against the public key for a genuine artifact
(2) verification FAILS after a single byte of that artifact is flipped
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HARNESS = REPO / "tools" / "plugin" / "tests"
sys.path.insert(0, str(HARNESS))
import harness as H  # noqa: E402


def main() -> int:
    result = H.two_signal_same_run()
    print(json.dumps(result, sort_keys=True))
    if not result.get("same_run"):
        print("FAILED:IMP-0063-probe1 signals were not observed in the same run")
        return 1
    if not result.get("genuine_ok"):
        print("FAILED:IMP-0063-probe1 genuine artifact did not verify")
        return 1
    if not result.get("tamper_fails"):
        print("FAILED:IMP-0063-probe1 tampered artifact did not fail verification")
        return 1
    if not result.get("digest_changed"):
        print("FAILED:IMP-0063-probe1 live digest unchanged after byte flip")
        return 1
    if not result.get("subject_unchanged"):
        print("FAILED:IMP-0063-probe1 attested subject moved; tamper check is not live")
        return 1
    if result.get("private_key_persisted_outside_tmpdir"):
        print("FAILED:IMP-0063-probe1 owner test key escaped the tempdir")
        return 1
    print(
        "genuine=VERIFIED tamper=TAMPERED_ARTIFACT "
        f"keyid={result.get('keyid')} commit={result.get('commit')}"
    )
    print("SUCCESS:IMP-0063-probe1 genuine-and-tamper same-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

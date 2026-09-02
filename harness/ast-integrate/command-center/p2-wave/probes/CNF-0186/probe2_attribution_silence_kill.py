#!/usr/bin/env python3
"""Probe 2: attribution from stored fingerprint bytes, silence≠green, kill-mid-run."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenarios as S  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0186-p2a-") as tmp:
        attr = S.scenario_attribution(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="cnf0186-p2s-") as tmp:
        silence = S.scenario_silence(Path(tmp))
    with tempfile.TemporaryDirectory(prefix="cnf0186-p2k-") as tmp:
        kill = S.scenario_kill_mid_run(Path(tmp))
    print(
        "attribution_from_stored={from_stored_bytes} "
        "planted_fingerprint_honored={planted_stored_fingerprint_honored}".format(**attr)
    )
    print(
        "silence_ok={silence_ok} missing_run_ok={missing_run_ok}".format(**silence)
    )
    print(
        "killed={killed} sleepy_not_success={sleepy_not_success} "
        "overall_failed={overall_failed} run_complete={run_complete}".format(**kill)
    )
    if not attr["pass"]:
        print("FAILED:CNF-0186-probe2 attribution (fingerprint reconstructed or unused)")
        return 1
    if not silence["pass"]:
        print("FAILED:CNF-0186-probe2 silence treated as green")
        return 1
    if not kill["pass"]:
        print("FAILED:CNF-0186-probe2 kill-mid-run did not fail the in-flight package")
        return 1
    print("SUCCESS:CNF-0186-probe2 attribution, silence, kill-mid-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

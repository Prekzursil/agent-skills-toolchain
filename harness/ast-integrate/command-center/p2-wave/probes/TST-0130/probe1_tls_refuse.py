#!/usr/bin/env python3
"""Probe 1: live TLS refuse + both-states valid cert + independent connection capture.

Evidence signal (a): client exit classification tls-handshake-failure.
Evidence signal (b): socket.create_connection capture — no http:// and no port 80.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from matrix import run_tls_matrix  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst-0130-p1-") as tmp:
        report = run_tls_matrix(Path(tmp))
    cases = report["cases"]
    needed = ("wrong_cn", "expired", "valid_both_states", "unverified_mutant_would_pass")
    failed = [name for name in needed if not cases[name]["pass"]]
    print(
        json.dumps(
            {
                "wrong_cn_class": cases["wrong_cn"]["classification"],
                "wrong_cn_exit": cases["wrong_cn"]["exit_code"],
                "expired_class": cases["expired"]["classification"],
                "expired_exit": cases["expired"]["exit_code"],
                "valid_class": cases["valid_both_states"]["classification"],
                "valid_exit": cases["valid_both_states"]["exit_code"],
                "wrong_cn_capture": cases["wrong_cn"]["capture"],
                "expired_capture": cases["expired"]["capture"],
                "http_trap_hits": cases["wrong_cn"]["http_trap_hits"],
                "cache_sha_before": cases["wrong_cn"]["cache_sha_before"],
                "cache_sha_after": cases["wrong_cn"]["cache_sha_after"],
                "dest_exists_on_refuse": cases["wrong_cn"]["dest_exists"],
                "mutant_unverified_connects": cases["unverified_mutant_would_pass"]["mutant_ok"],
                "port80_bound": report["port80_bound"],
            },
            sort_keys=True,
        )
    )
    if failed:
        for name in failed:
            print(f"FAILED case {name}: {cases[name]['problems']}")
        print("FAILED:TST-0130-probe1")
        return 1
    # Independent capture: no port 80, exactly the TLS fixture port.
    for name in ("wrong_cn", "expired"):
        ports = {int(a["port"]) for a in cases[name]["capture"]}
        if 80 in ports:
            print(f"FAILED:TST-0130-probe1 capture port 80 on {name}: {cases[name]['capture']}")
            return 1
        if len(cases[name]["capture"]) < 1:
            print(f"FAILED:TST-0130-probe1 empty capture on {name}")
            return 1
    print("SUCCESS:TST-0130-probe1 tls-refuse no-plaintext-retry both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 1: three tampers rejected, untampered control verified, one invocation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402
from verifier import (  # noqa: E402
    ERROR_CONTENT,
    ERROR_IDENTITY,
    ERROR_PROVENANCE_MISSING,
    EXIT_CONTENT_DIGEST_MISMATCH,
    EXIT_PROVENANCE_MISSING,
    EXIT_SIGNATURE_IDENTITY_MISMATCH,
)

EXPECTED = {
    "content-byte-flip": (EXIT_CONTENT_DIGEST_MISMATCH, ERROR_CONTENT),
    "signature-swap": (EXIT_SIGNATURE_IDENTITY_MISMATCH, ERROR_IDENTITY),
    "provenance-stripped": (EXIT_PROVENANCE_MISSING, ERROR_PROVENANCE_MISSING),
}


def main() -> int:
    observed = M.run_matrix()
    if not observed.get("same_invocation"):
        print("FAILED:CNF-0110-probe1 not same_invocation")
        return 1
    if not observed.get("untampered_verified"):
        print("FAILED:CNF-0110-probe1 detector-failure untampered control did not verify")
        return 1
    if not observed.get("all_tampered_rejected"):
        print("FAILED:CNF-0110-probe1 verification-bypass a tampered variant was accepted")
        return 1
    if not observed.get("errors_distinguishable"):
        print("FAILED:CNF-0110-probe1 indistinguishable-error")
        return 1
    by_id = {row["id"]: row for row in observed["variants"]}
    for name, (exit_code, error_code) in EXPECTED.items():
        row = by_id.get(name)
        if row is None:
            print(f"FAILED:CNF-0110-probe1 missing variant {name}")
            return 1
        if int(row["exit_code"]) != exit_code or row.get("error_code") != error_code:
            print(
                f"FAILED:CNF-0110-probe1 {name} exit={row['exit_code']} "
                f"error={row.get('error_code')} expected {exit_code}/{error_code}"
            )
            return 1
        if not (row.get("verbatim_error") or "").startswith(f"CNF-0110-VERIFY FAIL {error_code}:"):
            print(f"FAILED:CNF-0110-probe1 {name} verbatim error not distinguishable")
            return 1
    control = observed["control"]
    print(
        json.dumps(
            {
                "invocation_id": observed["invocation_id"],
                "same_invocation": True,
                "control_exit": control["exit_code"],
                "variant_exits": {row["id"]: row["exit_code"] for row in observed["variants"]},
                "error_codes": observed["error_codes"],
                "contract_holds": True,
            },
            sort_keys=True,
        )
    )
    print(
        "control_ok=True tampers_rejected=3 distinguishable=True "
        f"invocation={observed['invocation_id']}"
    )
    print("SUCCESS:CNF-0110-probe1 negative control same-invocation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named settling experiment for CNF-0161 fixture claims.

A third party can run this command. Exit 0 means the named claim is still
unresolved under the recorded vendor verdicts; exit 1 means it is not.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_FIXTURE = HERE / "fixtures" / "unresolved.json"
UNRESOLVED = {
    "UNRESOLVED",
    "AMBIGUOUS-CLAIM",
    "AMBIGUOUS",
    "IRREDUCIBLE",
    "NOT-SETTLED",
    "OWNER-REQUIRED",
    "THREE-WAY-SPLIT",
}


def load_claim(path: Path, claim_id: str) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("unresolved_claims") or doc.get("claims") or []
    for row in rows:
        if isinstance(row, dict) and str(row.get("id") or "") == claim_id:
            return row
    raise KeyError(claim_id)


def still_unresolved(claim: dict) -> tuple[bool, str]:
    status = str(claim.get("status") or "").upper()
    a = str(claim.get("vendor_a_verdict") or "").upper()
    b = str(claim.get("vendor_b_verdict") or "").upper()
    c = str(claim.get("vendor_c_verdict") or "").upper()
    if status not in UNRESOLVED:
        return False, f"status={status} is terminal"
    if a and b and a == b and a not in {"", "NOT-CHECKED"}:
        return False, f"vendors A and B agree on {a}"
    if a and c and a == c and a not in {"", "NOT-CHECKED"}:
        return False, f"vendors A and C agree on {a}"
    if b and c and b == c and b not in {"", "NOT-CHECKED"}:
        return False, f"vendors B and C agree on {b}"
    return True, f"status={status} a={a} b={b} c={c}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claim", required=True)
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    args = parser.parse_args()
    path = Path(args.fixture)
    if not path.is_file():
        print(f"FAILED:settle_claim missing fixture {path}")
        return 2
    try:
        claim = load_claim(path, args.claim)
    except KeyError:
        print(f"FAILED:settle_claim unknown claim {args.claim}")
        return 2
    ok, reason = still_unresolved(claim)
    print(json.dumps({"claim": args.claim, "unresolved": ok, "reason": reason}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 1: every hit records publication number, jurisdiction, status, claim read.

Both-states: the live artifact is SILENT (accept). A mutant missing
publication_number, and a mutant with an empty register, FIRE (reject).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402

UID = "RES-0118"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    art = C.REPO / C.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    doc = C.load_artifact()
    good = C.validate_hit_register(doc, check_snapshots=True)
    missing = C.validate_hit_register(
        C.mutant_missing_publication(doc), check_snapshots=False
    )
    empty = C.validate_hit_register(
        C.mutant_empty_register(doc), check_snapshots=False
    )
    payload = {
        "probe": "probe1-hit-register-fields",
        "unit_id": UID,
        "good": good,
        "missing_publication": missing,
        "empty_register": empty,
        "n_hits": len(doc.get("hit_register") or []),
        "pass": bool(
            good["pass"] and (not missing["pass"]) and (not empty["pass"])
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"good_pass={good['pass']} missing_fires={not missing['pass']} "
        f"empty_fires={not empty['pass']} n_hits={payload['n_hits']}"
    )
    if good["errors"]:
        print("good_errors=" + "; ".join(good["errors"][:8]))
    if not good["pass"]:
        return fail("live artifact rejected")
    if missing["pass"]:
        return fail("missing publication_number mutant was accepted")
    if empty["pass"]:
        return fail("empty hit_register mutant was accepted")
    if "publication_number" not in " ".join(missing["errors"]):
        return fail("missing-publication mutant did not name publication_number")
    print(f"SUCCESS:{UID}-probe1 hit register fields both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

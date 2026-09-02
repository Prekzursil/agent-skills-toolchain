#!/usr/bin/env python3
"""Named probe 2: no scope interpretation may be provided or inferred.

Control: the live artifact carries the required not-legal-advice statement
and is SILENT. A mutant that adds 'this patent covers...' FIRE. A mutant
that drops the not-legal-advice statement FIRE. Garbage is rejected.
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
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    art = C.REPO / C.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    doc = C.load_artifact()
    good = C.validate_no_scope(doc)
    scoped = C.validate_no_scope(C.mutant_scope_language(doc))
    dropped = C.validate_no_scope(C.mutant_drop_not_legal_advice(doc))
    garbage = C.validate_no_scope({"totally": "unrelated", "passing_tests": 999999})
    payload = {
        "probe": "probe2-no-scope-interpretation",
        "unit_id": UID,
        "good": good,
        "scope_mutant": scoped,
        "dropped_disclaimer": dropped,
        "garbage": garbage,
        "pass": bool(
            good["pass"]
            and (not scoped["pass"])
            and (not dropped["pass"])
            and (not garbage["pass"])
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"good_pass={good['pass']} scope_fires={not scoped['pass']} "
        f"dropped_fires={not dropped['pass']} garbage_fires={not garbage['pass']}"
    )
    if good["errors"]:
        print("good_errors=" + "; ".join(good["errors"][:8]))
    if not good["pass"]:
        return fail("live artifact rejected")
    if scoped["pass"]:
        return fail("scope-language mutant was accepted")
    if dropped["pass"]:
        return fail("dropped not-legal-advice mutant was accepted")
    if garbage["pass"]:
        return fail("garbage document was accepted")
    if not any("scope-interpretation" in e for e in scoped["errors"]):
        return fail("scope mutant did not fire on interpretation language")
    nla = doc.get("not_legal_advice") or {}
    if "not legal advice" not in str(nla.get("statement") or "").lower():
        return fail("not-legal-advice statement absent")
    print(f"SUCCESS:{UID}-probe2 no scope interpretation both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 2: fusion checker via interface vs direct file access; version lock.

A mutant interface that skips conflict subtraction must disagree with the
direct walk. A RESULT_SCHEMA edit without a version bump must fail the lock.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import expected as E  # noqa: E402
import fusion_precondition as F  # noqa: E402
import query as Q  # noqa: E402

from contract import OUT_REL, SENTINEL  # noqa: E402

ART = REPO / OUT_REL
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0084-probe2 {msg}")
    return 1


def main() -> int:
    live = Q.load_fixture_interface(HERE)
    via_iface = F.fusible_pair_set(live)
    via_direct = E.fusible_pairs(FIX)
    print(f"via_interface={sorted(via_iface)}")
    print(f"via_direct={sorted(via_direct)}")
    if via_iface != via_direct:
        return fail(f"consumer/direct disagreement iface={via_iface} direct={via_direct}")

    report = F.precondition_report(live)
    naive = E.load_compat_pairs(FIX)
    if report["naive_compat_count"] != len(naive):
        return fail("consumer naive_compat_count drifted")
    if not report["conflict_subtraction_visible"]:
        return fail("consumer did not observe conflict subtraction")
    if report["fusible_count"] >= report["naive_compat_count"]:
        return fail("fusible was not strictly less than naive compat")

    mutant = Q.load_fixture_interface(HERE, subtract_conflicts=False)
    mutant_set = F.fusible_pair_set(mutant)
    print(f"mutant_no_subtract={sorted(mutant_set)}")
    if mutant_set == via_direct:
        return fail("conflict-skip mutant still agreed with direct; gate not live")
    if mutant_set != naive:
        return fail(f"conflict-skip mutant expected all compat, got {mutant_set}")
    if not via_direct < mutant_set:
        return fail("direct set was not a proper subset of the mutant")

    ok, why = Q.version_lock_holds()
    print(f"version_lock live ok={ok} why={why}")
    if not ok:
        return fail(f"live version lock {why}")

    mutated = copy.deepcopy(Q.RESULT_SCHEMA)
    mutated["required"] = list(mutated["required"]) + ["new_required_field"]
    mutated["properties"]["new_required_field"] = {"type": "string"}
    m_ok, m_why = Q.version_lock_holds(
        schema=mutated, version=Q.INTERFACE_VERSION, ledger=Q.VERSION_LEDGER
    )
    print(f"version_lock mutated-no-bump ok={m_ok} why={m_why}")
    if m_ok:
        return fail("schema change without version bump did not fail")
    if m_why != "schema-changed-without-version-bump":
        return fail(f"unexpected mutant reason {m_why}")

    bumped_ok, bumped_why = Q.version_lock_holds(
        schema=mutated,
        version="1.1.0",
        ledger={**Q.VERSION_LEDGER, "1.1.0": Q.schema_fingerprint(mutated)},
    )
    print(f"version_lock mutated-with-bump ok={bumped_ok} why={bumped_why}")
    if not bumped_ok:
        return fail("version bump with ledger update should hold")

    if not ART.is_file():
        return fail("handoff artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sig_b = (doc.get("evidence") or {}).get("signal_b") or {}
    if sorted(sig_b.get("via_interface") or []) != sorted(via_iface):
        return fail("artifact signal_b via_interface drift")
    if sorted(sig_b.get("via_direct") or []) != sorted(via_direct):
        return fail("artifact signal_b via_direct drift")
    if sig_b.get("mutant_disagreed") is not True:
        return fail("artifact missing mutant_disagreed")

    print(
        json.dumps(
            {
                "probe": "probe2-fusion-consumer-and-version",
                "unit_id": "WFA-0084",
                "via_interface": sorted(via_iface),
                "via_direct": sorted(via_direct),
                "mutant": sorted(mutant_set),
                "version_lock_live": why,
                "version_lock_no_bump": m_why,
            },
            sort_keys=True,
        )
    )
    print(
        "NEGATIVE-CONTROL skip-conflict-subtract: interface fusible equals naive "
        f"compat n={len(mutant_set)}; direct file access n={len(via_direct)}"
    )
    print("SUCCESS:WFA-0084-probe2 fusion consumer vs direct and version lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

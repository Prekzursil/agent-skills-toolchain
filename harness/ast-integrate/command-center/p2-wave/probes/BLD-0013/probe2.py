#!/usr/bin/env python3
"""Probe 2: independent re-read of five SATISFIES verdicts from spec+target.

The binding record is not an input. Dropping unit-target evidence must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from auditor import audit_binding, evidence_ok  # noqa: E402
from catalog_units import unit_view  # noqa: E402
from register import reconstructed_register  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0013.json"


def resolve_anchor(repo: Path, anchor: str, snippet: str) -> tuple[bool, str]:
    path_s, _, line_s = anchor.rpartition(":")
    path = repo / path_s
    if not path.is_file():
        return False, f"missing:{path_s}"
    try:
        line_n = int(line_s)
    except ValueError:
        return False, f"bad-line:{line_s}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_n < 1 or line_n > len(lines):
        return False, f"line-oob:{line_n}"
    window = "\n".join(lines[max(0, line_n - 2) : min(len(lines), line_n + 2)])
    needle = snippet[:48]
    if needle and needle not in window and needle not in path.read_text(encoding="utf-8"):
        return False, f"snippet-miss:{needle!r}"
    return True, f"{path_s}:{line_n}"


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0013-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    classes = doc.get("classifications") or []
    satisfies = [c for c in classes if c.get("verdict") == "SATISFIES"]
    if len(satisfies) < 5:
        print(f"FAILED:BLD-0013-probe2 need 5 SATISFIES, got {len(satisfies)}")
        return 1

    reread = (doc.get("reviewer") or {}).get("satisfies_reread") or []
    if len(reread) < 5:
        print("FAILED:BLD-0013-probe2 reviewer reread short")
        return 1
    if not doc.get("reviewer", {}).get("independent"):
        print("FAILED:BLD-0013-probe2 reviewer not independent")
        return 1

    reg = reconstructed_register(REPO)
    idx = {(r["requirement_id"], r["bound_unit_id"]): r for r in reg}

    for i, c in enumerate(satisfies[:5]):
        src = idx.get((c["requirement_id"], c["bound_unit_id"]))
        if src is None:
            print(f"FAILED:BLD-0013-probe2 register missing {c['requirement_id']}")
            return 1
        view = unit_view(REPO, c["bound_unit_id"])
        # Recompute from spec quote + unit target only.
        again = audit_binding(
            c["demanded_mechanism_quote"],
            view["target"],
            src["disjuncts"],
            src["domain_tokens"],
            bound_unit_id=c["bound_unit_id"],
        )
        print(
            f"reread[{i}] {c['requirement_id']}->{c['bound_unit_id']} "
            f"again={again['verdict']}"
        )
        if again["verdict"] != "SATISFIES":
            print("FAILED:BLD-0013-probe2 independent reread flipped SATISFIES")
            return 1
        ok, why = evidence_ok(c)
        print(f"evidence[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:BLD-0013-probe2 SATISFIES lacks spec+target evidence")
            return 1
        aok, awhy = resolve_anchor(REPO, c["unit_target_anchor"], c["unit_target_quote"])
        print(f"anchor[{i}] ok={aok} {awhy}")
        if not aok:
            print("FAILED:BLD-0013-probe2 unit target anchor unresolved")
            return 1

    mutant = copy.deepcopy(satisfies[0])
    mutant["evidence_source"] = "binding-record"
    mutant["unit_target_quote"] = mutant.get("binding_record_quote") or (
        f"{mutant['requirement_id']} bound to {mutant['bound_unit_id']}"
    )
    mok, mwhy = evidence_ok(mutant)
    print(f"mutant_binding_record_ok={mok} {mwhy}")
    if mok:
        print("FAILED:BLD-0013-probe2 binding-record-only SATISFIES was accepted")
        return 1

    print("SUCCESS:BLD-0013-probe2 five SATISFIES reread; binding-record mutant rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

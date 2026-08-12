r"""Receipt admission check: parse + schema + CATALOG CROSS-REFERENCE, single-bit verdict.

WHY THIS EXISTS AND WHY IT IS NOT A SECOND VALIDATOR. `platform/lib/receipt_schema_gate.py`
already ships two layers -- JSON Schema (layer 1) and the 12-condition completion predicate
(layer 2) -- and this module IMPORTS it rather than reimplementing either. Measured gap
(`command-center/p2-wave/_r2_cc0002_gap.py`, executed 2026-08-12):

    fixture                       schema-only  full-gate
    golden (TST-0334)                    rc=0       rc=1
    m1-missing-sentinel                  rc=1       rc=1
    m2-empty-evidence                    rc=1       rc=1
    m3-unit-id-not-in-catalog            rc=0       rc=1   <-- ACCEPTED
    m4-unparseable                       rc=1       rc=1

Two facts fall out of that table, and CC-0002's contract needs both addressed:

  * layer 1 ACCEPTS a receipt whose `unit_id` is `ZZZ-9999`, an id that does not exist in the
    2,007-unit catalog. `WORK-UNIT-CATALOG` and `work_units` do not appear anywhere in
    receipt_schema_gate.py -- there is no cross-reference to be found, so this is a real hole,
    not a use-vs-mention miss;
  * layer 2 rejects the GOLDEN receipt too (rc=1), correctly -- it is state=BLOCKED on the
    reviewer gate -- so layer 2 cannot serve as the accept/reject instrument for CC-0002's
    "a golden receipt validates" test. Admission and completion are different questions.

So this module answers ADMISSION only: is this document a well-formed receipt for a real unit?
It deliberately does NOT answer completion; `receipt_schema_gate.py` does, and conflating the
two is the defect ADV-0001 attacks. Every message here says which question was answered.

Single-bit output by design: ACCEPT / REJECT plus one reason, never a score. A numeric quality
score becomes the next thing to optimise; an accept/reject bit cannot be partially satisfied.

    python command-center/receipt_validate.py command-center/receipts/*.json
    python command-center/receipt_validate.py --self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
GATE_PATH = REPO / "platform/lib/receipt_schema_gate.py"


def _load_gate():
    """Import the existing validator. A missing gate is a HARD failure: silently falling back to
    a weaker local check is how a gate turns into a no-op."""
    spec = importlib.util.spec_from_file_location("receipt_schema_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"FAILED:receipt-validate cannot load {GATE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["receipt_schema_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def catalog_ids() -> set[str]:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {u["id"] for u in doc["work_units"] if isinstance(u.get("id"), str)}


def admit(path: Path, ids: set[str], gate) -> tuple[bool, str, str]:
    """Return (accepted, unit_id, reason). Fail closed on every unexpected condition."""
    try:
        raw = path.read_bytes().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        return False, "<unreadable>", f"C1 unreadable: {type(exc).__name__}"
    try:
        doc: Any = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        return False, "<unparseable>", f"C1 unparseable JSON: {type(exc).__name__}"
    if not isinstance(doc, dict):
        return False, "<not-an-object>", "C1 top-level value is not an object"

    uid = doc.get("unit_id")
    uid_s = uid if isinstance(uid, str) and uid else "<missing>"

    errs = gate.validate_receipt(doc)
    if errs:
        return False, uid_s, f"C2 schema-invalid ({len(errs)}): {errs[0][:120]}"

    if uid_s not in ids:
        return False, uid_s, f"C3 unit_id {uid_s!r} is not one of the {len(ids)} catalog units"

    sentinel = doc.get("sentinel")
    if not isinstance(sentinel, str) or uid_s not in sentinel:
        return False, uid_s, f"C4 sentinel does not embed the unit id: {str(sentinel)[:80]!r}"

    return True, uid_s, "C1 parses; C2 schema-valid; C3 unit is in the catalog; C4 sentinel binds"


def self_test() -> int:
    """Both-states control: the golden must be ACCEPTED and all four mutants REJECTED, each for
    its OWN reason. A validator that rejects everything is as useless as one that accepts
    everything, so the accept side is asserted too."""
    gate = _load_gate()
    ids = catalog_ids()
    tmp = REPO / "command-center/p2-wave/_r2_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    golden_path = REPO / "command-center/receipts/TST-0334.json"
    if not golden_path.is_file():
        print(f"FAILED:receipt-validate self-test golden {golden_path} absent")
        return 1
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    cases: list[tuple[str, Path, bool, str]] = [("golden", golden_path, True, "")]

    m1 = json.loads(json.dumps(golden))
    m1.pop("sentinel", None)
    m2 = json.loads(json.dumps(golden))
    m2["evidence"] = []
    m3 = json.loads(json.dumps(golden))
    m3["unit_id"] = "ZZZ-9999"
    if isinstance(m3.get("sentinel"), str):
        m3["sentinel"] = m3["sentinel"].replace(str(golden.get("unit_id")), "ZZZ-9999")
    for name, doc, want_code in (
        ("m1-missing-sentinel", m1, "C2"),
        ("m2-empty-evidence", m2, "C2"),
        ("m3-unit-id-not-in-catalog", m3, "C3"),
    ):
        p = tmp / f"selftest-{name}.json"
        p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        cases.append((name, p, False, want_code))
    p4 = tmp / "selftest-m4-unparseable.json"
    p4.write_text('{"unit_id": "TST-0334", "state": ', encoding="utf-8")
    cases.append(("m4-unparseable", p4, False, "C1"))

    ok = True
    for name, p, want, want_code in cases:
        got, uid, reason = admit(p, ids, gate)
        code_ok = want or reason.startswith(want_code)
        good = (got is want) and code_ok
        if not good:
            ok = False
        print(
            f"  CONTROL {name:<26} want={'ACCEPT' if want else 'REJECT':<6} "
            f"got={'ACCEPT' if got else 'REJECT':<6} "
            f"{'OK' if good else 'BROKEN'}  {reason[:96]}"
        )
    if not ok:
        print("FAILED:receipt-validate self-test the admission check does not discriminate")
        return 1
    print(
        "SUCCESS:receipt-validate self-test 1 golden ACCEPTED, 4 mutants REJECTED each on its "
        "own condition (C1 parse, C2 schema x2, C3 catalog cross-reference)"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("receipt", nargs="*", help="receipt JSON path(s)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.receipt:
        print("FAILED:receipt-validate no input; an empty walk is not a pass")
        return 1

    gate = _load_gate()
    ids = catalog_ids()
    rows, worst = [], 0
    for spec in args.receipt:
        p = Path(spec)
        if not p.is_absolute():
            p = REPO / spec
        got, uid, reason = admit(p, ids, gate)
        rows.append({"path": spec, "unit_id": uid, "admitted": got, "reason": reason})
        if not args.json:
            print(f"{'ACCEPT' if got else 'REJECT'}:{uid} {reason}")
        if not got:
            worst = 1
    if args.json:
        print(json.dumps(rows, indent=2))
    if worst == 0 and not args.json:
        print(
            f"SUCCESS:receipt-validate {len(rows)} receipt(s) ADMITTED "
            "(admission only -- completion is receipt_schema_gate.py layer 2)"
        )
    return worst


if __name__ == "__main__":
    raise SystemExit(main())

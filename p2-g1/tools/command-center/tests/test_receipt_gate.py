"""IMP-0435 receipt-gate test battery (stdlib only, both states)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (str(REPO / "command-center"), str(HERE.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import receipt_gate  # noqa: E402
import receipt_validate as rv  # noqa: E402

RESULTS = []


def _record(name, cond, detail=""):
    RESULTS.append(("PASS " if cond else "FAIL ") + name + ((" :: " + detail) if detail else ""))


def test_green_registered_receipt_admitted():
    golden = rv.minimal_golden(REPO)
    rel = "command-center/receipts/TMP-GATE-GREEN.json"
    golden["id"] = "TMP-GATE-GREEN"
    (REPO / rel).write_text(json.dumps(golden, indent=2), encoding="utf-8")
    try:
        ids = rv.catalog_ids(REPO)
        gate = rv._load_gate()
        ok, uid, reason = rv.admit(REPO / rel, ids, gate)
        _record("green golden receipt admits", ok, reason[:80])
    finally:
        (REPO / rel).unlink(missing_ok=True)


def test_red_unknown_id_gates():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pd = root / "command-center" / "p2-wave" / "probes" / "IMP-0435"
        pd.mkdir(parents=True)
        (pd / "UNIT-ARTIFACT-MANIFEST.json").write_text(json.dumps({
            "unit_id": "IMP-0435",
            "artifacts": [{"unit_id": "ZZZ-9999",
                           "path": "command-center/receipts/ZZZ-9999.json",
                           "present": True}]}), encoding="utf-8")
        rd = root / "command-center" / "receipts"
        rd.mkdir(parents=True)
        (rd / "ZZZ-9999.json").write_text(
            json.dumps({"id": "ZZZ-9999", "state": "SUCCESS"}), encoding="utf-8")
        report = receipt_gate.check_default(root)
        _record("unknown-id registered receipt rejected",
                (not report["ok"]) and report["rejected_count"] == 1,
                json.dumps(report.get("rejected"))[:110])


def test_empty_walk_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        report = receipt_gate.check_default(Path(td))
        _record("empty walk is red", (not report["ok"]) and report.get("empty_walk") is True)


def test_banned_flags_refused():
    for flag in receipt_gate.BANNED_FLAGS[:3]:
        rc = receipt_gate.main([flag])
        _record("banned flag refused: " + flag, rc == 2, "rc=%d" % rc)


def test_missing_registered_receipt_red():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pd = root / "command-center" / "p2-wave" / "probes" / "IMP-0435"
        pd.mkdir(parents=True)
        (pd / "UNIT-ARTIFACT-MANIFEST.json").write_text(json.dumps({
            "unit_id": "IMP-0435",
            "artifacts": [{"unit_id": "IMP-0435",
                           "path": "command-center/receipts/IMP-0435.json",
                           "present": True}]}), encoding="utf-8")
        (root / "command-center" / "receipts").mkdir(parents=True)
        report = receipt_gate.check_default(root)
        _record("missing registered receipt is red", (not report["ok"])
                and report["rejected_count"] == 1)


ALL = [test_green_registered_receipt_admitted,
       test_red_unknown_id_gates,
       test_empty_walk_fail_closed,
       test_banned_flags_refused,
       test_missing_registered_receipt_red]

if __name__ == "__main__":
    for fn in ALL:
        try:
            fn()
        except Exception as exc:
            RESULTS.append("FAIL " + fn.__name__ + " raised " + repr(exc))
    for line in RESULTS:
        print(line)
    nfail = sum(1 for l in RESULTS if l.startswith("FAIL"))
    if nfail or not RESULTS:
        print("FAILED:receipt-gate tests %d checks, %d failed"
              % (len(RESULTS), nfail))
        raise SystemExit(1)
    print("SUCCESS:receipt-gate tests %d checks, 0 failed" % len(RESULTS))

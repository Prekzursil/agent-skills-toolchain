#!/usr/bin/env python3
"""TST-0143 probe2 -- live boundary re-run of completion-predicate condition 3.

Drives the live platform/lib/completion_predicate.py evaluate() on synthetic
receipts over size-boundary fixtures (0 / floor-1 / floor / floor+1 bytes,
an alternative 80 B floor, and a sub-absolute 40 B declaration) and asserts
the C03 outcomes the receipt records. The second signal is an independent
stat() of each fixture.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0143.json"
FIXDIR = Path(__file__).resolve().parent / "fixtures"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def main() -> int:
    for extra in (str(REPO / "platform/lib"), str(REPO)):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    spec = importlib.util.spec_from_file_location("live_completion_predicate", REPO / "platform/lib/completion_predicate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_completion_predicate"] = mod
    spec.loader.exec_module(mod)

    FIXDIR.mkdir(parents=True, exist_ok=True)
    sizes = {"empty.bin": 0, "floor1.bin": 127, "floor.bin": 128, "floor1p.bin": 129, "alt80.bin": 80, "sub40.bin": 40}
    rels = {}
    for name, n in sizes.items():
        p = FIXDIR / name
        p.write_bytes(b"x" * n)
        rels[name] = (p, "command-center/p2-wave/probes/TST-0143/fixtures/" + name, n)

    def c3(rel: str, declared: int):
        receipt = {
            "unit_id": "TST-0143",
            "state": "COMPLETE",
            "sentinel": "SUCCESS:TST-0143",
            "min_bytes_threshold": declared,
            "artifacts": [{"path": rel, "bytes": sizes[Path(rel).name], "role": "primary", "sha256": None}],
        }
        opts = mod.PredicateOptions(repo_root=REPO)
        res = mod.evaluate(receipt, opts, skip={1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12})
        row = next(c for c in res.conditions if c.n == 3)
        oname = getattr(row.outcome, "name", None) or str(row.outcome)
        return oname, row.basis

    o0, _ = c3(rels["empty.bin"][1], 128)
    o127, _ = c3(rels["floor1.bin"][1], 128)
    o128, _ = c3(rels["floor.bin"][1], 128)
    o129, _ = c3(rels["floor1p.bin"][1], 128)
    o80, _ = c3(rels["alt80.bin"][1], 80)
    o40, b40 = c3(rels["sub40.bin"][1], 40)
    chk(o0 == "UNSATISFIED", "0B", o0)
    chk(o127 == "UNSATISFIED", "floor-1", o127)
    chk(o128 == "SATISFIED", "floor", o128)
    chk(o129 == "SATISFIED", "floor+1", o129)
    chk(o80 == "SATISFIED", "alt-80", o80)
    chk(o40 == "UNSATISFIED", "sub-absolute-40", o40)

    # independent stat() second signal
    for name, (p, _, n) in rels.items():
        chk(p.stat().st_size == n, "stat-drift", name)

    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    ans = str((doc.get("extensions") or {}).get("answer") or "")
    for token in ("128 B", "80 B", "40 B", "ABSOLUTE_MIN_BYTES"):
        chk(token in ans, "answer-token", token)
    basis = json.dumps(doc.get("report") or {})
    chk("boundary floor-1/floor/floor+1" in basis or "floor-1/floor/floor+1" in basis, "recorded-boundary-text")
    if FAILS:
        print("FAILED:TST-0143-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0143-probe2 live C03: 0B UNSATISFIED, floor-1 UNSATISFIED, floor SATISFIED, floor+1 SATISFIED, alt 80B floor SATISFIED at exact size, sub-absolute 40B declaration raised; independent stat() agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

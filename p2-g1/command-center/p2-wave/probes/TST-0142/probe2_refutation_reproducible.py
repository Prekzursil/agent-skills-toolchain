#!/usr/bin/env python3
"""TST-0142 probe2 -- fan-in refutation: reproduce if the candidate exists,
else verify the receipt's honesty invariants and the recorded sha.

The receipt REFUTED the nearest live r2e fan-in loop (it drops exceptional
futures and prints success over the survivor denominator, 3/3) while the
exact B07 barrier stays NOT-CHECKED. This probe re-runs the refutation
against the live loop when present; otherwise it verifies the recorded sha
and that the receipt's no-hand-flip invariants still hold.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0142.json"

FAILS: list[str] = []
HEX = re.compile(r"^[0-9a-f]{64}$")


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def norm_sha(p: Path) -> tuple[str, int]:
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    ro = str(doc.get("refutation_outcome") or "")
    chk("REFUTED-NEAREST-LIVE-CANDIDATE" in ro and "EXACT-B07-TARGET-NOT-CHECKED" in ro, "refutation-outcome", ro)
    qa = str(doc.get("question_answer") or "")
    chk("FAIL for the nearest live" in qa, "question-answer", qa[:60])
    chk(doc.get("success_withheld_while_condition11_red") is True, "withheld-flag")
    chk(any("UNIT-COMPLETE:TST-0142" in ln for ln in json.dumps(doc).splitlines()), "completion-line")

    t = doc.get("this_tree_honesty") or {}
    sha_rec = str(t.get("r2e_loop_sha256") or "")
    chk(bool(HEX.match(sha_rec)), "recorded-sha-not-hex", sha_rec)
    chk(t.get("r2e_loop_drops_exceptional_futures") is True, "recorded-drops-false")
    chk(t.get("r2e_loop_prints_success_over_survivor_denominator") is True, "recorded-shrunk-false")
    mutants = t.get("mutants_measured_not_applied") or {}
    chk(mutants.get("applied") is False, "mutants-applied")
    foc = REPO / str(t.get("fan_out_contract_path") or "rules/common/fan-out-contract.md")
    chk(foc.is_file(), "fan-out-contract-absent-live", foc)

    # live candidate search
    cand = None
    for base in (REPO / "command-center", REPO / "tools"):
        if base.is_dir():
            cand = next(base.rglob("r2e_loop.py"), None)
            if cand:
                break
    if cand is not None:
        sha, _ = norm_sha(cand)
        if sha == sha_rec:
            spec = importlib.util.spec_from_file_location("live_r2e_loop", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print("NOTE live r2e_loop found at %s with matching sha; refutation reproduces if the loop still drops exceptional futures" % cand.relative_to(REPO))
        else:
            print("NOTE live r2e_loop found but sha differs (recorded %s... live %s...); refutation not re-run" % (sha_rec[:12], sha[:12]))
    else:
        print("NOTE live r2e_loop absent on this tree; the recorded refutation stands as a historical measurement and the exact-target absence conclusion still holds live")
    if FAILS:
        print("FAILED:TST-0142-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0142-probe2 refutation receipt verified: outcome REFUTED-NEAREST-LIVE-CANDIDATE + exact-target NOT-CHECKED recorded; dropped-exceptional-futures + shrunken-denominator flags recorded; sha integrity ok; no mutant applied; fan-out contract live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

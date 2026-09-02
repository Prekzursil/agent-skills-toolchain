#!/usr/bin/env python3
"""Probe 2: negative control — disable retrieval, early-round citations collapse.

Independent of the author's summary: starts from the retrieve public API and
from the tests, then checks the receipt for overclaim. Measurement sensitivity
is proven two ways: (1) retrieval off yields rate 0 on the overflowing council;
(2) a mutant citer that reads the durable store instead of the prompt would not
collapse — the real citer must refuse that mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.evidence.retrieve import (  # noqa: E402
    RetrieveConfig,
    build_overflow_council,
    cite_early_anchors,
    run_both_configurations,
    run_council,
)

ART = REPO / "command-center/receipts/IMP-0349.json"
MODULE = REPO / "tools/council/evidence/retrieve.py"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0349-probe2 {msg}")
    return 1


def _mutant_store_citer(prompt: str, early) -> tuple[str, ...]:
    """Illegal citer: cites every early anchor from the store, ignoring prompt."""
    del prompt
    return tuple(a.id for a in early)


def main() -> int:
    if not MODULE.is_file():
        return fail("retrieve.py missing")
    council = build_overflow_council()
    live = run_both_configurations(council, token_budget=48)
    off = run_council(council, RetrieveConfig(enabled=False, token_budget=48))

    rate_off = float(live["rate_off"]["rate"])
    rate_on = float(live["rate_on"]["rate"])
    print(
        json.dumps(
            {
                "rate_on": rate_on,
                "rate_off": rate_off,
                "pass_negative_control": live.get("pass_negative_control"),
                "late_off": live["rate_off"]["per_turn"],
                "off_late_fetches": [
                    list(t.fetched_anchor_ids) for t in off.turns if t.round >= 7
                ],
            },
            sort_keys=True,
            default=str,
        )[:3000]
    )

    if not live.get("pass_negative_control"):
        return fail("negative-control predicate false")
    if rate_off != 0.0:
        return fail(f"rate_off={rate_off} did not collapse")
    if rate_on <= rate_off:
        return fail("measurement is not sensitive: on did not beat off")
    late_off = [t for t in off.turns if t.round >= 7]
    if len(late_off) != 2:
        return fail("expected two late turns")
    if any(t.fetched_anchor_ids for t in late_off):
        return fail("disabled retrieval still fetched")
    if any(t.cited_early_ids for t in late_off):
        return fail("disabled retrieval still cited early anchors")
    if not all(t.overflowed for t in late_off):
        return fail("late turns did not overflow under disable")

    early = council.early_anchors()
    empty_prompt = "ROLE skeptic seat-0\nQUERY freshness dates\nHISTORY filler only"
    real_empty = cite_early_anchors(empty_prompt, early)
    if real_empty:
        return fail(f"citer fired on empty prompt {real_empty}")
    restored = empty_prompt + "\n" + early[0].body
    real_hit = cite_early_anchors(restored, early)
    if real_hit != (early[0].id,):
        return fail(f"citer missed restored marker {real_hit}")
    mutant_empty = _mutant_store_citer(empty_prompt, early)
    if set(mutant_empty) != {a.id for a in early}:
        return fail("mutant store-citer did not over-cite")
    if set(real_empty) == set(mutant_empty):
        return fail("real citer is the store-citer mutant; measurement is insensitive")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0349" not in text:
        return fail("sentinel-absent")
    if doc.get("reviewer_verdict") != "PASS":
        return fail(f"reviewer_verdict {doc.get('reviewer_verdict')}")
    negs = doc.get("negative_control_ids") or []
    if not negs:
        return fail("negative_control_ids empty")
    residuals = [str(x) for x in (doc.get("residual_unknowns") or [])]
    blob = " ".join(residuals).lower()
    if "imp-0338" not in blob and "context.py" not in blob:
        return fail("residual_unknowns silent on missing IMP-0338 context.py")
    if "llm" not in blob and "live council" not in blob:
        return fail("residual_unknowns silent on no live LLM council")
    low = text.lower()
    answer = str(doc.get("answer") or "").lower()
    if "imp-0338 delivered" in low or "imp-0314 delivered" in low:
        return fail("overclaim: sibling IMP marked delivered")
    if "live llm" in answer and "not a live" not in answer:
        return fail("overclaim: answer asserts a live LLM council")
    if "vendor bpe" in low:
        return fail("overclaim: vendor BPE tokenizer")
    spec = str(doc.get("spec_anchor") or "")
    if ":" not in spec:
        return fail(f"spec_anchor not path:line {spec}")
    rel, _, line_s = spec.partition(":")
    spec_path = REPO / rel
    if not spec_path.is_file():
        return fail(f"spec_anchor file missing {rel}")
    try:
        line_no = int(line_s.split(":", 1)[0])
    except ValueError:
        return fail(f"spec_anchor line not int {spec}")
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    if line_no < 1 or line_no > len(lines):
        return fail("spec_anchor line oob")
    hit = lines[line_no - 1]
    if "retrieve.py" not in hit and "early-round" not in hit:
        return fail(f"spec_anchor line does not name the unit {hit[:160]}")

    print("collapse=True mutant_store_citer_rejected=True")
    print("SUCCESS:IMP-0349-probe2 negative-control collapse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

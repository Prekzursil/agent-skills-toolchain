#!/usr/bin/env python3
"""Probe 1: held-out policy choices vs the operator that actually certified.

Evidence A. Re-fits the policy from the TRAIN split only, applies it to
held-out pairs, and requires the live artifact to match the recomputation
and to beat the random-operator baseline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0111-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if doc.get("record_type") != "AuditReport" or doc.get("unit_id") != E.UNIT:
        return fail("not-an-audit-report")

    pairs = E.load_pairs()
    train = [p for p in pairs if p["split"] == "train"]
    held = [p for p in pairs if p["split"] == "held_out"]
    policy = E.fit_policy(train)
    ev = E.evaluate(policy, held)

    rec = doc.get("held_out_evaluation") or {}
    if int(rec.get("n") or 0) != ev["n"]:
        return fail(f"held-out n drift rec={rec.get('n')} live={ev['n']}")
    if int(rec.get("exact_matches") or -1) != ev["exact_matches"]:
        return fail("exact_matches drift")
    if abs(float(rec.get("exact_match_rate") or -1) - ev["exact_match_rate"]) > 1e-9:
        return fail("exact_match_rate drift")
    if rec.get("policy_beats_random") is not True:
        return fail("artifact policy_beats_random is not true")
    if not ev["policy_beats_random"]:
        return fail("recomputed policy does not beat random")
    if ev["margin_over_random"] < 0.15:
        return fail(f"margin {ev['margin_over_random']} < 0.15")

    rec_rows = {r["id"]: r for r in rec.get("rows") or [] if isinstance(r, dict)}
    if len(rec_rows) != ev["n"]:
        return fail("held-out row count mismatch")
    disagreements = []
    for live in ev["rows"]:
        rec_row = rec_rows.get(live["id"])
        if rec_row is None:
            return fail(f"missing held-out row {live['id']}")
        if rec_row.get("policy_choice") != live["policy_choice"]:
            disagreements.append(live["id"])
        if rec_row.get("certified") != live["certified"]:
            return fail(f"certified drift {live['id']}")
        if rec_row.get("match") is not live["match"]:
            return fail(f"match flag drift {live['id']}")
    if disagreements:
        return fail(f"policy_choice drift n={len(disagreements)}")

    corpus = doc.get("corpus") or {}
    if corpus.get("path") != E.PAIRS_REL:
        return fail("fit-inputs path missing")
    if corpus.get("n_train") != len(train) or corpus.get("n_held_out") != len(held):
        return fail("corpus split counts drift")

    pol = doc.get("policy") or {}
    if pol.get("revisable") is not True:
        return fail("policy not marked revisable")
    if int(pol.get("n_train") or 0) != len(train):
        return fail("policy n_train drift")
    if not pol.get("rules"):
        return fail("policy rules absent")

    print(
        json.dumps(
            {
                "probe": "probe1-held-out-vs-certified",
                "n_held_out": ev["n"],
                "exact_matches": ev["exact_matches"],
                "exact_match_rate": ev["exact_match_rate"],
                "random_expected_rate": ev["random_expected_rate"],
                "margin_over_random": ev["margin_over_random"],
                "not_fusible_held_out": ev["not_fusible_n"],
                "pass": True,
                "unit_id": E.UNIT,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0111-probe1 held-out policy vs certified operator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

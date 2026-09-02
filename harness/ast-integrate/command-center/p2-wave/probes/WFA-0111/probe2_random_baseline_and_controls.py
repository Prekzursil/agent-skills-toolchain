#!/usr/bin/env python3
"""Probe 2: independent random baseline, NOT-FUSIBLE, both-states controls.

Evidence B plus the adversarial reviewer requirement. Does not treat the
artifact's published random rate as an authority: it recomputes expected
random as mean(1/7 for fusible golds, else 0). Invert-policy must not
beat random. Planted conflict must refuse union. Planted licence block
must be NOT-FUSIBLE. Schema must reject garbage and accept the live
artifact.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / E.OUT_REL
SCHEMA = HERE / "audit-report.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0111-probe2 {msg}")
    return 1


def independent_random_expected(golds: list[str]) -> float:
    """Second implementation of the random-operator baseline."""
    n = len(golds)
    if n == 0:
        return 0.0
    hits = 0.0
    for g in golds:
        if g in E.OPERATORS:
            hits += 1.0 / float(len(E.OPERATORS))
    return hits / n


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

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not E.schema_rejects_garbage(schema):
        return fail("schema-accepts-garbage")
    try:
        E.schema_accepts(schema, doc)
    except Exception as exc:
        return fail(f"live-artifact-schema:{exc}")

    pairs = E.load_pairs()
    train = [p for p in pairs if p["split"] == "train"]
    held = [p for p in pairs if p["split"] == "held_out"]
    policy = E.fit_policy(train)
    ev = E.evaluate(policy, held)
    golds = [p["certified"] for p in held]
    indep = independent_random_expected(golds)
    pub = float(
        (doc.get("random_baseline") or {}).get("expected_exact_match_rate") or -1
    )
    if abs(indep - ev["random_expected_rate"]) > 1e-6:
        return fail("engine random != independent random")
    if abs(pub - indep) > 1e-6:
        return fail(f"published random {pub} != independent {indep}")
    if not ev["policy_beats_random"]:
        return fail("policy does not beat independent random")
    if ev["exact_match_rate"] <= indep:
        return fail("policy rate did not exceed independent random")
    if not ev["invert_does_not_beat_random"]:
        return fail("invert-policy beat random (control silent)")
    if ev["invert_policy_rate"] >= ev["exact_match_rate"]:
        return fail("invert-policy matched the real policy; control broken")

    nf = doc.get("not_fusible") or {}
    if nf.get("token") != E.NOT_FUSIBLE or nf.get("valid_outcome") is not True:
        return fail("NOT-FUSIBLE not recorded as a valid outcome")
    if int(nf.get("n_held_out") or 0) < 1:
        return fail("no held-out NOT-FUSIBLE")
    live_nf = [p["id"] for p in held if p["certified"] == E.NOT_FUSIBLE]
    if sorted(nf.get("ids_held_out") or []) != sorted(live_nf):
        return fail("NOT-FUSIBLE id list drift")

    union_row = next(
        (
            p
            for p in held
            if p["certified"] == "union" and not p["conflict_presence"]
        ),
        None,
    )
    if union_row is None:
        union_row = next(
            (
                p
                for p in train
                if p["certified"] == "union" and not p["conflict_presence"]
            ),
            None,
        )
    if union_row is None:
        return fail("no clean union-gold pair for conflict plant")
    planted = copy.deepcopy(union_row)
    planted["conflict_presence"] = True
    after = E.apply_policy(policy, planted)
    oracle_after = E.certify_pair(planted)
    if "union" in oracle_after["certified_set"] or oracle_after["certified"] == "union":
        return fail("oracle still certifies union under conflict (instrument broken)")
    if after["policy_choice"] == "union":
        return fail("policy still selected union after conflict plant")

    blocked = copy.deepcopy(held[0])
    blocked["licence_incompatible"] = True
    oracle_b = E.certify_pair(blocked)
    pol_b = E.apply_policy(policy, blocked)
    if oracle_b["certified"] != E.NOT_FUSIBLE or oracle_b["certified_set"]:
        return fail("licence plant did not make oracle NOT-FUSIBLE")
    if pol_b["policy_choice"] != E.NOT_FUSIBLE:
        return fail(
            f"licence plant policy_choice={pol_b['policy_choice']} not NOT-FUSIBLE"
        )

    if not held[0].get("licence_incompatible"):
        orig = E.apply_policy(policy, held[0])
        if orig["policy_choice"] == pol_b["policy_choice"] and orig[
            "policy_choice"
        ] != E.NOT_FUSIBLE:
            return fail("licence plant did not change policy (control silent)")

    print(
        json.dumps(
            {
                "probe": "probe2-random-baseline-and-controls",
                "independent_random_expected": round(indep, 6),
                "policy_rate": ev["exact_match_rate"],
                "invert_rate": ev["invert_policy_rate"],
                "not_fusible_held_out": len(live_nf),
                "conflict_plant_refused_union": True,
                "licence_plant_not_fusible": True,
                "schema_rejects_garbage": True,
                "pass": True,
                "unit_id": E.UNIT,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0111-probe2 random baseline, NOT-FUSIBLE, both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

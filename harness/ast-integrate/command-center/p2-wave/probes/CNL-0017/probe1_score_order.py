#!/usr/bin/env python3
"""Probe 1: a priori threshold, then unbalanced must score worse than balanced.

Two independent censuses: collections.Counter vs sort|uniq -c.
Diversity (richness D) is equal on the pair, so richness cannot be the metric.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import metric as M  # noqa: E402

NOTE = REPO / (
    "command-center/design/council/"
    "CNL-0017-stakeholder-balanced-selection-the-taxonomy-and-the-balanc.md"
)
SCHEMA = HERE / "note.schema.json"
CATALOG_SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
FIX = HERE / "fixtures"
THRESHOLD = FIX / "threshold.json"
TARGET = FIX / "target.json"
BAL = FIX / "roster-balanced.json"
UNB = FIX / "roster-unbalanced.json"

ALLOWED_THR_KEYS = {
    "taxonomy_id",
    "I_star",
    "rule",
    "declared_before_scoring",
    "note",
}


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def shell_census(seats: list[dict]) -> tuple[dict[str, int], str]:
    lines = "".join(f"{s['stakeholder_class']}\n" for s in seats)
    sort_p = subprocess.run(
        ["sort"],
        input=lines,
        capture_output=True,
        text=True,
        check=True,
    )
    uniq_p = subprocess.run(
        ["uniq", "-c"],
        input=sort_p.stdout,
        capture_output=True,
        text=True,
        check=True,
    )
    counts = {c: 0 for c in M.CLASSES}
    for line in uniq_p.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        n, cls = parts
        counts[cls] = int(n)
    return counts, uniq_p.stdout


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0017-probe1 {msg}")
    return 1


def main() -> int:
    # --- threshold is loaded and printed BEFORE any roster is scored ---
    thr = load(THRESHOLD)
    print("THRESHOLD_DECLARED_BEFORE_SCORE " + json.dumps(thr, sort_keys=True))
    thr_sha = sha256_file(THRESHOLD)
    print(f"THRESHOLD_SHA256 {thr_sha}")
    extra = set(thr) - ALLOWED_THR_KEYS
    if extra:
        return fail(f"threshold file contains scoring fields {sorted(extra)}")
    if "I_balanced" in thr or "I_unbalanced" in thr or "rosters" in thr:
        return fail("threshold file looks retrofitted with scores")
    if thr.get("declared_before_scoring") is not True:
        return fail("declared_before_scoring is not true")
    if not isinstance(thr.get("I_star"), int) or thr["I_star"] < 0:
        return fail("I_star missing")
    i_star = int(thr["I_star"])
    if thr.get("taxonomy_id") != M.TAXONOMY_ID:
        return fail("taxonomy_id mismatch")

    target_doc = load(TARGET)
    target = target_doc["target"]
    if sum(target.values()) != 8:
        return fail("target occupancy does not sum to 8")

    # --- now load and score rosters ---
    bal = load(BAL)
    unb = load(UNB)
    s_bal = M.score(bal["seats"], target, i_star)
    s_unb = M.score(unb["seats"], target, i_star)
    print("SCORE_BALANCED " + json.dumps(s_bal, sort_keys=True))
    print("SCORE_UNBALANCED " + json.dumps(s_unb, sort_keys=True))

    if not s_bal["valid"] or not s_unb["valid"]:
        return fail("fixture seats used labels outside the closed catalog")
    if s_bal["I"] is None or s_unb["I"] is None:
        return fail("I missing")
    if s_unb["I"] <= s_bal["I"]:
        return fail(f"unbalanced I={s_unb['I']} not worse than balanced I={s_bal['I']}")
    if not (s_bal["I"] <= i_star < s_unb["I"]):
        return fail(
            f"threshold does not separate: I_bal={s_bal['I']} I_star={i_star} "
            f"I_unb={s_unb['I']}"
        )
    if s_unb["D"] < s_bal["D"]:
        return fail("unbalanced fixture is less rich; richness could explain the fail")
    if s_bal["D"] != len(M.CLASSES) or s_unb["D"] != len(M.CLASSES):
        return fail("expected both fixtures to seat every catalog class")
    if s_bal["fires"] or not s_unb["fires"]:
        return fail("decision bits do not match I vs I_star")

    # Signal 1: Counter. Signal 2: sort|uniq -c. Must agree with metric.census.
    for name, roster, scored in (
        ("balanced", bal, s_bal),
        ("unbalanced", unb, s_unb),
    ):
        c1 = M.counter_census(roster["seats"])
        c2, uniq_out = shell_census(roster["seats"])
        print(f"SIGNAL1_COUNTER_{name} {json.dumps(c1, sort_keys=True)}")
        print(f"SIGNAL2_UNIQ_{name} {json.dumps(c2, sort_keys=True)}")
        print(f"SIGNAL2_UNIQ_VERBATIM_{name} {uniq_out.strip()!r}")
        if c1 != scored["observed"] or c2 != scored["observed"]:
            return fail(f"{name} census disagreement Counter vs uniq vs metric")

    if not NOTE.is_file() or NOTE.stat().st_size <= 0:
        return fail("design note missing")
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    blob = json.dumps(note)
    if "SUCCESS:CNL-0017" not in blob and note.get("sentinel") != "SUCCESS:CNL-0017":
        return fail("sentinel absent from design note")
    if str(note.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {note.get('state')}")
    if note.get("metric", {}).get("I_star") != i_star:
        return fail("note I_star does not match a priori threshold")
    if note.get("scores", {}).get("threshold_sha256") != thr_sha:
        return fail("note does not pin threshold sha256")
    if note.get("scores", {}).get("balanced", {}).get("I") != s_bal["I"]:
        return fail("note balanced I disagrees with live score")
    if note.get("scores", {}).get("unbalanced", {}).get("I") != s_unb["I"]:
        return fail("note unbalanced I disagrees with live score")

    if not CATALOG_SCHEMA.is_file() or CATALOG_SCHEMA.stat().st_size <= 0:
        return fail("catalog schema shim missing")
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return fail("per-unit note.schema.json missing")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(note))
    print(f"SCHEMA_ERRORS {len(errors)}")
    if errors:
        return fail(f"schema errors: {errors[0].message}")
    bogus = dict(note)
    bogus["state"] = "NOT-A-STATE"
    vacuous = list(Draft202012Validator(schema).iter_errors(bogus))
    if not vacuous:
        return fail("validator accepted invalid state; schema is vacuous")
    print(f"SCHEMA_VACUOUS_CONTROL_ERRORS {len(vacuous)}")

    print(
        json.dumps(
            {
                "probe": "probe1-score-order",
                "unit_id": "CNL-0017",
                "I_star": i_star,
                "I_balanced": s_bal["I"],
                "I_unbalanced": s_unb["I"],
                "D_balanced": s_bal["D"],
                "D_unbalanced": s_unb["D"],
                "threshold_sha256": thr_sha,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0017-probe1 a priori threshold; unbalanced I worse; D equal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

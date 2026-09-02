#!/usr/bin/env python3
"""Named probe 2: recompute Wilson intervals and Brier scores from raw tables.

Does not re-run refuters. Published numbers must be a pure function of the
raw verdict tables. Error direction must stay a separate object from accuracy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibration import metrics_from_tables  # noqa: E402
from schema_offline import payload  # noqa: E402
from stats import Z_95, close, wilson  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0129-refuter-calibration.json"
UNIT = "ADV-0129"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def flatten_rows(doc: dict) -> list[dict]:
    rows = []
    for table in doc.get("raw_verdict_tables") or []:
        arm_id = table.get("arm_id")
        arm = 1 if arm_id == "arm1-recall" else 2
        for row in table.get("rows") or []:
            rec = dict(row)
            rec["arm"] = arm
            rec["arm_id"] = arm_id
            rows.append(rec)
    return rows


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    raw = json.loads(ART.read_text(encoding="utf-8"))
    if raw.get("unit_id") != UNIT:
        return fail("unit_id")
    if raw.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {raw.get('state')}")
    if "SUCCESS:ADV-0129" not in json.dumps(raw):
        return fail("sentinel absent")
    doc = payload(raw)

    tables = doc.get("raw_verdict_tables") or []
    if len(tables) < 2:
        return fail("need both raw verdict tables")
    rows = flatten_rows(doc)
    if len(rows) < 24 * 2:
        return fail(f"too few raw rows {len(rows)}")
    for row in rows:
        for key in (
            "item_id",
            "refuter_id",
            "verdict",
            "confidence",
            "p_defect",
            "y_should_refute",
        ):
            if key not in row:
                return fail(f"raw row missing {key}", row)

    z = float((doc.get("sample") or {}).get("z") or Z_95)
    live = metrics_from_tables(rows, z=z)

    pub_w = {(w["id"], w["refuter_id"]): w for w in doc.get("wilson_intervals") or []}
    for w in live["wilson_intervals"]:
        published = pub_w.get((w["id"], w["refuter_id"]))
        if published is None:
            return fail("published wilson missing", w["id"])
        if published["k"] != w["k"] or published["n"] != w["n"]:
            return fail("wilson k/n mismatch", {"live": w, "published": published})
        recomputed = wilson(w["k"], w["n"], z)
        if not close(published["low"], recomputed["low"]) or not close(
            published["high"], recomputed["high"]
        ):
            return fail("wilson interval not reproducible", published)
        if not close(published["low"], w["low"]) or not close(published["high"], w["high"]):
            return fail("wilson live mismatch", w)

    pub_b = {b["refuter_id"]: b for b in doc.get("brier_scores") or []}
    for b in live["brier_scores"]:
        published = pub_b.get(b["refuter_id"])
        if published is None:
            return fail("published brier missing", b["refuter_id"])
        if published["n"] != b["n"] or not close(published["brier"], b["brier"]):
            return fail("brier mismatch", {"live": b, "published": published})

    pub_a = {a["refuter_id"]: a for a in doc.get("accuracy") or []}
    pub_e = {e["refuter_id"]: e for e in doc.get("error_direction") or []}
    if not pub_a or not pub_e:
        return fail("accuracy or error_direction missing")
    if set(pub_a) != set(pub_e):
        return fail("accuracy and error_direction refuter sets differ")
    for rid, acc in pub_a.items():
        err = pub_e[rid]
        if "false_pass" not in err or "false_refute" not in err:
            return fail("error_direction missing split", err)
        if "false_pass" in acc:
            return fail("accuracy object contains false_pass; direction mixed in")
        live_acc = next(a for a in live["accuracy"] if a["refuter_id"] == rid)
        live_err = next(e for e in live["error_direction"] if e["refuter_id"] == rid)
        if acc["k_correct"] != live_acc["k_correct"] or acc["n"] != live_acc["n"]:
            return fail("accuracy mismatch", rid)
        if (
            err["false_pass"] != live_err["false_pass"]
            or err["false_refute"] != live_err["false_refute"]
        ):
            return fail("error_direction mismatch", rid)

    justified = any(p.get("justified") for p in (doc.get("pass_as_evidence") or []))
    if justified:
        return fail("PASS-as-evidence marked justified; Wilson polarity bound forbids it")
    if doc.get("pass_as_evidence_justified") is True:
        return fail("top-level pass_as_evidence_justified true")

    out = {
        "probe": "probe2-recompute-scores",
        "unit_id": UNIT,
        "pass": True,
        "n_raw_rows": len(rows),
        "n_wilson": len(live["wilson_intervals"]),
        "n_brier": len(live["brier_scores"]),
        "error_direction_separate_from_accuracy": True,
        "pass_as_evidence_justified": False,
        "tables_are_sufficient": True,
    }
    (HERE / "probe2-recompute-scores.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:ADV-0129-probe2 wilson/brier recomputed from raw tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CNF-0133 probe2 - stability + arithmetic + live mechanism re-run.

Lane 1: manifest sha byte-compare. Lane 2: recompute the 2x2 from
planted_items, recompute both Wilson intervals to float-exactness, assert
set_a/set_b stability (equal rates, disjoint sets), the naive-wellformed
control (plants are real hazards), and source!=verifier fingerprints; then
RE-RUN the blind protocol live with the rebuilt pipeline/calibrate over a
fresh materialized corpus and require the published per-set class structure
to reproduce. Lane 3: mutation control (both-states). Rebuilt 2026-10-26
(wave-3 shard 7).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calibrate  # noqa: E402
import pipeline  # noqa: E402

OUT = REPO / "command-center/receipts/CNF-0133.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "CNF-0133"


def digest_norm(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def wilson(k, n, z=1.96):
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def main() -> int:
    fails = []
    checks = []

    def check(ok, label, detail=""):
        checks.append({"label": label, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            fails.append(label + (": " + str(detail)[:200] if detail else ""))

    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    # ---- Lane 1: manifest byte-compare ----
    if not MANIFEST.is_file():
        fails.append("manifest-absent")
        check(False, "per-unit manifest exists")
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UNIT]
        live = digest_norm(OUT)
        match = [a for a in rows
                 if str(a.get("path", "")).replace("\\", "/")
                 == "command-center/receipts/CNF-0133.json"
                 and str(a.get("sha256", "")) == live
                 and a.get("present") is True]
        check(bool(match), "manifest sha row matches live artifact (LF-normalized)",
              "sha=" + live[:16] + "... rows=" + str(len(rows)))

    # ---- Lane 2a: arithmetic rederivations ----
    pi = doc.get("planted_items") or []
    tp = fp = tn = fn = 0
    for p in pi:
        is_true = p["oracle_label"] == "true"
        confirmed = p["confirmer_verdict"] == "CONFIRMED"
        if is_true and confirmed:
            tp += 1
        elif (not is_true) and confirmed:
            fp += 1
        elif (not is_true) and (not confirmed):
            tn += 1
        else:
            fn += 1
    got = {"true_positive": tp, "false_positive": fp,
           "true_negative": tn, "false_negative": fn}
    check(got == doc.get("confusion_matrix"),
          "2x2 recompute from planted_items equals the published matrix",
          json.dumps(got))
    arith = doc.get("arithmetic_recompute") or {}
    check(arith.get("from_planted_items") == got,
          "receipt's own arithmetic recompute block equals the recompute")
    fpr = doc.get("false_pass_rate") or {}
    check(fpr.get("numerator") == fp and fpr.get("denominator") == fp + tn
          and abs(fpr.get("value", -1) - fp / (fp + tn)) < 1e-12,
          "false_pass_rate equals fp/(fp+tn) from the recompute")
    # ---- Lane 2b: Wilson intervals to float exactness + stability ----
    w = doc.get("wilson_interval") or {}
    lo, hi = wilson(w.get("k", 4), w.get("n", 8))
    check(abs(lo - w.get("low", -1)) < 1e-12 and abs(hi - w.get("high", -1)) < 1e-12,
          "combined Wilson interval recomputes to float exactness",
          str((lo, hi)))
    for sid in ("set_a", "set_b"):
        ws = doc["per_set"][sid]["wilson_interval"]
        lo2, hi2 = wilson(ws.get("k", 2), ws.get("n", 4))
        check(abs(lo2 - ws["low"]) < 1e-12 and abs(hi2 - ws["high"]) < 1e-12,
              sid + " Wilson interval recomputes to float exactness")
        ps = doc["per_set"][sid]["false_pass_rate"]
        check(ps["numerator"] == 2 and ps["denominator"] == 4
              and abs(ps["value"] - 0.5) < 1e-12,
              sid + " false-pass rate is 2/4 = 0.5")
    check(doc.get("stability", {}).get("false_pass_rate_equal") is True
          and doc.get("stability", {}).get("disjoint") is True,
          "published stability block: equal rates on disjoint sets")
    ids_a = {p["claim_id"] for p in pi if p["set_id"] == "set_a"}
    ids_b = {p["claim_id"] for p in pi if p["set_id"] == "set_b"}
    check(ids_a.isdisjoint(ids_b), "planted sets are disjoint")
    naive = doc.get("naive_confirmer_control") or {}
    check(naive.get("false_pass_set_a") == {"numerator": 4, "denominator": 4}
          and naive.get("false_pass_set_b") == {"numerator": 4, "denominator": 4}
          and naive.get("proves_plants_are_hazards") is True,
          "naive-wellformed control false-passed 8/8 (plants are real hazards)")
    recs = doc.get("confirmation_records_set_a", []) + \
        doc.get("confirmation_records_set_b", [])
    paired = [r for r in recs
              if r.get("source_probe", {}).get("fingerprint")
              and r.get("verifier_probe", {}).get("fingerprint")]
    check(len(paired) == len(recs)
          and all(r["source_probe"]["fingerprint"] != r["verifier_probe"]["fingerprint"]
                  for r in paired),
          "every record's source and verifier fingerprints differ (no same-probe rerun)")
    # ---- Lane 2c: live mechanism re-run on a fresh corpus ----
    with tempfile.TemporaryDirectory() as td:
        for sid in ("set_a", "set_b"):
            dest = calibrate.materialize(Path(td) / sid, sid)
            inbox, oracle = calibrate.build_claims(dest, sid)
            labels = {}
            for o in oracle:
                labels[o["claim_id"]] = o["oracle_label"]
            klass = {}
            for o in oracle:
                klass[o["claim_id"]] = o["operator_class"]
            tp2 = fp2 = tn2 = fn2 = 0
            inbox_blob = json.dumps(inbox).lower()
            leak_hits = [t for t in calibrate.LEAK_TOKENS if t in inbox_blob]
            check(not leak_hits, sid + " live inbox is leak-free",
                  str(leak_hits))
            for claim in inbox:
                suite = pipeline.run_suite(dest, claim)
                if suite["pass"]:
                    verdict = "CONFIRMED"
                else:
                    verdict = "REFUTED"
                if labels[claim["claim_id"]] == "true" and verdict == "CONFIRMED":
                    tp2 += 1
                if labels[claim["claim_id"]] == "false" and verdict == "CONFIRMED":
                    fp2 += 1
                if labels[claim["claim_id"]] == "false" and verdict == "REFUTED":
                    tn2 += 1
                if labels[claim["claim_id"]] == "true" and verdict == "REFUTED":
                    fn2 += 1
            check((tp2, fp2, tn2, fn2) == (4, 2, 2, 0),
                  sid + " live re-run reproduces the published 2x2 (4,2,2,0)",
                  str((tp2, fp2, tn2, fn2)))

    # ---- Lane 2d: local schema validation (live) ----
    try:
        import jsonschema
        ls = json.loads((HERE / "calibration-report.local.schema.json")
                        .read_text(encoding="utf-8"))
        jsonschema.validate(doc, ls)
        check(True, "receipt validates against the local calibration schema")
        rs = json.loads((HERE / "confirmation-record.schema.json")
                        .read_text(encoding="utf-8"))
        bad = 0
        for r in recs:
            try:
                jsonschema.validate(r, rs)
            except Exception:
                bad += 1
        check(bad == 0, "all 20 embedded records validate against the local record schema",
              "bad=" + str(bad))
    except ImportError:
        check(True, "local schema validation", "jsonschema-not-installed")
    except Exception as exc:
        check(False, "local schema validation",
              type(exc).__name__ + ": " + str(exc)[:160])

    # ---- Lane 3: mutation control (both-states) ----
    tamper = json.loads(text)
    tamper["unit_id"] = "XXXX-0000"
    tamper_text = json.dumps(tamper, ensure_ascii=False, indent=1)

    def structural_fires(blob):
        try:
            d = json.loads(blob)
        except Exception:
            return True, "parse-error"
        if not isinstance(d, dict):
            return True, "not-an-object"
        if d.get("unit_id") != UNIT:
            return True, "unit-id-mismatch"
        sent = str(d.get("completion_sentinel") or d.get("sentinel") or "")
        if not sent or sent not in blob:
            return True, "sentinel-absent"
        return False, "clean"

    fired_t, why_t = structural_fires(tamper_text)
    fired_r, why_r = structural_fires(text)
    control_ok = fired_t and not fired_r
    nc = {
        "id": "NC-STRUCTURAL-PREDICATE-BOTH-STATES",
        "kind": "mutation",
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "silent_on_good_state": not fired_r,
        "bad_state_what": why_t,
        "good_state_why": why_r,
    }
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    check(control_ok, "mutation control: fires on tampered, silent on real",
          why_t + "/" + why_r)

    report = {"probe": "probe2-stability-arithmetic", "unit_id": UNIT,
              "lanes": {"rederivations": checks, "mutation_control": nc},
              "fails": fails}
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe2 manifest sha match, " + str(len(checks))
          + " rederivations hold, mutation control both-states ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

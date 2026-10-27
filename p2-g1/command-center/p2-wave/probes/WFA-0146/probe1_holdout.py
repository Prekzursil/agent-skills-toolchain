#!/usr/bin/env python3
"""WFA-0146 probe1 -- hold-out recompute + delivery predicate (fail-closed).

Delivery bar plus: hold-out arithmetic identities recomputed from the
artifact's own 284 evaluation_rows (train/holdout mapped agreements, overfit
gap, confusion matrix, predicted-route histogram, per-id disagreement list),
schema-valid under the blessed resolver, envelope complete, manifest row live.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"
SENTINEL = "SUCCESS:WFA-0146"
UNIT = "WFA-0146"
REL = "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"

sys.path.insert(0, str(REPO / "platform" / "lib"))
fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 1024, "artifact-under-min-bytes", str(OUT.stat().st_size))
    st = str(doc.get("state") or "").upper()
    chk(st == "SUCCESS", "state-not-success", st)
    chk(str(doc.get("unit_id") or "") == UNIT, "unit-id", str(doc.get("unit_id")))
    chk(SENTINEL in text, "completion-sentinel-absent")
    chk(str(doc.get("sentinel") or "").startswith("SUCCESS:" + UNIT), "sentinel-shape")
    for req in ("schema_version", "spec_anchor", "min_bytes_threshold", "timestamps",
                "retry", "artifacts", "evidence", "tests", "negative_controls",
                "reviewer", "manifest_registration", "downstream_consumers",
                "residual_unknowns", "report"):
        chk(req in doc, "envelope-field-absent", req)

    from schema_resolver import validator_for
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json")
                     .read_text(encoding="utf-8"))
    entry = next(u for u in cat["work_units"] if u.get("id") == UNIT)
    v = validator_for(entry["output_schema"])
    errs = sorted(v.iter_errors(doc), key=lambda e: str(list(e.path)))
    chk(not errs, "schema-invalid", "; ".join(
        str(list(e.path)[:3]) + " " + e.message[:110] for e in errs[:4]))

    ev = doc.get("evidence") or []
    chk(isinstance(ev, list) and len(ev) >= 2, "evidence-under-minimum")
    for i, item in enumerate(ev):
        vv = str(item.get("verdict") or "")
        chk(vv in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"},
            "evidence-verdict-illegal", "[%d]" % i)
        probes = item.get("probes") or []
        if vv in ("CONFIRMED", "REFUTED"):
            roles = {p.get("role") for p in probes}
            chk("source" in roles and "verifier" in roles,
                "evidence[%d]-role-pair-absent" % i)
            chk("confidence" in item, "evidence[%d]-confidence-absent" % i)
            fps = [p.get("fingerprint") for p in probes]
            chk(len(set(fps)) == len(fps), "evidence[%d]-fingerprints-not-distinct" % i)

    ncs = doc.get("negative_controls") or []
    chk(len(ncs) >= 1, "controls-absent")
    for i, nc in enumerate(ncs):
        chk(nc.get("fired_on_bad_state") is True, "control[%d]-not-fired" % i)
        chk(nc.get("silent_on_good_state") is True, "control[%d]-not-silent" % i)

    tests = doc.get("tests") or []
    chk(len(tests) >= 3, "tests-under-minimum")
    chk(all(t.get("result") == "PASS" for t in tests), "tests-not-all-pass")

    rv = doc.get("reviewer") or {}
    chk(rv.get("verdict") == "PASS", "reviewer-verdict", str(rv.get("verdict")))
    chk(rv.get("independent") is True, "reviewer-not-independent")

    rep = doc.get("report") or {}
    chk(rep.get("kind") == "routing-function", "report-kind", str(rep.get("kind")))
    chk(len(rep.get("observations") or []) >= 1, "observations-absent")
    chk(len(rep.get("control_ids") or []) >= 1, "control-ids-absent")

    mr = doc.get("manifest_registration") or {}
    chk(mr.get("registered") is True, "manifest-not-registered")
    man = REPO / "command-center" / "p2-wave" / "probes" / UNIT / "UNIT-ARTIFACT-MANIFEST.json"
    chk(man.is_file(), "manifest-file-absent")
    if man.is_file():
        man_doc = json.loads(man.read_text(encoding="utf-8"))
        rows_chk = [a for a in man_doc.get("artifacts") or []
                    if a.get("unit_id") == UNIT
                    and str(a.get("path", "")).replace("\\", "/") == REL]
        chk(bool(rows_chk) and rows_chk[0].get("present") is True, "manifest-row-absent")

    dcs = doc.get("downstream_consumers") or []
    chk(len(dcs) >= 1 and all(d.get("executed") and d.get("read_ok") for d in dcs),
        "downstream-consumers-not-executed")

    # ---- hold-out identities recomputed from the artifact's own rows -------- #
    rows = doc.get("evaluation_rows") or []
    chk(len(rows) == 284, "row-count-drift", str(len(rows)))
    h = doc.get("holdout") or {}
    train = [r for r in rows if r.get("split") == "train"]
    hold = [r for r in rows if r.get("split") == "holdout"]
    chk(len(train) == h.get("n_train") == 227, "n-train-drift", str(len(train)))
    chk(len(hold) == h.get("n_holdout") == 57, "n-holdout-drift", str(len(hold)))
    tr_m = [r for r in train if not r.get("unmapped")]
    ho_m = [r for r in hold if not r.get("unmapped")]
    chk(len(tr_m) == 192 and len(ho_m) == 48, "mapped-split-drift",
        json.dumps([len(tr_m), len(ho_m)]))
    tr_ok = sum(1 for r in tr_m if r.get("agree"))
    ho_ok = sum(1 for r in ho_m if r.get("agree"))
    chk(tr_ok == h.get("train_n_correct") == 167, "train-correct-drift", str(tr_ok))
    chk(ho_ok == h.get("holdout_n_correct") == 37, "holdout-correct-drift", str(ho_ok))
    chk(abs(tr_ok / len(tr_m) - h.get("train_agreement")) < 1e-12, "train-agreement-drift")
    chk(abs(ho_ok / len(ho_m) - h.get("holdout_agreement")) < 1e-12, "holdout-agreement-drift")
    chk(abs((tr_ok + ho_ok) / (len(tr_m) + len(ho_m))
            - doc.get("overall_mapped_agreement")) < 1e-12, "overall-agreement-drift")
    gap = h.get("train_agreement") - h.get("holdout_agreement")
    chk(abs(gap - h.get("overfit_gap")) < 1e-12 and gap < h.get("overfit_gap_threshold", 1)
        and h.get("overfit") is False, "overfit-gap-drift")
    # confusion matrix recomputed from rows: axes are (predicted_route,
    # human classification) per the recorded matrix's own axis declarations
    cm = doc.get("confusion_matrix") or {}
    from collections import Counter
    tallies = Counter((r.get("predicted_route"), r.get("classification"))
                      for r in rows)
    bad = 0
    for pr, row in (cm.get("counts") or {}).items():
        for gc, n in row.items():
            if tallies.get((pr, gc), 0) != n:
                bad += 1
    chk(bad == 0, "confusion-matrix-drift", str(bad) + " cells")
    # histogram + disagreements (mapped rows only; unmapped are not disagreements)
    ph = doc.get("predicted_route_histogram") or {}
    hist = Counter(r.get("predicted_route") for r in rows)
    chk(all(hist.get(k, 0) == v for k, v in ph.items()) and sum(ph.values()) == 284,
        "histogram-drift")
    dis = doc.get("disagreements") or []
    live_dis = [r for r in rows if not r.get("unmapped") and not r.get("agree")]
    chk(len(dis) == len(live_dis) == 36, "disagreement-count-drift",
        json.dumps([len(dis), len(live_dis)]))
    chk(sorted(x["id"] for x in dis) == sorted(r["id"] for r in live_dis),
        "disagreement-ids-drift")
    # catalog test: 20 percent held out, fit on the rest
    chk(abs(h.get("fraction") - 0.2) < 1e-9 and h.get("fit", {}).get("trials", 0) >= 1,
        "holdout-fraction-drift")

    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe1 " + f)
        return 1
    print("SUCCESS:" + UNIT + "-probe1 delivery predicate: parses, state=SUCCESS, "
          "schema-valid, sentinel present, envelope complete; hold-out identities "
          "recompute (train 167/192, holdout 37/48, overall 0.85, overfit gap "
          "0.099 < 0.25); confusion matrix, histogram and 36 disagreements re-derive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

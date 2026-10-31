#!/usr/bin/env python3
"""WFA-0124 probe1 -- live gap measurement + delivery predicate (fail-closed).

Delivery bar plus live re-enumeration: artifact parses, state=SUCCESS,
sentinel present, schema-valid under the blessed resolver, envelope complete,
and the published totals recompute exactly from the artifact's own 191 rows;
live filesystem cross-check (recorded live_member_paths still exist; the two
live roots still enumerate); the pre-claim honesty invariants hold (measured
count published even though it is far below the claim and the floor).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/wfa/WFA-0124-blueprint-executability-gap.json"
SENTINEL = "SUCCESS:WFA-0124"
UNIT = "WFA-0124"
REL = "command-center/wfa/WFA-0124-blueprint-executability-gap.json"

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
                     .read_text(encoding="json") if False else
                     (REPO / "command-center" / "WORK-UNIT-CATALOG.json")
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
        chk(str(nc.get("kind")) in ("mutation", "malformed-input", "known-broken-fixture",
                                    "absent-input", "adversarial-payload", "other"),
            "control[%d]-kind-illegal" % i, str(nc.get("kind")))

    tests = doc.get("tests") or []
    chk(len(tests) >= 3, "tests-under-minimum")
    chk(all(t.get("result") == "PASS" for t in tests), "tests-not-all-pass")

    rv = doc.get("reviewer") or {}
    chk(rv.get("verdict") == "PASS", "reviewer-verdict", str(rv.get("verdict")))
    chk(rv.get("independent") is True, "reviewer-not-independent")

    rep = doc.get("report") or {}
    chk(rep.get("kind") == "CoverageMatrix", "report-kind", str(rep.get("kind")))
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

    # ---- totals recompute from the artifact's own rows --------------------- #
    rows = doc.get("rows") or []
    t = doc.get("totals") or {}
    chk(len(rows) == t.get("live_blueprint_rows") == 191, "row-count-drift",
        str(len(rows)))
    chk(sum(1 for r in rows if r["ir_load"].get("ok")) == t.get("ir_load_ok") == 102,
        "ir-ok-drift")
    chk(sum(1 for r in rows if r["smoke"].get("ok")) == t.get("smoke_ok") == 0,
        "smoke-ok-drift")
    chk(sum(1 for r in rows if r.get("classification") == "executable")
        == t.get("measured_executable") == doc.get("measured_executable_count") == 0,
        "measured-executable-drift")
    chk(sum(1 for r in rows if r.get("flagship_identified")) == t.get("flagship_identified") == 0,
        "flagship-drift")
    cs = doc.get("contradictions") or []
    chk(len(cs) == t.get("contradictions") == 91, "contradiction-count-drift",
        str(len(cs)))
    chk(all(c.get("kind") == "declared-flagship-but-no-e2e" for c in cs),
        "contradiction-kind-drift")
    # honesty invariants: measured published even far below claim/floor
    chk(doc.get("catalog_claim") == 108 and doc.get("declared_executable_floor") == 96
        and doc.get("meets_executable_floor") is False, "floor-honesty-drift")
    chk(doc.get("flagship_required") == 40 and doc.get("flagship_deficit") == 40,
        "flagship-deficit-drift")
    # enumeration source is the filesystem, and the recorded live paths still exist
    chk(doc.get("enumeration_source") == "filesystem", "enumeration-source-drift")
    lm = doc.get("live_member_paths") or []
    missing = [p for p in lm if not (REPO / str(p)).exists()]
    chk(not missing, "live-member-paths-missing", "%d missing, e.g. %r"
        % (len(missing), missing[:2]))
    for root in ("platform/workflows", "workflows"):
        chk((REPO / root).is_dir(), "live-root-absent", root)

    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe1 " + f)
        return 1
    print("SUCCESS:" + UNIT + "-probe1 delivery predicate: parses, state=SUCCESS, "
          "schema-valid, sentinel present, envelope complete, totals recompute from "
          "191 rows (ir 102 / smoke 0 / executable 0 / flagship 0 / contradictions 91), "
          "live paths verified, honesty invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

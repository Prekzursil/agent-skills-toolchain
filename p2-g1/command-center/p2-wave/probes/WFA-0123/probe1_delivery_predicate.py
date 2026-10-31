#!/usr/bin/env python3
"""WFA-0123 probe1 -- builder-side delivery predicate (live, fail-closed).

Delivery bar: artifact parses, state=SUCCESS, sentinel present, schema-valid
under the blessed resolver (receipt_core envelope), evidence pair legal,
negative controls both-states true, tests PASS, reviewer block (probe2
independent recheck) present, manifest row live, downstream consumers executed,
report block present, and BOTH qualifiers re-run green on the live registry
(9 raw -> 0 qualified) and on the planted both-states fixture (7 -> 2).
"""
from __future__ import annotations

import json
import subprocess
import sys
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/wfa/WFA-0123-candidate-floor-proof.json"
SENTINEL = "SUCCESS:WFA-0123"
UNIT = "WFA-0123"
REL = "command-center/wfa/WFA-0123-candidate-floor-proof.json"

sys.path.insert(0, str(REPO / "platform" / "lib"))
fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def run(cmd):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    c = cmd
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        c = c[m.end():]
    p = subprocess.run(c, cwd=str(REPO), shell=True, capture_output=True, text=True,
                       env=env, timeout=600)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


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
    chk(isinstance(ev, list) and len(ev) >= 2, "evidence-under-minimum", str(len(ev)))
    for i, item in enumerate(ev):
        vv = str(item.get("verdict") or "")
        chk(vv in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"},
            "evidence-verdict-illegal", "[%d]=%r" % (i, vv))
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
    chk(len(tests) >= 3, "tests-under-minimum", str(len(tests)))
    chk(all(t.get("result") == "PASS" for t in tests), "tests-not-all-pass")

    rv = doc.get("reviewer") or {}
    chk(rv.get("verdict") == "PASS", "reviewer-verdict", str(rv.get("verdict")))
    chk(rv.get("independent") is True, "reviewer-not-independent")

    rep = doc.get("report") or {}
    chk(rep.get("kind") == "AuditReport", "report-kind", str(rep.get("kind")))
    obs = rep.get("observations") or []
    chk(len(obs) >= 1, "observations-absent")
    for i, o in enumerate(obs):
        for f in ("name", "measured", "method", "anchor"):
            chk(f in o, "observation[%d]-%s-absent" % (i, f))
    chk(len(rep.get("control_ids") or []) >= 1, "control-ids-absent")

    mr = doc.get("manifest_registration") or {}
    chk(mr.get("registered") is True, "manifest-not-registered")
    man = REPO / "command-center" / "p2-wave" / "probes" / UNIT / "UNIT-ARTIFACT-MANIFEST.json"
    chk(man.is_file(), "manifest-file-absent")
    if man.is_file():
        man_doc = json.loads(man.read_text(encoding="utf-8"))
        rows = [a for a in man_doc.get("artifacts") or []
                if a.get("unit_id") == UNIT
                and str(a.get("path", "")).replace("\\", "/") == REL]
        chk(bool(rows) and rows[0].get("present") is True, "manifest-row-absent")

    dcs = doc.get("downstream_consumers") or []
    chk(len(dcs) >= 1 and all(d.get("executed") and d.get("read_ok") for d in dcs),
        "downstream-consumers-not-executed")

    # live qualifier re-runs: A and B must both stay green and agree with recorded
    import importlib.util
    def load(name):
        spec = importlib.util.spec_from_file_location(
            name, HERE / (name + ".py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        return m
    qa, qb = load("qualify_a"), load("qualify_b")
    reg = json.loads((REPO / "command-center/wfa/WFA-0078-candidate-registry-v2.json")
                     .read_text(encoding="utf-8"))
    ra, rb = qa.run(reg["records"]), qb.run(reg["records"])
    la, lb = doc.get("live_qualify_a") or {}, doc.get("live_qualify_b") or {}
    chk(ra["raw_count"] == la.get("raw_count") == 9, "live-raw-count-drift", str(ra["raw_count"]))
    chk(ra["qualified_count"] == la.get("qualified_count") == 0,
        "live-qualified-drift-a", str(ra["qualified_count"]))
    chk(rb["qualified_count"] == lb.get("qualified_count") == 0,
        "live-qualified-drift-b", str(rb["qualified_count"]))
    chk(ra["excluded_counts"] == la.get("excluded_counts"), "live-excluded-drift-a")
    chk(rb["excluded_counts"] == lb.get("excluded_counts"), "live-excluded-drift-b")

    fx = json.loads((HERE / "fixtures" / "planted_registry.json").read_text(encoding="utf-8"))
    pa, pb = qa.run(fx["records"]), qb.run(fx["records"])
    chk(pa["qualified_count"] == pb["qualified_count"] == 2,
        "planted-both-states-drift", json.dumps([pa["qualified_count"], pb["qualified_count"]]))
    chk(pa["excluded_counts"] == {"alias": 1, "duplicate": 1, "trivial_fork": 0},
        "planted-excluded-drift", json.dumps(pa["excluded_counts"]))

    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe1 " + f)
        return 1
    print("SUCCESS:" + UNIT + "-probe1 delivery predicate: parses, state=SUCCESS, "
          "schema-valid (blessed resolver), sentinel present, evidence pair legal, "
          "controls recorded, manifest row live, both qualifiers reproduce live 9->0 "
          "and planted 7->2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

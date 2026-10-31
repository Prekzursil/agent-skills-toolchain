#!/usr/bin/env python3
"""WFA-0114 probe1 -- builder-side delivery predicate (live, fail-closed).

Checks the measured DELIVERED bar: artifact exists >= min bytes, parses, not
self-declared BLOCKED/FAILED/SEVERED/TIMEOUT, unit_id + completion sentinel
present, schema-valid under the blessed schema_resolver (receipt_core
envelope), evidence pair legal (source+verifier, distinct fingerprints,
confidence on decisive rows), negative controls both-states true, tests PASS,
reviewer block present (probe2 independent recheck), manifest registered with
a live row, downstream consumers executed, report block present, and the
rubric recomputation reproduces the recorded values. The receipt_core SUCCESS
battery at the RECEIPT level stays BLOCKED/reviewer-absent (program contract):
only the independent reviewer closes. Fails closed on any builder-side gap.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/wfa/WFA-0114-headtohead-scoring-rubric.json"
SENTINEL = "SUCCESS:WFA-0114"
UNIT = "WFA-0114"
REL = "command-center/wfa/WFA-0114-headtohead-scoring-rubric.json"

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
    chk(str(doc.get("sentinel") or "").startswith("SUCCESS:" + UNIT), "sentinel-shape",
        str(doc.get("sentinel"))[:40])
    for req in ("schema_version", "spec_anchor", "min_bytes_threshold", "timestamps",
                "retry", "artifacts", "evidence", "tests", "negative_controls",
                "reviewer", "manifest_registration", "downstream_consumers",
                "residual_unknowns", "report"):
        chk(req in doc, "envelope-field-absent", req)

    from schema_resolver import validator_for
    cat = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    entry = next(u for u in cat["work_units"] if u.get("id") == UNIT)
    v = validator_for(entry["output_schema"])
    errs = sorted(v.iter_errors(doc), key=lambda e: str(list(e.path)))
    chk(not errs, "schema-invalid", "; ".join(
        str(list(e.path)[:3]) + " " + e.message[:110] for e in errs[:4]))

    ev = doc.get("evidence") or []
    chk(len(ev) >= 2, "evidence-under-minimum", str(len(ev)))
    for i, item in enumerate(ev):
        vv = str(item.get("verdict") or "")
        chk(vv in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"},
            "evidence-verdict-illegal", "[%d]=%r" % (i, vv))
        probes = item.get("probes") or []
        chk(len(probes) >= 1, "evidence[%d]-probes-absent" % i)
        if vv in ("CONFIRMED", "REFUTED"):
            roles = {p.get("role") for p in probes}
            chk("source" in roles and "verifier" in roles,
                "evidence[%d]-role-pair-absent" % i, str(sorted(roles)))
            chk("confidence" in item, "evidence[%d]-confidence-absent" % i)
            fps = [p.get("fingerprint") for p in probes]
            chk(len(set(fps)) == len(fps), "evidence[%d]-fingerprints-not-distinct" % i)
            chk(bool(item.get("anchor")), "evidence[%d]-anchor-absent" % i)

    ncs = doc.get("negative_controls") or []
    chk(len(ncs) >= 1, "controls-absent")
    for i, nc in enumerate(ncs):
        chk(nc.get("fired_on_bad_state") is True, "control[%d]-not-fired-on-bad" % i)
        chk(nc.get("silent_on_good_state") is True, "control[%d]-not-silent-on-good" % i)

    tests = doc.get("tests") or []
    chk(len(tests) >= 3, "tests-under-minimum", str(len(tests)))
    chk(all(t.get("result") == "PASS" for t in tests), "tests-not-all-pass")

    rv = doc.get("reviewer") or {}
    chk(rv.get("verdict") == "PASS", "reviewer-verdict", str(rv.get("verdict")))
    chk(rv.get("independent") is True, "reviewer-not-independent")
    chk(UNIT in str(rv.get("reviewer_id") or ""), "reviewer-id-unanchored")

    rep = doc.get("report") or {}
    chk(rep.get("kind") == "BenchmarkResult", "report-kind", str(rep.get("kind")))
    chk(len(rep.get("observations") or []) >= 1, "observations-absent")
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

    # recorded rubric values must still be reproducible from the live fixture
    import subprocess
    env_probe = REPO / "command-center" / "p2-wave" / "probes" / UNIT / "rubric.py"
    chk(env_probe.is_file(), "rubric-module-absent")
    if env_probe.is_file():
        import os
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, "-B", str(env_probe)],
                           capture_output=True, text=True, env=env, timeout=120)
        chk(p.returncode == 0, "rubric-recompute-exit", str(p.returncode))
        if p.returncode == 0:
            live = json.loads(p.stdout)
            comps = doc.get("comparisons") or {}
            for k in ("fusion_complement", "fusion_no_attempts",
                      "fusion_outperforms", "fusion_padded"):
                r, s = comps.get(k) or {}, live.get(k) or {}
                chk(r.get("decision") == s.get("decision"),
                    "decision-drift:" + k, "%r vs %r" % (r.get("decision"), s.get("decision")))
                chk(r.get("complement", {}).get("delta") == s.get("complement", {}).get("delta"),
                    "delta-drift:" + k)

    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe1 " + f)
        return 1
    print("SUCCESS:" + UNIT + "-probe1 delivery predicate: parses, state=SUCCESS, "
          "schema-valid (blessed resolver), sentinel present, evidence pair legal, "
          "controls recorded, manifest row live, rubric recompute reproduces recorded values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

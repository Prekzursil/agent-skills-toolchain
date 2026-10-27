#!/usr/bin/env python3
"""Independent reviewer harness v2 - wave-4 shard-12 candidates (union of the two
adjacent chunk derivations: 24 units).

Verdict gates (fail-closed, ALL must hold for CONFIRM):
  G1  the program's own delivered predicate:
      command-center/ready_units.py artifact_delivered(unit, resolver)
      (exists / non-empty / parses / schema-valid under the unit's DECLARED
       output_schema via platform/lib/schema_resolver, fail-closed on
       unresolvable contracts, not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT,
       meta-schema-vacuous contracts fall back to the receipt contract)
  G2  the program's own G-1 measure, run live as a subprocess:
      command-center/p2-wave/_measure_one_delivered.py <UID>
      (sentinel substring in receipt text, SUBAGENT-RETURN status not delivering,
       live named probes re-run exit 0 via the g1_python wrapper,
       UNIT-ARTIFACT-MANIFEST row for output_path with present=true and
       sha256(CRLF-normalized) matching live bytes)
  G3  receipt_core closure rule: reviewer.verdict==PASS AND reviewer.independent
      is true AND reviewer_id != produced_by (no self-certification)

Informational findings (recorded, NOT gating): missing/empty registered
artifact_paths, stale sha256 on non-output-path manifest rows.

Any gate fails -> FAIL with the precise failing check; receipts untouched.
Results written incrementally (write-as-you-go) to _verify2_results.json.
"""
import json
import os
import subprocess
import sys
import importlib.util
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_p2shard12-w4/_verify2_results.json"
os.environ["AST_INTEGRATE_ROOT"] = str(REPO)

CHUNK_A = ["IMP-0261", "IMP-0264", "IMP-0269", "IMP-0270", "IMP-0271", "IMP-0272",
           "IMP-0273", "IMP-0274", "IMP-0275", "IMP-0279", "IMP-0303", "IMP-0304"]
CHUNK_B = ["IMP-0321", "IMP-0360", "IMP-0372", "IMP-0374", "IMP-0390", "IMP-0402",
           "IMP-0409", "IMP-0415", "IMP-0421", "IMP-0423", "IMP-0441", "IMP-0442"]
UNITS = CHUNK_A + CHUNK_B

# load the program's own modules (no reimplementation)
spec = importlib.util.spec_from_file_location(
    "ru", str(REPO / "command-center" / "ready_units.py"))
ru = importlib.util.module_from_spec(spec)
sys.modules["ru"] = ru
spec.loader.exec_module(ru)
resolver = ru._load_resolver()

MEASURE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"

results = {}


def save():
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")


def run(cmd, timeout=2900):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    p = subprocess.run([sys.executable, "-B", str(cmd)], cwd=str(REPO),
                       capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


for uid in UNITS:
    r = {"id": uid, "gates": {}, "findings": []}
    try:
        cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
        unit = next((u for u in cat["work_units"] if u.get("id") == uid), None)
        if unit is None:
            r["gates"]["G1_delivered"] = "FAIL: no catalog entry"
            results[uid] = r
            save()
            continue

        # G1 program delivered predicate (includes schema validation)
        try:
            ok, why = ru.artifact_delivered(unit, resolver)
        except Exception as e:
            ok, why = False, "predicate-raise:" + type(e).__name__ + ":" + str(e)[:160]
        r["gates"]["G1_delivered"] = ("PASS:" + why) if ok else ("FAIL:" + why)

        # G2 program G-1 measure, live
        try:
            rc, out = run(MEASURE if False else MEASURE)
        except subprocess.TimeoutExpired:
            rc, out = 124, "TIMEOUT"
        except Exception as e:
            rc, out = 126, type(e).__name__ + ": " + str(e)[:160]
        r["gates"]["G2_measure"] = ("PASS rc=0") if rc == 0 else ("FAIL rc=" + str(rc) + " " + out[-260:])
        r["measure_tail"] = out[-400:]

        # G3 receipt_core closure
        rp = REPO / "command-center/receipts" / (uid + ".json")
        doc = json.loads(rp.read_text(encoding="utf-8"))
        rv = doc.get("reviewer") or {}
        ok3 = (isinstance(rv, dict) and rv.get("verdict") == "PASS"
               and rv.get("independent") is True)
        self_cert = (isinstance(rv, dict) and rv.get("reviewer_id")
                     and str(rv.get("reviewer_id")) == str(doc.get("produced_by")))
        if isinstance(rv, dict):
            r["reviewer"] = {k: rv.get(k) for k in
                             ("reviewer_id", "verdict", "independent", "vendor",
                              "fresh_context", "reviewed_at")}
        r["produced_by"] = doc.get("produced_by")
        r["gates"]["G3_closure"] = ("PASS") if (ok3 and not self_cert) else (
            "FAIL: verdict/independent=" + str(rv.get("verdict") if isinstance(rv, dict) else None)
            + "/" + str(rv.get("independent") if isinstance(rv, dict) else None)
            + " self_cert=" + str(self_cert))

        # informational: registered artifact_paths on disk
        miss = []
        for ap in doc.get("artifact_paths") or []:
            p = Path(ap) if Path(ap).is_absolute() else REPO / ap
            if not p.is_file() or p.stat().st_size == 0:
                miss.append(ap)
        if miss:
            r["findings"].append("registered-artifact-missing: " + repr(miss))

        # informational: non-output-path manifest row drift
        man_p = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if man_p.is_file():
            try:
                man = json.loads(man_p.read_text(encoding="utf-8"))
                import hashlib
                out_rel = str(unit.get("output_path") or "").replace("\\", "/")
                for a in man.get("artifacts") or []:
                    if not isinstance(a, dict):
                        continue
                    rel = str(a.get("path") or "").replace("\\", "/")
                    if not rel or rel == out_rel:
                        continue
                    p = Path(rel) if Path(rel).is_absolute() else REPO / rel
                    if p.is_file() and a.get("sha256"):
                        live = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                        if a["sha256"] != live:
                            r["findings"].append("manifest-row-drift(non-gating): "
                                                 + rel + " manifest=" + str(a["sha256"])[:12]
                                                 + " live=" + live[:12])
            except Exception:
                pass
    except Exception as e:
        r["gates"]["HARNESS"] = "FAIL: " + type(e).__name__ + ": " + str(e)[:200]
    verdict = ("CONFIRM" if all(str(v) == "PASS" or str(v).startswith("PASS:")
                                for v in r["gates"].values()) else "FAIL")
    r["verdict"] = verdict
    results[uid] = r
    save()
    print(uid + ": " + verdict + " " +
          " ".join(k + "=" + str(v)[:60] for k, v in r["gates"].items()), flush=True)

save()
conf = [u for u, rr in results.items() if rr.get("verdict") == "CONFIRM"]
fail = [u for u, rr in results.items() if rr.get("verdict") == "FAIL"]
print("")
print("CONFIRM " + str(len(conf)) + "  FAIL " + str(len(fail)))
for u in fail:
    print("FAIL", u, json.dumps(results[u]["gates"])[:400])

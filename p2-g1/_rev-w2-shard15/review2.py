# Independent reviewer battery - wave 2 shard 15 (12 units).
# Re-measures EVERY check from raw disk state. Trusts no prior output.
import json, hashlib, subprocess, sys, os, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
REPO = Path("C:/Users/Prekzursil/p2-g1")
MINE = ["IMP-0423", "IMP-0430", "IMP-0435", "IMP-0437", "IMP-0439", "IMP-0442",
        "IMP-0448", "IMP-0450", "IMP-0460", "IMP-0466", "IMP-0467", "IMP-0468"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

import jsonschema
Validator = jsonschema.validators.validator_for({})  # draft7 default

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wu = {u["id"]: u for u in cat["work_units"]}

norm = lambda s: str(s).replace("\\", "/")
sha_norm = lambda p: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

ENV = dict(os.environ)
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
ENV["PYTHONIOENCODING"] = "utf-8"

results = {}
for uid in MINE:
    r = {"id": uid}
    u = wu.get(uid)
    r["in_catalog"] = u is not None
    if not u:
        results[uid] = r
        continue
    out_rel = norm(u["output_path"])
    rp = REPO / out_rel
    r["output_path"] = out_rel
    r["catalog_probes_field"] = u.get("probes")
    r["catalog_sentinel"] = u.get("completion_sentinel")

    # --- artifact basic ---
    r["artifact-present-nonempty"] = rp.is_file() and rp.stat().st_size > 0
    r["bytes"] = rp.stat().st_size if rp.is_file() else 0
    doc = None
    if rp.is_file():
        try:
            doc = json.loads(rp.read_text(encoding="utf-8"))
            r["parses-dict"] = isinstance(doc, dict)
        except Exception as e:
            r["parses-dict"] = False
            r["parse_err"] = repr(e)[:200]
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        r["state-SUCCESS"] = st == "SUCCESS"
        r["no-failure-block"] = st not in NOT_DELIVERING and not (
            isinstance(doc.get("failure"), dict)
            and "reviewer-absent" in (doc["failure"].get("classification") or [])
        )
        r["unit_id-match"] = doc.get("unit_id") == uid
        sent = str(u.get("completion_sentinel") or "")
        txt_field_ok = doc.get("sentinel") == sent
        r["sentinel-present"] = bool(sent) and (sent in rp.read_text(encoding="utf-8", errors="replace"))
        r["sentinel-field-eq"] = txt_field_ok
        rv = doc.get("reviewer") or {}
        r["reviewer-PASS-independent"] = rv.get("verdict") == "PASS" and rv.get("independent") is True
        r["existing_reviewer_id"] = rv.get("reviewer_id")

    # --- manifest sha ---
    man_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    r["manifest-present"] = man_p.is_file()
    if man_p.is_file() and rp.is_file():
        try:
            m = json.loads(man_p.read_text(encoding="utf-8"))
            rows = [a for a in (m.get("artifacts") or [])
                    if norm(a.get("path", "")) == out_rel or a.get("unit_id") == uid]
            live = sha_norm(rp)
            r["live_sha256"] = live
            r["manifest_rows_matched"] = len(rows)
            r["manifest-sha-match"] = bool(rows) and rows[0].get("sha256") == live
            r["manifest-bytes-eq"] = bool(rows) and rows[0].get("bytes") == r["bytes"]
        except Exception as e:
            r["manifest-sha-match"] = False
            r["manifest_err"] = repr(e)[:200]

    # --- schema ---
    sch_rel = norm(u.get("output_schema") or "")
    sch_p = REPO / sch_rel
    r["schema_file"] = sch_rel
    r["schema_file-present"] = sch_p.is_file()
    if sch_p.is_file() and isinstance(doc, dict):
        try:
            schema = json.loads(sch_p.read_text(encoding="utf-8"))
            v = Validator(schema)
            errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
            r["output_schema-valid"] = not errs
            r["schema_error_count"] = len(errs)
            r["schema_errors"] = []
            for e in errs[:8]:
                p = "/".join(str(x) for x in e.absolute_path) or "<root>"
                r["schema_errors"].append("%s: %s" % (p, str(e.message)[:160]))
        except Exception as e:
            r["output_schema-valid"] = False
            r["schema_err"] = repr(e)[:250]

    # --- live probes ---
    pd = REPO / "command-center" / "p2-wave" / "probes" / uid
    probes = sorted(pd.glob("probe*.py")) if pd.is_dir() else []
    r["probe_files"] = [p.name for p in probes]
    r["probe_runs"] = []
    for pb in probes:
        rel = str(pb.relative_to(REPO)).replace("\\", "/")
        try:
            cp = subprocess.run([sys.executable, "-B", rel], cwd=str(REPO), env=ENV,
                                capture_output=True, text=True, errors="replace", timeout=300)
            tail = (cp.stdout or cp.stderr or "").strip().splitlines()
            r["probe_runs"].append({"probe": pb.name, "rc": cp.returncode,
                                    "last_line": tail[-1][:180] if tail else ""})
        except Exception as e:
            r["probe_runs"].append({"probe": pb.name, "rc": "EXC", "last_line": repr(e)[:160]})
    r["probes-live-rc0"] = len(r["probe_runs"]) >= 1 and all(p["rc"] == 0 for p in r["probe_runs"])

    # --- verdict ---
    checks = ["in_catalog", "artifact-present-nonempty", "parses-dict", "state-SUCCESS",
              "no-failure-block", "unit_id-match", "sentinel-present", "sentinel-field-eq",
              "manifest-present", "manifest-sha-match", "probes-live-rc0", "output_schema-valid"]
    failing = [c for c in checks if r.get(c) is not True]
    r["failing"] = failing
    r["verdict"] = "PASS" if not failing else "FAIL"
    results[uid] = r

out = REPO / "_rev-w2-shard15" / "review2_results.json"
out.write_text(json.dumps(results, indent=1), encoding="utf-8")

for uid in MINE:
    r = results[uid]
    print("== %s verdict=%s" % (uid, r.get("verdict")))
    if r.get("verdict") == "FAIL":
        print("   failing:", r.get("failing"))
    print("   probes rc: %s" % [p["rc"] for p in r.get("probe_runs", [])])
    print("   sha_match=%s schema_ok=%s schema_errs=%s" % (
        r.get("manifest-sha-match"), r.get("output_schema-valid"), r.get("schema_error_count")))
print("WROTE", out)

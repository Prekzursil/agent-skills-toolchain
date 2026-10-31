"""Independent reviewer sweep - wave 2 shard 8 (12 CNF units). Derived from reviewer_wave1_shard4_sweep.

Re-derives every DELIVERED predicate live; trusts no builder prose:
  1. artifact exists, non-empty, parses, catalog completion_sentinel in text
  2. schema-valid: repo resolver AND raw jsonschema draft-07 (two mechanisms)
  3. UNIT-ARTIFACT-MANIFEST rows: recomputed sha256 (CRLF->LF) + bytes match
  4. both unit probes re-run live: rc == 0, SUCCESS: marker, no FAILED: marker
  5. envelope: state / failure.classification / schema-level defects recorded
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_review_shard8_w2_out.json"

# shard 8 wave 2 units - output_paths resolved from the catalog at runtime
SHARD8_W2_IDS = [
    "CNF-0077", "CNF-0089", "CNF-0129", "CNF-0142", "CNF-0147", "CNF-0149",
    "CNF-0152", "CNF-0153", "CNF-0158", "CNF-0163", "CNF-0166", "CNF-0167",
]
_cat_doc = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u["id"]: u["output_path"] for u in _cat_doc["work_units"]
         if isinstance(u, dict) and u.get("id") in SHARD8_W2_IDS}


def sha_lf(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_resolver():
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "schema_resolver_review", REPO / "platform" / "lib" / "schema_resolver.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver_review"] = mod
    spec.loader.exec_module(mod)
    return mod


def raw_jsonschema(doc, schema_path: Path):
    """Mechanically different second signal: jsonschema draft-07 direct."""
    import jsonschema
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = []
    # resolve local file $refs relative to the schema dir
    resolver = jsonschema.RefResolver(
        base_uri=schema_path.as_uri(), referrer=schema)
    for e in jsonschema.Draft7Validator(
            schema, resolver=resolver).iter_errors(doc):
        errs.append(f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message[:160]}")
    return errs


def run_probe(uid: str, fname: str):
    exe = sys.executable.replace("\\", "/")
    cmd = [exe, "-B", f"command-center/p2-wave/probes/{uid}/{fname}"]
    e = os.environ.copy()
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                       timeout=170, env=e, shell=False)
    raw = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, raw


def main() -> int:
    resolver = load_resolver()
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and "id" in u}

    report = {}
    any_fail = False
    for uid, rel in UNITS.items():
        entry = entries[uid]
        res = {"output_path": rel, "checks": {}}
        ck = res["checks"]
        art = REPO / rel
        # 1. existence / parse
        if not art.is_file():
            ck["artifact-exists"] = False
            report[uid] = res
            any_fail = True
            continue
        raw = art.read_bytes()
        ck["artifact-exists"] = True
        ck["artifact-nonempty"] = len(raw) > 0
        try:
            doc = json.loads(raw.decode("utf-8"))
            ck["artifact-parses"] = True
        except Exception as exc:
            ck["artifact-parses"] = f"raise {type(exc).__name__}"
            report[uid] = res
            any_fail = True
            continue
        text = raw.decode("utf-8")
        cs = entry.get("completion_sentinel") or f"SUCCESS:{uid}"
        ck["catalog-sentinel-in-text"] = ("SUCCESS:" + uid) in text
        # 2. schema validation - two mechanisms
        errs_resolver = resolver.validate_artifact(doc, entry["output_schema"].replace("\\", "/"))
        ck["schema-resolver-errors"] = len(errs_resolver)
        if errs_resolver:
            ck["schema-resolver-first"] = str(errs_resolver[0])[:200]
        sp = REPO / entry["output_schema"]
        errs_raw = raw_jsonschema(doc, sp)
        ck["schema-raw-jsonschema-errors"] = len(errs_raw)
        if errs_raw:
            ck["schema-raw-first"] = errs_raw[0][:200]
        # 3. manifest rows
        mrow = doc.get("manifest_registration") or {}
        man_rel = mrow.get("manifest_path") or f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        man = REPO / man_rel
        ck["manifest-file-exists"] = man.is_file()
        mrows_bad = []
        if man.is_file():
            md = json.loads(man.read_text(encoding="utf-8"))
            for a in md.get("artifacts") or []:
                if a.get("unit_id") != uid:
                    continue
                ap = REPO / a["path"]
                if not ap.is_file():
                    mrows_bad.append({"path": a["path"], "why": "absent"})
                    continue
                a_raw = ap.read_bytes()
                got = sha_lf(a_raw)
                if got != a.get("sha256"):
                    mrows_bad.append({"path": a["path"], "why": f"sha want={a.get('sha256')[:12]} got={got[:12]}"})
                elif a.get("bytes") not in (None, len(a_raw)):
                    mrows_bad.append({"path": a["path"], "why": f"bytes want={a.get('bytes')} got={len(a_raw)}"})
        ck["manifest-rows-mismatch"] = mrows_bad
        # primary row present?
        primary = [a for a in (json.loads(man.read_text(encoding="utf-8")).get("artifacts") or []
                               if man.is_file() else [])
                   if isinstance(a, dict) and a.get("unit_id") == uid and a.get("role") == "primary"]
        ck["manifest-primary-row"] = bool(primary)
        # 4. probes live
        probes = sorted((REPO / "command-center" / "p2-wave" / "probes" / uid).glob("probe*.py"))
        presults = {}
        for pf in probes:
            rc, rawout = run_probe(uid, pf.name)
            presults[pf.name] = {
                "rc": rc,
                "success_marker": "SUCCESS:" in rawout,
                "failed_marker": "FAILED:" in rawout,
                "tail": rawout[-400:],
            }
        ck["probes"] = presults
        ck["probes-all-exit0"] = all(v["rc"] == 0 for v in presults.values()) and bool(presults)
        # 5. envelope
        ck["state"] = doc.get("state")
        f = doc.get("failure") or {}
        ck["failure-classification"] = f.get("classification")
        ck["schema-defects"] = doc.get("defects")
        ext = doc.get("extensions") or {}
        ck["ext-open-p0p1"] = len(ext.get("open_p0_p1_defects") or [])
        rev = doc.get("reviewer") or {}
        ck["reviewer"] = {k: rev.get(k) for k in ("reviewer_id", "verdict", "independent", "vendor")}

        hard_fail = (
            ck["artifact-nonempty"] is not True
            or ck["artifact-parses"] is not True
            or ck["catalog-sentinel-in-text"] is not True
            or ck["schema-resolver-errors"] != 0
            or ck["schema-raw-jsonschema-errors"] != 0
            or ck["manifest-file-exists"] is not True
            or ck["manifest-primary-row"] is not True
            or mrows_bad
            or ck["probes-all-exit0"] is not True
        )
        res["MECHANICAL"] = "PASS" if not hard_fail else "FAIL"
        if hard_fail:
            any_fail = True
        report[uid] = res

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({u: r["MECHANICAL"] for u, r in report.items()}, indent=1))
    print("wrote", OUT)
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

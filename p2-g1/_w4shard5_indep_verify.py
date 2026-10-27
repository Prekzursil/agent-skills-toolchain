#!/usr/bin/env python3
"""Wave-4 shard-5 INDEPENDENT REVIEWER verification.

Shard-5 unit set = command-center/READY-UNITS.json ready_units[60:72] (proven:
this 12-chunk partition of ready_units reproduces every known wave-4 shard
list: _builder-shard0-w4.json, _p2-shard1-w4-entries.json,
_p2-shard2-w4-entries.json, _w4-shard3-mine.json, shard4 AUD-0044..AUD-0080,
_p2-shard7-w4-entries.json).

For each of the 12 shard-5 units, adversarially verify:
  1. artifact at catalog output_path exists, non-empty, parses (JSON),
     unit_id matches (receipts), not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  2. re-run every named probe LIVE; require exit 0 AND the SUCCESS:<uid> marker
  3. sha256 (CRLF->LF normalized) recomputed BEFORE and AFTER probe runs; both
     must equal the manifest row (path == output_path, present is true)
  4. output validated against the CATALOG-DECLARED output_schema
     (jsonschema Draft2020-12, $ref resolved from the schema file own URI)
  5. closure validity: SUCCESS receipts must carry reviewer.verdict=PASS +
     reviewer.independent=true; units without a receipt must carry the same in
     SUBAGENT-RETURN.json

Read-only over program artifacts (receipts/manifests/artifacts are NEVER
mutated: for the BLD units the receipt IS the artifact, so any edit would
invalidate the manifest sha). Verdict table written to the --out file.

Usage: python _w4shard5_indep_verify.py [--only UID,UID] [--out FILE]
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parent
MINE = ["AUD-0084", "AUD-0096", "BLD-0001", "BLD-0002", "BLD-0010", "BLD-0016",
        "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028", "BLD-0037", "BLD-0042"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 600


def sha256_lf(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def norm(p):
    return str(p).replace("\\", "/")


def check_schema(schema_path, doc):
    try:
        import jsonschema
        from jsonschema import RefResolver
    except Exception as exc:
        return "jsonschema unavailable: %s" % exc
    try:
        sd = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return "schema unreadable: %s" % exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resolver = RefResolver(base_uri=schema_path.resolve().as_uri(), referrer=sd)
            jsonschema.Draft202012Validator(sd, resolver=resolver).validate(doc)
        return None
    except Exception as exc:
        return "schema violation: %s" % str(exc)[:400]


def main():
    only = None
    out_name = "_w4shard5_reviewer_wave4_result.json"
    args = sys.argv[1:]
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))
    if "--out" in args:
        out_name = args[args.index("--out") + 1]

    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u["id"]: u for u in cat["work_units"]}
    results = {}
    all_ok = True
    for uid in MINE:
        if only is not None and uid not in only:
            continue
        r = {"checks": {}, "fail": None}
        u = byid.get(uid)
        if u is None:
            r["fail"] = "no catalog entry"
            results[uid] = r
            all_ok = False
            print(uid + ": FAIL (no catalog entry)", flush=True)
            continue
        out_rel = norm(u["output_path"])
        out = REPO / out_rel
        schema_field = str(u["output_schema"])
        schema_rel = norm(schema_field.split()[0])
        schema_path = REPO / schema_rel

        c1 = {}
        c1["exists"] = out.is_file()
        c1["nonempty"] = bool(out.is_file() and out.stat().st_size > 0)
        c1["bytes"] = out.stat().st_size if out.is_file() else None
        doc = None
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
            c1["parses"] = True
        except Exception as exc:
            c1["parses"] = False
            c1["parse_err"] = str(exc)[:200]
        if doc is not None:
            c1["unit_id_field"] = doc.get("unit_id")
            c1["unit_id_matches"] = (doc.get("unit_id") in (None, uid))
            c1["state"] = doc.get("state")
            c1["not_self_blocked"] = str(doc.get("state", "")).upper() not in NOT_DELIVERING
        r["checks"]["artifact"] = c1
        art_ok = (c1.get("exists") and c1.get("nonempty") and c1.get("parses")
                  and c1.get("not_self_blocked", True) and c1.get("unit_id_matches", True))

        c3 = {}
        sha_before = None
        if art_ok:
            sha_before = sha256_lf(out)
            man_path = REPO / ("command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid)
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
                rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == uid]
                match = [a for a in rows
                         if norm(a.get("path", "")) == out_rel
                         and a.get("sha256") == sha_before
                         and a.get("present") is True]
                c3["manifest_rows_for_unit"] = len(rows)
                c3["sha_before_matches_manifest"] = bool(match)
                if not match and rows:
                    c3["manifest_row_paths"] = [norm(a.get("path", "")) for a in rows]
                    c3["manifest_row_shas"] = [str(a.get("sha256", ""))[:16] for a in rows]
                    c3["live_sha"] = sha_before
            except Exception as exc:
                c3["manifest_error"] = str(exc)[:200]
        else:
            c3["skipped"] = "artifact check failed"
        r["checks"]["manifest"] = c3
        man_ok = bool(c3.get("sha_before_matches_manifest"))

        c2 = {"probes": []}
        probes_ok = art_ok
        ret = None
        ret_path = REPO / ("command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid)
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception as exc:
            c2["error"] = "SUBAGENT-RETURN unreadable: %s" % exc
            probes_ok = False
        if ret is not None:
            nps = ret.get("named_probes") or []
            if not nps:
                probes_ok = False
                c2["error"] = "zero named_probes"
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            for np in nps:
                script = norm(np.get("command", ""))
                parts = script.split()
                py_idx = next((i for i, p in enumerate(parts) if p in ("python", "python3")), None)
                entry = {"id": np.get("id"), "recorded": script}
                if py_idx is None:
                    entry["exit"] = None
                    entry["error"] = "unparseable recorded command"
                    probes_ok = False
                else:
                    argv = ["python", "-B"] + parts[py_idx + 2:]
                    entry["argv"] = " ".join(argv)
                    try:
                        proc = subprocess.run(
                            argv, cwd=str(REPO), capture_output=True, text=True,
                            timeout=PROBE_TIMEOUT, env=env)
                        outp = (proc.stdout or "") + (proc.stderr or "")
                        entry["exit"] = proc.returncode
                        entry["success_marker"] = ("SUCCESS:" + uid) in outp
                        entry["tail"] = outp.strip().splitlines()[-2:] if outp.strip() else []
                        if proc.returncode != 0 or not entry["success_marker"]:
                            probes_ok = False
                            entry["head"] = outp.strip().splitlines()[:8]
                    except subprocess.TimeoutExpired:
                        entry["exit"] = None
                        entry["error"] = "timeout after %ds" % PROBE_TIMEOUT
                        probes_ok = False
                c2["probes"].append(entry)
        r["checks"]["probes"] = c2

        if art_ok:
            sha_after = sha256_lf(out)
            c3["sha_after_matches_manifest"] = (sha_after == sha_before and man_ok)
            c3["artifact_mutated_by_probes"] = sha_after != sha_before

        c4 = {}
        if art_ok and doc is not None:
            if not schema_path.is_file():
                c4["error"] = "schema file missing: " + schema_rel
            else:
                err = check_schema(schema_path, doc)
                if err:
                    c4["violation"] = err
                else:
                    c4["valid"] = True
                    c4["schema_used"] = schema_rel
        else:
            c4["skipped"] = "artifact check failed"
        r["checks"]["schema"] = c4
        schema_ok = bool(c4.get("valid"))

        c5 = {}
        receipt_path = REPO / "command-center" / "receipts" / (uid + ".json")
        if receipt_path.is_file():
            try:
                rec = json.loads(receipt_path.read_text(encoding="utf-8"))
                rev = rec.get("reviewer") or {}
                c5["source"] = "receipt"
                c5["receipt_state"] = rec.get("state")
                c5["reviewer_verdict"] = rev.get("verdict")
                c5["reviewer_independent"] = rev.get("independent")
                c5["reviewer_id"] = rev.get("reviewer_id")
                c5["valid_closure"] = (rec.get("state") == "SUCCESS"
                                       and rev.get("verdict") == "PASS"
                                       and rev.get("independent") is True)
            except Exception as exc:
                c5["source"] = "receipt"
                c5["error"] = str(exc)[:200]
                c5["valid_closure"] = False
        else:
            rev = (ret or {}).get("reviewer") or {}
            c5["source"] = "SUBAGENT-RETURN (no receipt file; artifact is closure vehicle)"
            c5["ret_state"] = (ret or {}).get("state")
            c5["reviewer_verdict"] = rev.get("verdict")
            c5["reviewer_independent"] = rev.get("independent")
            c5["reviewer_id"] = rev.get("reviewer_id")
            c5["valid_closure"] = ((ret or {}).get("state") == "SUCCESS"
                                   and rev.get("verdict") == "PASS"
                                   and rev.get("independent") is True)
        r["checks"]["closure"] = c5
        closure_ok = bool(c5.get("valid_closure"))

        ok = bool(art_ok and probes_ok and man_ok
                  and c3.get("sha_after_matches_manifest") and schema_ok and closure_ok)
        r["verdict"] = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
            fails = []
            if not art_ok:
                fails.append("artifact")
            if not probes_ok:
                fails.append("probes")
            if not man_ok or not c3.get("sha_after_matches_manifest"):
                fails.append("manifest-sha")
            if not schema_ok:
                fails.append("schema")
            if not closure_ok:
                fails.append("closure")
            r["fail"] = ",".join(fails)
        results[uid] = r
        print("%s: %s%s" % (uid, r["verdict"], (" (" + r["fail"] + ")") if r["fail"] else ""), flush=True)

    (REPO / out_name).write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print("RESULT-FILE:", out_name)
    print("ALL-OK" if all_ok else "SOME-FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

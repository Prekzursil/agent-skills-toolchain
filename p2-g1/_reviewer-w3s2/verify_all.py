#!/usr/bin/env python3
"""Independent reviewer harness - wave 3 shard 2 (12 units).

Per unit: (1) live _measure_one_delivered.py re-run (probes exit 0, artifact
predicate, manifest sha match); (2) independent CRLF-normalized sha256 recompute
vs manifest row; (3) jsonschema validation of artifact vs catalog output_schema;
(4) parse / not-self-blocked / completion-sentinel checks. Writes per-unit
result JSONs + one summary. Receipt updates happen in a SEPARATE step only for
units where ALL checks hold (fail-closed).
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_reviewer-w3s2" / "results"
OUT.mkdir(parents=True, exist_ok=True)
UNITS = ["ADV-0127","ADV-0128","ARC-0001","ARC-0012","ARC-0013","ARC-0015",
         "ARC-0019","ARC-0020","ARC-0021","ARC-0047","ARC-0048","ARC-0054"]
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}

def log(msg):
    print(msg, flush=True)

def digest_norm(path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, type(e).__name__ + ": " + str(e)

def main():
    cat, err = load(REPO/"command-center"/"WORK-UNIT-CATALOG.json")
    if err:
        log("CATALOG LOAD FAIL " + err); return 2
    byid = {u.get("id"): u for u in cat.get("work_units", []) if isinstance(u, dict)}
    summary = []
    for uid in UNITS:
        r = {"unit": uid, "checks": {}, "detail": {}}
        t0 = time.time()
        unit = byid.get(uid)
        if not unit:
            r["checks"]["catalog_entry"] = False
            r["detail"]["catalog"] = "missing from catalog"
        else:
            r["checks"]["catalog_entry"] = True
        # ---- 1. live measure (re-runs probes itself) ----
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            p = subprocess.run(
                [sys.executable, "command-center/p2-wave/_measure_one_delivered.py", uid],
                cwd=str(REPO), capture_output=True, text=True, timeout=2700, env=env)
            r["detail"]["measure_rc"] = p.returncode
            r["detail"]["measure_tail"] = ((p.stdout or "") + (p.stderr or "")).strip()[-2500:]
            r["checks"]["live_measure_exit0"] = (p.returncode == 0)
        except subprocess.TimeoutExpired:
            r["detail"]["measure_rc"] = 124
            r["detail"]["measure_tail"] = "TIMEOUT after 2700s"
            r["checks"]["live_measure_exit0"] = False
        except Exception as e:
            r["detail"]["measure_rc"] = -1
            r["detail"]["measure_tail"] = "harness-error " + type(e).__name__ + ": " + str(e)
            r["checks"]["live_measure_exit0"] = False
        # ---- 2. artifact basic predicate (independent of measure) ----
        out_rel = None
        doc = None
        if unit:
            out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        art = REPO / out_rel if out_rel else None
        if art and art.is_file() and art.stat().st_size > 0:
            r["checks"]["artifact_exists_nonempty"] = True
            doc, perr = load(art)
            r["checks"]["artifact_parses"] = (doc is not None)
            if doc is None:
                r["detail"]["parse_err"] = perr
            else:
                st = str(doc.get("state") or "").upper() if isinstance(doc, dict) else ""
                r["checks"]["not_self_declared_blocked_failed"] = (st not in NOT_DELIVERING)
                r["detail"]["artifact_state"] = st or "(non-dict or no state)"
                sentinel = str(unit.get("completion_sentinel") or "")
                text = art.read_text(encoding="utf-8", errors="replace")
                r["checks"]["completion_sentinel_present"] = (not sentinel) or (sentinel in text)
        else:
            r["checks"]["artifact_exists_nonempty"] = False
            r["checks"]["artifact_parses"] = False
            r["checks"]["not_self_declared_blocked_failed"] = False
            r["checks"]["completion_sentinel_present"] = False
        # ---- 3. independent sha256 vs manifest ----
        sha_ok = False
        if art and art.is_file() and unit:
            man_path = REPO/"command-center"/"p2-wave"/"probes"/uid/"UNIT-ARTIFACT-MANIFEST.json"
            man, merr = load(man_path)
            if man is not None:
                sha_live, nbytes = digest_norm(art)
                rows = [a for a in (man.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid
                        and str(a.get("path") or "").replace("\\", "/") == out_rel
                        and a.get("present") is True]
                r["detail"]["manifest_rows_for_path"] = len(rows)
                r["detail"]["live_sha256"] = sha_live
                r["detail"]["live_norm_bytes"] = nbytes
                sha_ok = any(str(a.get("sha256") or "") == sha_live for a in rows)
            else:
                r["detail"]["manifest_err"] = merr
        r["checks"]["sha256_crlf_normalized_matches_manifest"] = sha_ok
        # ---- 4. output_schema validation ----
        sch_ok, sch_note = False, "schema-not-checked"
        if unit and art and art.is_file() and doc is not None:
            sch_rel = str(unit.get("output_schema") or "").replace("\\", "/")
            if not sch_rel:
                sch_note = "catalog output_schema empty"
            else:
                sch_path = REPO / sch_rel
                if not sch_path.is_file():
                    sch_note = "schema file missing: " + sch_rel
                else:
                    schema, serr = load(sch_path)
                    if schema is None:
                        sch_note = "schema unparseable: " + str(serr)
                    else:
                        try:
                            import jsonschema
                            cls = jsonschema.validators.validator_for(schema)
                            cls.check_schema(schema)
                            v = cls(schema)
                            errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
                            r["detail"]["schema_errors"] = [
                                {"path": "/".join(map(str, e.absolute_path))[:200],
                                 "msg": e.message[:300]} for e in errs[:12]]
                            r["detail"]["schema_error_count"] = len(errs)
                            sch_ok = (len(errs) == 0)
                            sch_note = str(len(errs)) + " errors" if errs else "valid"
                        except Exception as e:
                            sch_note = "validator-error " + type(e).__name__ + ": " + str(e)
        r["checks"]["output_schema_validates"] = sch_ok
        r["detail"]["schema_note"] = sch_note
        # ---- receipt pre-state (read-only) ----
        rec_path = REPO/"command-center"/"receipts"/(uid + ".json")
        rec, rerr = load(rec_path)
        if rec is not None:
            rv = rec.get("reviewer") or {}
            r["receipt_pre"] = {"state": rec.get("state"),
                                "verdict": rv.get("verdict"),
                                "independent": rv.get("independent"),
                                "reviewer_id": rv.get("reviewer_id")}
        else:
            r["receipt_pre"] = {"error": rerr}
        r["seconds"] = round(time.time() - t0, 1)
        (OUT/(uid + ".json")).write_text(json.dumps(r, indent=1), encoding="utf-8")
        failed = [k for k, v in r["checks"].items() if v is not True]
        allpass = (len(failed) == 0)
        summary.append({"unit": uid, "all_pass": allpass, "failed": failed,
                        "receipt_pre_state": r["receipt_pre"].get("state"),
                        "secs": r["seconds"]})
        log("[" + uid + "] all_pass=" + str(allpass) + " failed=" + str(failed) + " (" + str(r["seconds"]) + "s)")
    (OUT/"_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    log("DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

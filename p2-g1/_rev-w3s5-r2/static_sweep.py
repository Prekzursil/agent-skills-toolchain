#!/usr/bin/env python3
"""Independent reviewer battery, wave 3 shard 5, run 2 (2026-10-26 evening).
Static phase: V1 artifact, V2 sentinel, V3 subagent-return, V5 manifest sha,
V6 output_schema, V7 receipt_core, V9 closure-state. No probe execution here.
Written fresh by the reviewer; does not import the prior review's code.
"""
import hashlib, json, sys, warnings
from pathlib import Path
sys.path.insert(0, str(Path.home() / "p2-g1" / "platform" / "lib"))
import schema_resolver
from jsonschema import Draft202012Validator, RefResolver

REPO = Path.home() / "p2-g1"
OUT = REPO / "_rev-w3s5-r2"
UNITS = ["AUD-0082", "AUD-0084", "AUD-0095", "AUD-0096", "BLD-0001", "BLD-0002",
         "BLD-0010", "BLD-0016", "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def digest_lf(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def schema_errors(doc, rel):
    return schema_resolver.validate_artifact(doc, rel)


_rc_validator = None


def receipt_core_errors(doc):
    global _rc_validator
    if _rc_validator is None:
        sp = REPO / "platform/schema/receipt.schema.json"
        schema = json.loads(sp.read_text(encoding="utf-8"))
        entry = {"allOf": [{"$ref": "#/$defs/receipt_core"}], "$defs": schema["$defs"]}
        resolver = RefResolver(base_uri=sp.as_uri(), referrer=schema)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _rc_validator = Draft202012Validator(entry, resolver=resolver)
    errs = sorted(_rc_validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:220]}"
            for e in errs[:10]]


def main():
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wu = {u["id"]: u for u in cat["work_units"]}
    report = {}
    for uid in UNITS:
        entry = wu[uid]
        out_rel = str(entry["output_path"]).replace("\\", "/")
        art = REPO / out_rel
        r = {"output_path": out_rel}
        fails = []
        # V1
        if not art.is_file() or art.stat().st_size <= 0:
            r["verdict"] = "FAIL"
            r["reasons"] = ["V1 artifact-absent-or-empty"]
            report[uid] = r
            print(f"{uid:9} FAIL  V1 artifact-absent-or-empty")
            continue
        text = art.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except Exception as exc:
            r["verdict"] = "FAIL"
            r["reasons"] = [f"V1 unparseable {type(exc).__name__}: {exc}"]
            report[uid] = r
            print(f"{uid:9} FAIL  V1 unparseable {type(exc).__name__}")
            continue
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            fails.append(f"V1-self-declared:{st}")
        # V2
        sentinel = str(entry.get("completion_sentinel") or "")
        if not sentinel:
            fails.append("V2 sentinel-missing-in-catalog")
        elif sentinel not in text:
            fails.append("V2 sentinel-absent")
        # V3
        srp = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
        try:
            sr = json.loads(srp.read_text(encoding="utf-8"))
        except Exception as exc:
            fails.append(f"V3 return-unparseable {type(exc).__name__}")
            sr = {}
        else:
            sret = str(sr.get("status") or sr.get("state") or "").upper()
            if sret in NOT_DELIVERING:
                fails.append(f"V3 return:{sret}")
        # V5
        man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            fails.append(f"V5 manifest-unparseable {type(exc).__name__}")
            man = {}
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        live = digest_lf(art)
        prim = [a for a in rows if str(a.get("path") or "").replace("\\", "/") == out_rel]
        if not prim:
            fails.append("V5 manifest-primary-row-absent")
        else:
            if prim[0].get("present") is not True:
                fails.append("V5 primary-row present!=true")
            if str(prim[0].get("sha256") or "") != live:
                fails.append(f"V5 sha-mismatch recorded={str(prim[0].get('sha256'))[:16]} live={live[:16]}")
        if prim:
            others_missing = []
            seen_prim = False
            for a in rows:
                if a is prim[0]:
                    seen_prim = True
                    continue
                if a.get("present") is True:
                    p2 = REPO / str(a.get("path") or "").replace("\\", "/")
                    if not p2.is_file():
                        others_missing.append(str(a.get("path")))
            if others_missing:
                fails.append(f"V5 present-rows-absent-on-disk {others_missing[:4]}")
        # V6
        sch = schema_errors(doc, str(entry["output_schema"]))
        if sch:
            fails.append(f"V6 output_schema x{len(sch)}: " + " ;; ".join(e[:140] for e in sch[:3]))
        # V7
        rce = receipt_core_errors(doc)
        if rce:
            fails.append(f"V7 receipt_core x{len(rce)}: " + " ;; ".join(e[:140] for e in rce[:3]))
        # V9 (closure state; pending is expected for unclosed units)
        rev = doc.get("reviewer") or {}
        r["closure_state"] = {"state": doc.get("state"), "verdict": rev.get("verdict"),
                              "independent": rev.get("independent")}
        r["sha256_live"] = live
        r["schema_errors"] = sch if len(sch) <= 12 else sch[:12] + [f"...+{len(sch)-12} more"]
        r["receipt_core_errors"] = rce if len(rce) <= 12 else rce[:12] + [f"...+{len(rce)-12} more"]
        r["verdict_static"] = "PASS" if not fails else "FAIL"
        if fails:
            r["static_fails"] = fails
        report[uid] = r
        print(f"{uid:9} {'PASS' if not fails else 'FAIL'}  " +
              (" ;; ".join(f[:120] for f in fails[:3]) if fails
               else f"sha={live[:12]} closure={r['closure_state']}"))
        sys.stdout.flush()
    (OUT / "static-sweep.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    n = sum(1 for v in report.values() if v["verdict_static"] == "PASS")
    print(f"STATIC-SUMMARY {n}/{len(UNITS)}")


if __name__ == "__main__":
    main()

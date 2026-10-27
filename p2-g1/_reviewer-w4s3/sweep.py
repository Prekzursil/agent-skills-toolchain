#!/usr/bin/env python3
"""w4s3 independent reviewer - deterministic static sweep (phase 1).

Per unit: catalog entry, artifact at output_path (exists/non-empty/parses/
not-self-blocked), manifest primary sha256 row vs live artifact (CRLF->LF
normalized AND raw), artifact vs catalog output_schema (jsonschema),
receipt parse + receipt schema, receipt SUCCESS-precondition inventory
(which builder-side fields state=SUCCESS would require).
"""
from __future__ import annotations
import hashlib, importlib.util, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IDS = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
       "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]


def digest_lf(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def digest_raw(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"__parse_error__": f"{type(e).__name__}: {e}"}


spec = importlib.util.spec_from_file_location(
    "rsg", REPO / "platform" / "lib" / "receipt_schema_gate.py")
rsg = importlib.util.module_from_spec(spec)
sys.modules["rsg"] = rsg
spec.loader.exec_module(rsg)

import jsonschema

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

results = {}
for uid in IDS:
    u = byid[uid]
    out_rel = str(u["output_path"]).replace("\\", "/")
    schema_rel = str(u["output_schema"]).replace("\\", "/")
    out = REPO / out_rel
    rec = {"unit_id": uid, "output_path": out_rel, "output_schema": schema_rel}
    rec["artifact_exists"] = out.is_file()
    rec["artifact_bytes"] = out.stat().st_size if out.is_file() else 0
    art = load_json(out) if out.is_file() else None
    rec["artifact_parses"] = isinstance(art, dict) and "__parse_error__" not in art
    rec["artifact_parse_error"] = art.get("__parse_error__") if isinstance(art, dict) else "not-an-object"
    st = str((art or {}).get("state") or "").upper() if isinstance(art, dict) else ""
    rec["artifact_self_state"] = st or None
    rec["artifact_not_self_blocked"] = st not in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT")
    man = load_json(REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json")
    rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
    prim_rows = [a for a in rows if str(a.get("path") or "").replace("\\", "/") == out_rel]
    rec["manifest_rows_for_unit"] = len(rows)
    rec["manifest_primary_rows"] = len(prim_rows)
    if out.is_file():
        rec["live_sha_lf"] = digest_lf(out)
        rec["live_sha_raw"] = digest_raw(out)
        rec["manifest_sha_match_lf"] = any(a.get("sha256") == rec["live_sha_lf"] and a.get("present") is True for a in prim_rows)
        rec["manifest_sha_match_raw"] = any(a.get("sha256") == rec["live_sha_raw"] and a.get("present") is True for a in prim_rows)
        rec["manifest_declared_bytes"] = [a.get("bytes") for a in prim_rows]
        rec["manifest_sha_primary"] = [a.get("sha256") for a in prim_rows]
    sp = REPO / schema_rel
    sch = load_json(sp)
    if isinstance(art, dict) and "__parse_error__" not in art and isinstance(sch, dict) and "__parse_error__" not in sch:
        try:
            jsonschema.validate(art, sch)
            rec["artifact_schema_valid"] = True
            rec["artifact_schema_errors"] = []
        except jsonschema.ValidationError as e:
            rec["artifact_schema_valid"] = False
            rec["artifact_schema_errors"] = [f"{list(e.absolute_path)}: {e.message[:200]}"]
        except jsonschema.SchemaError as e:
            rec["artifact_schema_valid"] = None
            rec["artifact_schema_errors"] = [f"SCHEMA-ERROR: {e.message[:200]}"]
    else:
        rec["artifact_schema_valid"] = None
        rec["artifact_schema_errors"] = ["artifact or schema unparseable"]
    rp = REPO / "command-center/receipts" / f"{uid}.json"
    rdoc = load_json(rp)
    rec["receipt_parses"] = isinstance(rdoc, dict) and "__parse_error__" not in rdoc
    rec["receipt_state"] = rdoc.get("state") if isinstance(rdoc, dict) else None
    errs = rsg.validate_receipt(rdoc) if isinstance(rdoc, dict) else ["unparseable"]
    rec["receipt_schema_errors_now"] = len(errs)
    rec["receipt_schema_errors_now_first3"] = errs[:3]
    if isinstance(rdoc, dict):
        tests = [t for t in (rdoc.get("tests") or []) if isinstance(t, dict)]
        bad_tests = [t.get("id") for t in tests if t.get("result") not in ("PASS",)]
        nc = [c for c in (rdoc.get("negative_controls") or []) if isinstance(c, dict)]
        bad_nc = [c.get("id") for c in nc if c.get("fired_on_bad_state") is not True or c.get("silent_on_good_state") is not True]
        cons = [c for c in (rdoc.get("downstream_consumers") or []) if isinstance(c, dict)]
        bad_cons = [c.get("consumer") for c in cons if c.get("executed") is not True or c.get("read_ok") is not True or not isinstance(c.get("probe"), dict) or not c["probe"].get("raw_output")]
        reg = rdoc.get("manifest_registration") or {}
        mm = []
        for a in (rdoc.get("artifacts") or []):
            if not isinstance(a, dict):
                continue
            p = REPO / str(a.get("path"))
            if not p.is_file():
                mm.append({"path": a.get("path"), "why": "absent"})
                continue
            if p.stat().st_size != a.get("bytes"):
                mm.append({"path": a.get("path"), "why": f"declared {a.get('bytes')} != disk {p.stat().st_size}"})
            elif a.get("role") == "primary":
                d = digest_raw(p)
                dl = digest_lf(p)
                if d != a.get("sha256") and dl != a.get("sha256"):
                    mm.append({"path": a.get("path"), "why": f"sha mismatch disk raw={d[:12]} lf={dl[:12]}"})
        rec["success_preconditions"] = {
            "tests_count": len(tests), "tests_all_pass": len(tests) > 0 and not bad_tests, "bad_tests": bad_tests,
            "negative_controls_count": len(nc), "negative_controls_valid": len(nc) > 0 and not bad_nc, "bad_nc": bad_nc,
            "residual_unknowns_present": "residual_unknowns" in rdoc,
            "manifest_registered": reg.get("registered") is True,
            "manifest_path_on_disk": (REPO / str(reg.get("manifest_path"))).is_file() if reg.get("manifest_path") else False,
            "downstream_consumers_count": len(cons), "downstream_consumers_valid": len(cons) > 0 and not bad_cons, "bad_cons": bad_cons,
            "evidence_count": len([e for e in (rdoc.get("evidence") or []) if isinstance(e, dict)]),
            "artifacts_rows_bytes_match_disk": not mm,
            "artifact_row_mismatches": mm,
        }
    results[uid] = rec

out_path = Path(__file__).parent / "sweep.json"
out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
print("wrote", out_path)
for uid, r in results.items():
    ok_art = r["artifact_exists"] and r["artifact_bytes"] > 0 and r["artifact_parses"] and r["artifact_not_self_blocked"]
    sha_ok = r.get("manifest_sha_match_lf")
    sch_ok = r["artifact_schema_valid"]
    sp2 = r.get("success_preconditions", {})
    print(f"{uid}: artifact={'OK' if ok_art else 'BAD'} shaLF={'OK' if sha_ok else 'BAD'} "
          f"artSchema={'OK' if sch_ok else 'BAD'} receipt_state={r['receipt_state']} "
          f"rschema_errs={r['receipt_schema_errors_now']} "
          f"succ_pre:tests={sp2.get('tests_count')}/{'P' if sp2.get('tests_all_pass') else 'F'} "
          f"nc={sp2.get('negative_controls_count')}/{'V' if sp2.get('negative_controls_valid') else 'I'} "
          f"ru={'Y' if sp2.get('residual_unknowns_present') else 'N'} "
          f"cons={sp2.get('downstream_consumers_count')}/{'V' if sp2.get('downstream_consumers_valid') else 'I'}")

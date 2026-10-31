#!/usr/bin/env python3
"""Independent reviewer verifier + closer - wave 2 shard 17 (12 RES units).

Transport INDEPENDENT of the builder's finish.py: direct subprocess probes,
own sha256 recomputation (CRLF->LF normalized), own jsonschema validation,
own receipt read-back. The builder's BLOCKED receipts are closed ONLY here.

Modes:
  verify   - run every check, print per-unit results, dump evidence JSON.
             Exit 0 only if ALL 12 units hold every predicate.
  close    - for units green in verify-evidence.json with a BLOCKED
             reviewer-absent receipt: write the closure (state=SUCCESS,
             reviewer.verdict=PASS, reviewer.independent=true, failure block
             removed) and read the receipt back to confirm the shape.
  confirm  - cheap receipt-shape re-check of all 12 (no probes re-run).
             Exit 0 only if every receipt reads back as a valid closure.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
RECEIPTS = REPO / "command-center" / "receipts"
EVIDENCE = Path(r"C:\Users\Prekzursil\p2-g1\_rev-w2-shard17\verify-evidence.json")
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
UNITS = [
    "RES-0020", "RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079",
    "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
]
REVIEWER_ID = "independent-reviewer-shard17-w2-2026-10-25"
TODAY = "2026-10-25"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - verifier must see the reason
        return None, f"{type(exc).__name__}: {exc}"


def catalog_units() -> dict:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = None
    if isinstance(cat, dict):
        for key in ("work_units", "units", "entries", "catalog"):
            if isinstance(cat.get(key), list):
                units = cat[key]
                break
        if units is None:
            units = cat
    else:
        units = cat
    if isinstance(units, list):
        units = {u.get("id") or u.get("unit_id"): u for u in units}
    return units


def run_probe(script: Path) -> tuple[int, str, float]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = datetime.now(timezone.utc)
    try:
        r = subprocess.run(
            [sys.executable, "-B", str(script)],
            capture_output=True, text=True, timeout=900,
            cwd=str(REPO), env=env, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT after 900s", 900.0
    dt = (datetime.now(timezone.utc) - t0).total_seconds()
    out = ((r.stdout or "") + "\n--stderr--\n" + (r.stderr or "")).strip()
    return r.returncode, out, dt


def validate_schema(schema_val, doc) -> tuple[bool, str]:
    try:
        import jsonschema
    except Exception as exc:  # noqa: BLE001 - fail closed, never silently pass
        return False, f"jsonschema-unavailable:{exc}"
    schema = schema_val
    origin = "inline"
    if isinstance(schema_val, str):
        sp = REPO / schema_val.replace("\\", "/")
        if not sp.is_file():
            return False, f"schema-file-absent:{schema_val}"
        schema, err = load_json(sp)
        if schema is None:
            return False, f"schema-unreadable:{schema_val}:{err}"
        origin = schema_val
    if not isinstance(schema, dict):
        return False, f"schema-not-object:{origin}"
    try:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        errs = sorted(cls(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
    except jsonschema.SchemaError as exc:
        return False, f"schema-invalid:{origin}:{exc.message[:160]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"schema-validator-error:{origin}:{exc}"
    if errs:
        w = errs[0]
        return False, (
            f"schema-violations:{len(errs)} first:{w.message[:200]} "
            f"at:{'/'.join(str(x) for x in w.absolute_path)[:120]}"
        )
    return True, f"OK:{origin}:0-errors"


def verify_unit(uid: str, units: dict) -> tuple[bool, list[str], dict]:
    fails: list[str] = []
    info: dict = {"uid": uid}

    unit = units.get(uid)
    if unit is None:
        return False, ["catalog-entry-absent"], info

    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    if not out_rel:
        return False, ["catalog-output_path-absent"], info
    out = REPO / out_rel
    info["output_path"] = out_rel

    # -- 1. artifact exists / non-empty / parses / dict / not self-blocked ---
    if not out.is_file():
        return False, [f"artifact-absent:{out_rel}"], info
    raw_bytes = out.stat().st_size
    info["artifact_bytes_on_disk"] = raw_bytes
    if raw_bytes <= 0:
        fails.append("artifact-empty")
    doc, err = load_json(out)
    if doc is None:
        fails.append(f"artifact-unparseable:{err}")
        return False, fails, info
    if not isinstance(doc, dict):
        fails.append("artifact-not-object")
        return False, fails, info
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        fails.append(f"artifact-self-declared:{st}")

    # -- 2. completion sentinel present in artifact text ---------------------
    sent = str(unit.get("completion_sentinel") or "")
    info["sentinel"] = sent[:80]
    if sent and sent not in out.read_text(encoding="utf-8", errors="replace"):
        fails.append("completion-sentinel-absent-in-artifact")

    # -- 3. live sha256 vs UNIT-ARTIFACT-MANIFEST.json row -------------------
    live_sha, live_n = digest(out)
    info["sha256"] = live_sha
    info["artifact_bytes_lf"] = live_n
    man, err = load_json(PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json")
    if man is None:
        fails.append(f"manifest-unparseable:{err}")
    else:
        rows = [a for a in (man.get("artifacts") or man.get("rows") or [])
                if isinstance(a, dict) and (a.get("unit_id") in (None, uid))]
        prim = [a for a in rows
                if str(a.get("path") or "").replace("\\", "/") == out_rel]
        info["manifest_primary_rows"] = len(prim)
        ok_row = [a for a in prim
                  if str(a.get("sha256") or "") == live_sha
                  and a.get("present") is True]
        if not ok_row:
            if prim:
                got = prim[0].get("sha256")
                fails.append(f"manifest-sha-mismatch:manifest={got} live={live_sha}")
            else:
                fails.append("manifest-primary-row-missing")
        rb = ok_row[0].get("bytes") if ok_row else None
        if isinstance(rb, int) and rb != live_n:
            fails.append(f"manifest-bytes-mismatch:manifest={rb} live={live_n}")

    # -- 4. receipt: parse, builder claims, min-bytes threshold --------------
    rec, err = load_json(RECEIPTS / f"{uid}.json")
    if rec is None:
        fails.append(f"receipt-unparseable:{err}")
        info["receipt_state"] = "UNPARSEABLE"
        r_state = "UNPARSEABLE"
    else:
        r_state = str(rec.get("state") or "").upper()
        info["receipt_state"] = r_state
        th = rec.get("min_bytes_threshold")
        if isinstance(th, int) and live_n < th:
            fails.append(f"receipt-min-bytes:{live_n}<{th}")
        art_rows = [a for a in (rec.get("artifacts") or []) if isinstance(a, dict)]
        prim_rec = [a for a in art_rows
                    if str(a.get("path") or "").replace("\\", "/") == out_rel]
        if not prim_rec:
            fails.append("receipt-primary-artifact-row-missing")
        else:
            rsha = str(prim_rec[0].get("sha256") or "")
            if rsha != live_sha:
                fails.append(f"receipt-sha-mismatch:receipt={rsha[:16]} live={live_sha[:16]}")
        rv = rec.get("reviewer") if isinstance(rec.get("reviewer"), dict) else {}
        info["receipt_reviewer_verdict"] = rv.get("verdict")
        info["receipt_reviewer_independent"] = rv.get("independent")
        already = (r_state == "SUCCESS"
                   and str(rv.get("verdict") or "").upper() == "PASS"
                   and rv.get("independent") is True)
        info["already_closed_valid"] = already
        if r_state == "SUCCESS" and not already:
            fails.append("state=SUCCESS-without-valid-independent-PASS-closure")
        if r_state not in ("BLOCKED", "SUCCESS"):
            fails.append(f"unexpected-receipt-state:{r_state}")

    # -- 5. SUBAGENT-RETURN.json sanity ---------------------------------------
    ret, err = load_json(PROBES / uid / "SUBAGENT-RETURN.json")
    if ret is None:
        fails.append(f"subagent-return-unparseable:{err}")
    else:
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        if rst in NOT_DELIVERING:
            fails.append(f"subagent-return-self-declared:{rst}")
        np = ret.get("named_probes")
        info["named_probes_recorded"] = len(np) if isinstance(np, list) else 0

    # -- 6. re-run BOTH live probes myself ------------------------------------
    p1 = sorted(PROBES.joinpath(uid).glob("probe1*.py"))
    p2 = sorted(PROBES.joinpath(uid).glob("probe2*.py"))
    probes = p1 + p2
    if len(p1) < 1 or len(p2) < 1:
        fails.append(f"probe-scripts-missing:probe1={len(p1)} probe2={len(p2)}")
    info["probes"] = {}
    for pf in probes:
        rc, outp, dt = run_probe(pf)
        marker_ok = any(ln.lstrip().startswith("SUCCESS:")
                        for ln in outp.splitlines())
        okp = (rc == 0) and marker_ok
        info["probes"][pf.name] = {"rc": rc, "secs": round(dt, 1), "success_marker": marker_ok}
        if not okp:
            tail = outp[-260:].replace("\n", " | ")
            fails.append(f"probe-{pf.name}-red:rc={rc} marker={marker_ok} tail={tail}")

    # -- 7. catalog output_schema validation ----------------------------------
    schema_val = unit.get("output_schema", unit.get("output_schema_path"))
    if schema_val is None:
        fails.append("catalog-output-schema-absent")
    else:
        ok_s, msg = validate_schema(schema_val, doc)
        info["schema"] = msg
        if not ok_s:
            fails.append(f"schema-fail:{msg}")

    return (not fails), fails, info


def close_unit(uid: str, info: dict) -> tuple[bool, str]:
    path = RECEIPTS / f"{uid}.json"
    rec, err = load_json(path)
    if rec is None:
        return False, f"receipt-unreadable-at-close:{err}"
    r_state = str(rec.get("state") or "").upper()
    rv = rec.get("reviewer") if isinstance(rec.get("reviewer"), dict) else {}
    if (r_state == "SUCCESS" and str(rv.get("verdict") or "").upper() == "PASS"
            and rv.get("independent") is True):
        return True, "already-closed-valid-unchanged"

    probes_seen = info.get("probes") or {}
    probe_txt = ", ".join(f"{k}=rc{v['rc']}" for k, v in sorted(probes_seen.items()))
    schema_msg = str(info.get("schema") or "not-run")
    notes = (
        f"Independent reviewer closure {TODAY} (wave 2 shard 17). Reviewer did not "
        f"build this unit. Live re-verification: artifact at {info.get('output_path')} "
        f"exists/non-empty/parses, no self-declared non-delivery state; completion "
        f"sentinel present in artifact text; sha256 recomputed CRLF->LF = "
        f"{str(info.get('sha256'))[:16]}... and matches the "
        f"UNIT-ARTIFACT-MANIFEST.json primary row (present=true) and the receipt's "
        f"primary artifacts row; both named probes re-executed by the reviewer "
        f"({probe_txt}, each rc=0 with terminal SUCCESS: marker); output_schema "
        f"validated: {schema_msg}."
    )
    rec["state"] = "SUCCESS"
    rec["reviewer"] = {
        "reviewer_id": REVIEWER_ID,
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "reviewed_at": now_utc(),
        "notes": notes,
    }
    rec.pop("failure", None)
    sent = str(rec.get("sentinel") or "")
    if "independent reviewer closure" not in sent:
        rec["sentinel"] = (sent + f" Independent reviewer closure {TODAY} "
                           f"(wave 2 shard 17): PASS.").strip()
    ts = rec.get("timestamps") if isinstance(rec.get("timestamps"), dict) else {}
    ts["reviewed_at"] = now_utc()
    rec["timestamps"] = ts

    path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # read-back: the write is only done when the shape re-reads correctly
    back, err2 = load_json(path)
    if back is None:
        return False, f"closure-readback-unparseable:{err2}"
    rvb = back.get("reviewer") if isinstance(back.get("reviewer"), dict) else {}
    ok = (str(back.get("state") or "").upper() == "SUCCESS"
          and str(rvb.get("verdict") or "").upper() == "PASS"
          and rvb.get("independent") is True
          and not (isinstance(back.get("failure"), dict)
                   and "reviewer-absent" in [str(c) for c in (back["failure"].get("classification") or [])]))
    return ok, ("closed+readback-ok" if ok else "closure-readback-shape-invalid")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    units = catalog_units()

    if mode == "verify":
        results = {}
        all_ok = True
        for uid in UNITS:
            ok, fails, info = verify_unit(uid, units)
            results[uid] = {"ok": ok, "fails": fails, "info": info}
            all_ok = all_ok and ok
            print(f"== {uid} {'OK' if ok else 'FAIL'}")
            print(f"   out={info.get('output_path')} bytes_lf={info.get('artifact_bytes_lf')}")
            print(f"   sha256={info.get('sha256')}")
            print(f"   receipt_state={info.get('receipt_state')} already_closed={info.get('already_closed_valid')}")
            print(f"   schema={info.get('schema')}")
            for name, p in (info.get("probes") or {}).items():
                print(f"   probe {name}: rc={p['rc']} secs={p['secs']} marker={p['success_marker']}")
            for f in fails:
                print(f"   FAILCHECK: {f}")
            print(f"   {'SUCCESS:' if ok else 'FAILED:'}{uid}")
        EVIDENCE.write_text(json.dumps(
            {"generated_at": now_utc(), "reviewer": REVIEWER_ID,
             "all_ok": all_ok, "units": results}, indent=1) + "\n", encoding="utf-8")
        print(f"SUCCESS:reviewer-shard17-w2 verify all-green" if all_ok
              else "FAILED:reviewer-shard17-w2 verify one or more units red")
        return 0 if all_ok else 1

    if mode == "close":
        ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))["units"]
        rc_all = 0
        for uid in UNITS:
            u = ev.get(uid)
            if not u or not u.get("ok"):
                print(f"FAILED:{uid} not closed - verification not green")
                rc_all = 1
                continue
            ok, msg = close_unit(uid, u["info"])
            print(f"   close {uid}: {msg}")
            print(f"   {'SUCCESS:' if ok else 'FAILED:'}close-{uid}")
            rc_all = rc_all if ok else 1
        return rc_all

    if mode == "confirm":
        all_ok = True
        for uid in UNITS:
            rec, err = load_json(RECEIPTS / f"{uid}.json")
            if rec is None:
                print(f"FAILED:{uid} confirm receipt-unreadable:{err}")
                all_ok = False
                continue
            rv = rec.get("reviewer") if isinstance(rec.get("reviewer"), dict) else {}
            st = str(rec.get("state") or "").upper()
            ok = (st == "SUCCESS"
                  and str(rv.get("verdict") or "").upper() == "PASS"
                  and rv.get("independent") is True
                  and not (isinstance(rec.get("failure"), dict)
                           and "reviewer-absent" in [str(c) for c in (rec["failure"].get("classification") or [])]))
            print(f"   {uid}: state={st} verdict={rv.get('verdict')} independent={rv.get('independent')} "
                  f"failure={'absent' if not isinstance(rec.get('failure'), dict) else 'present'} "
                  f"-> {'SUCCESS:' if ok else 'FAILED:'}{uid}")
            all_ok = all_ok and ok
        print("SUCCESS:reviewer-shard17-w2 confirm all receipts closed valid" if all_ok
              else "FAILED:reviewer-shard17-w2 confirm found invalid receipts")
        return 0 if all_ok else 1

    print("usage: verify | close | confirm")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

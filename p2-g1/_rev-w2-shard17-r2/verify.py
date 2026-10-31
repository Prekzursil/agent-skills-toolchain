#!/usr/bin/env python3
"""FRESH independent reviewer verification - wave 2 shard 17 (12 RES units).
Own code, run 2026-10-26. Checks per unit:
 1 artifact at catalog output_path: exists, non-empty, parses, state not in NOT_DELIVERING
 2 completion sentinel present in artifact text
 3 sha256 (CRLF->LF) recomputed live vs UNIT-ARTIFACT-MANIFEST.json row (path+sha+present+bytes)
 4 probes probe1*/probe2* re-run live: rc==0 + SUCCESS: marker
 5 output_schema validated via blessed resolver AND direct jsonschema
 6 SUBAGENT-RETURN not self-declaring non-delivery
 7 receipt shape read (report only)
"""
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
RECEIPTS = REPO / "command-center" / "receipts"
UNITS = ["RES-0020", "RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079",
         "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as SR


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_lf(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = {u.get("id"): u for u in cat["work_units"]}
    out = {}
    all_ok = True
    for uid in UNITS:
        r = {"uid": uid, "fails": []}
        unit = units.get(uid)
        if unit is None:
            r["fails"].append("catalog-entry-absent")
            out[uid] = r
            all_ok = False
            continue
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        r["output_path"] = out_rel
        p_out = REPO / out_rel
        if not p_out.is_file():
            r["fails"].append(f"artifact-absent:{out_rel}")
            out[uid] = r
            all_ok = False
            continue
        n = p_out.stat().st_size
        r["bytes_disk"] = n
        if n <= 0:
            r["fails"].append("artifact-empty")
        doc, err = load(p_out)
        if doc is None:
            r["fails"].append(f"unparseable:{err}")
            out[uid] = r
            all_ok = False
            continue
        st = str(doc.get("state") or "").upper()
        r["artifact_state"] = st or None
        if st in NOT_DELIVERING:
            r["fails"].append(f"artifact-self-declared:{st}")
        text = p_out.read_text(encoding="utf-8", errors="replace")
        sent = str(unit.get("completion_sentinel") or "")
        r["sentinel_present"] = (not sent) or (sent in text)
        if sent and sent not in text:
            r["fails"].append("completion-sentinel-absent")

        live_sha, live_n = sha_lf(p_out)
        r["sha256"] = live_sha
        r["bytes_lf"] = live_n
        man, err = load(PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json")
        if man is None:
            r["fails"].append(f"manifest-unparseable:{err}")
        else:
            rows = [a for a in (man.get("artifacts") or [])
                    if isinstance(a, dict) and a.get("unit_id") == uid]
            r["manifest_rows"] = len(rows)
            hit = [a for a in rows
                   if str(a.get("path") or "").replace("\\", "/") == out_rel
                   and str(a.get("sha256") or "") == live_sha
                   and a.get("present") is True]
            if not hit:
                if rows:
                    r["fails"].append(
                        f"manifest-sha-mismatch:manifest={rows[0].get('sha256')} live={live_sha}")
                else:
                    r["fails"].append("manifest-row-missing")
            else:
                rb = hit[0].get("bytes")
                if isinstance(rb, int) and rb != live_n:
                    r["fails"].append(f"manifest-bytes-mismatch:{rb}!={live_n}")

        rec, err = load(RECEIPTS / f"{uid}.json")
        if rec is None:
            r["fails"].append(f"receipt-unparseable:{err}")
            r["receipt_state"] = "UNPARSEABLE"
        else:
            r["receipt_state"] = str(rec.get("state") or "").upper()
            rv = rec.get("reviewer") if isinstance(rec.get("reviewer"), dict) else {}
            r["receipt_verdict"] = rv.get("verdict")
            r["receipt_independent"] = rv.get("independent")
            th = rec.get("min_bytes_threshold")
            if isinstance(th, int) and live_n < th:
                r["fails"].append(f"min-bytes:{live_n}<{th}")

        ret, err = load(PROBES / uid / "SUBAGENT-RETURN.json")
        if ret is None:
            r["fails"].append(f"subagent-return-unparseable:{err}")
        else:
            rst = str(ret.get("status") or ret.get("state") or "").upper()
            r["return_state"] = rst
            if rst in NOT_DELIVERING:
                r["fails"].append(f"subagent-return-declares:{rst}")

        probes = (sorted(PROBES.joinpath(uid).glob("probe1*.py"))
                  + sorted(PROBES.joinpath(uid).glob("probe2*.py")))
        if len(probes) < 2:
            r["fails"].append(f"probe-scripts-found:{len(probes)}")
        r["probes"] = {}
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for pf in probes:
            try:
                pr = subprocess.run([sys.executable, "-B", str(pf)], capture_output=True,
                                    text=True, timeout=900, cwd=str(REPO), env=env,
                                    encoding="utf-8", errors="replace")
                rc, o = pr.returncode, (pr.stdout or "") + (pr.stderr or "")
            except subprocess.TimeoutExpired:
                rc, o = 124, "TIMEOUT"
            marker = any(l.lstrip().startswith("SUCCESS:") for l in o.splitlines())
            r["probes"][pf.name] = {"rc": rc, "marker": marker}
            if rc != 0 or not marker:
                r["fails"].append(f"probe-red:{pf.name}:rc={rc}:marker={marker}")

        decl = unit.get("output_schema")
        if not decl:
            r["fails"].append("output-schema-absent-in-catalog")
        else:
            try:
                errs = SR.validate_artifact(doc, decl)
                rr = SR.resolve(decl).as_dict()
                r["schema_class"] = rr.get("artifact_class")
                r["schema_resolver"] = (
                    f"violations={len(errs)} first={(errs[0][:150] if errs else 'OK')}")
                if errs:
                    r["fails"].append(f"schema-resolver-fail:{len(errs)}:{errs[0][:160]}")
            except Exception as e:
                r["schema_resolver"] = f"validator-error:{e}"
                r["fails"].append(f"schema-resolver-error:{str(e)[:160]}")
            try:
                import jsonschema
                sp = REPO / decl.replace("\\", "/")
                schema, serr = load(sp)
                if schema is None:
                    r["schema_direct"] = f"unreadable:{serr}"
                    r["fails"].append("schema-shim-unreadable")
                else:
                    cls = jsonschema.validators.validator_for(schema)
                    cls.check_schema(schema)
                    derrs = sorted(cls(schema).iter_errors(doc),
                                   key=lambda e: list(e.absolute_path))
                    r["schema_direct"] = f"violations={len(derrs)}"
                    if derrs:
                        r["fails"].append(
                            f"schema-direct-fail:{len(derrs)}:{derrs[0].message[:150]}")
            except Exception as e:
                r["schema_direct"] = f"error:{e}"
                r["fails"].append(f"schema-direct-error:{str(e)[:160]}")

        r["ok"] = not r["fails"]
        all_ok = all_ok and r["ok"]
        out[uid] = r

    ev = Path(r"C:\Users\Prekzursil\p2-g1\_rev-w2-shard17-r2\verify-evidence-r2.json")
    ev.write_text(json.dumps(
        {"generated_at": now(),
         "reviewer": "independent-reviewer-shard17-w2-r2-20261026",
         "all_ok": all_ok, "units": out}, indent=1) + "\n", encoding="utf-8")
    for uid in UNITS:
        r = out[uid]
        print(f"== {uid} {'OK' if r.get('ok') else 'FAIL'} "
              f"state={r.get('artifact_state')} rcpt={r.get('receipt_state')}/{r.get('receipt_verdict')}")
        print(f"   sha={r.get('sha256')} bytes={r.get('bytes_lf')} "
              f"manifest_rows={r.get('manifest_rows')} sentinel={r.get('sentinel_present')}")
        for nm, p in (r.get("probes") or {}).items():
            print(f"   probe {nm}: rc={p['rc']} marker={p['marker']}")
        print(f"   resolver: {r.get('schema_resolver')}")
        print(f"   direct:   {r.get('schema_direct')}")
        for f in r["fails"]:
            print(f"   FAILCHECK: {f}")
    print("ALL-GREEN" if all_ok else "ONE-OR-MORE-RED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

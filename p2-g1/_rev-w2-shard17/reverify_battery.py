#!/usr/bin/env python3
"""Independent re-verification battery - reviewer wave 2 shard 17 (12 RES units).

Deliberately NOT the previous session's script: fresh code, own sha256
computation, own schema validation through BOTH the blessed resolver and a
direct jsonschema run, own probe execution, own receipt checks.
Also runs a population control: validates every RES-* artifact in the catalog
so we know whether the schema is satisfiable at all.
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

UNITS = [
    "RES-0020", "RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079",
    "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as SR  # noqa: E402

OUT = {}


def sha_lf(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_unit(uid: str, units: dict) -> dict:
    res = {"uid": uid, "fails": []}
    unit = units.get(uid)
    if unit is None:
        res["fails"].append("catalog-entry-absent")
        return res

    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    res["output_path"] = out_rel

    # 1. artifact existence / non-empty / parse / self-state
    if not out.is_file():
        res["fails"].append(f"artifact-absent:{out_rel}")
        return res
    n_disk = out.stat().st_size
    res["bytes_disk"] = n_disk
    if n_disk <= 0:
        res["fails"].append("artifact-empty")
    doc, err = load(out)
    if doc is None:
        res["fails"].append(f"unparseable:{err}")
        return res
    st = str(doc.get("state") or "").upper()
    res["artifact_state"] = st or None
    if st in NOT_DELIVERING:
        res["fails"].append(f"artifact-self-declared:{st}")

    # 2. completion sentinel text present
    sent = str(unit.get("completion_sentinel") or "")
    if sent and sent not in out.read_text(encoding="utf-8", errors="replace"):
        res["fails"].append("completion-sentinel-absent")

    # 3. sha256 (CRLF->LF) vs manifest primary row
    live_sha, live_n = sha_lf(out)
    res["sha256"] = live_sha
    res["bytes_lf"] = live_n
    man, err = load(PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json")
    if man is None:
        res["fails"].append(f"manifest-unparseable:{err}")
    else:
        rows = [a for a in (man.get("artifacts") or man.get("rows") or [])
                if isinstance(a, dict) and (a.get("unit_id") in (None, uid))]
        prim = [a for a in rows
                if str(a.get("path") or "").replace("\\", "/") == out_rel]
        res["manifest_rows"] = len(prim)
        hit = [a for a in prim
               if str(a.get("sha256") or "") == live_sha and a.get("present") is True]
        if not hit:
            if prim:
                res["fails"].append(
                    f"manifest-sha-mismatch:manifest={prim[0].get('sha256')} live={live_sha}")
            else:
                res["fails"].append("manifest-primary-row-missing")
        else:
            rb = hit[0].get("bytes")
            if isinstance(rb, int) and rb != live_n:
                res["fails"].append(f"manifest-bytes-mismatch:{rb}!={live_n}")

    # 4. receipt current state (report only; closure decision separate)
    rec, err = load(RECEIPTS / f"{uid}.json")
    if rec is None:
        res["fails"].append(f"receipt-unparseable:{err}")
        res["receipt_state"] = "UNPARSEABLE"
    else:
        r_state = str(rec.get("state") or "").upper()
        res["receipt_state"] = r_state
        rv = rec.get("reviewer") if isinstance(rec.get("reviewer"), dict) else {}
        res["receipt_verdict"] = rv.get("verdict")
        res["receipt_independent"] = rv.get("independent")
        th = rec.get("min_bytes_threshold")
        if isinstance(th, int) and live_n < th:
            res["fails"].append(f"min-bytes:{live_n}<{th}")

    # 5. SUBAGENT-RETURN sanity
    ret, err = load(PROBES / uid / "SUBAGENT-RETURN.json")
    if ret is None:
        res["fails"].append(f"subagent-return-unparseable:{err}")
    else:
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        if rst in NOT_DELIVERING:
            res["fails"].append(f"subagent-return-declares:{rst}")

    # 6. probes re-run by ME (fresh subprocess, rc==0 + SUCCESS: marker)
    p1 = sorted(PROBES.joinpath(uid).glob("probe1*.py"))
    p2 = sorted(PROBES.joinpath(uid).glob("probe2*.py"))
    probes = p1 + p2
    if len(p1) < 1 or len(p2) < 1:
        res["fails"].append(f"probe-scripts-missing:p1={len(p1)} p2={len(p2)}")
    res["probes"] = {}
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for pf in probes:
        try:
            r = subprocess.run([sys.executable, "-B", str(pf)], capture_output=True,
                               text=True, timeout=900, cwd=str(REPO), env=env,
                               encoding="utf-8", errors="replace")
            rc, outp = r.returncode, ((r.stdout or "") + (r.stderr or ""))
        except subprocess.TimeoutExpired:
            rc, outp = 124, "TIMEOUT"
        marker = any(ln.lstrip().startswith("SUCCESS:") for ln in outp.splitlines())
        res["probes"][pf.name] = {"rc": rc, "marker": marker}
        if rc != 0 or not marker:
            res["fails"].append(f"probe-red:{pf.name}:rc={rc}:marker={marker}")

    # 7. output_schema - TWO instruments
    decl = unit.get("output_schema") or unit.get("output_schema_path")
    if not decl:
        res["fails"].append("output-schema-absent-in-catalog")
        res["schema_resolver"] = "no-decl"
        res["schema_direct"] = "no-decl"
    else:
        try:
            errs = SR.validate_artifact(doc, decl)
            rr = SR.resolve(decl).as_dict()
            res["schema_class"] = rr.get("artifact_class")
            res["schema_physical"] = f"{rr.get('physical_path')}#{rr.get('physical_fragment')}"
            res["schema_resolver"] = f"violations={len(errs)} first={errs[0][:150] if errs else 'OK'}"
            if errs:
                res["fails"].append(f"schema-resolver-fail:{len(errs)}:{errs[0][:180]}")
        except Exception as exc:  # noqa: BLE001
            res["schema_resolver"] = f"validator-error:{exc}"
            res["fails"].append(f"schema-resolver-error:{str(exc)[:180]}")
        # direct instrument on the declared shim path
        try:
            import jsonschema
            sp = REPO / decl.replace("\\", "/")
            if not sp.is_file():
                res["schema_direct"] = f"shim-absent:{decl}"
                res["fails"].append(f"schema-shim-absent:{decl}")
            else:
                schema, serr = load(sp)
                if schema is None:
                    res["schema_direct"] = f"shim-unreadable:{serr}"
                    res["fails"].append("schema-shim-unreadable")
                else:
                    cls = jsonschema.validators.validator_for(schema)
                    cls.check_schema(schema)
                    derrs = sorted(cls(schema).iter_errors(doc),
                                   key=lambda e: list(e.absolute_path))
                    res["schema_direct"] = f"violations={len(derrs)}"
                    if derrs:
                        res["fails"].append(
                            f"schema-direct-fail:{len(derrs)}:{derrs[0].message[:150]}")
        except Exception as exc:  # noqa: BLE001
            res["schema_direct"] = f"error:{exc}"
            res["fails"].append(f"schema-direct-error:{str(exc)[:180]}")

    res["ok"] = not res["fails"]
    return res


def population_control(units: dict) -> dict:
    """Validate EVERY RES-* artifact in the catalog; count clean vs violating
    per artifact class. Proves whether the schema is satisfiable in practice."""
    from collections import Counter
    clean, bad = Counter(), Counter()
    bad_examples = {}
    for u in units.values():
        uid = str(u.get("id") or "")
        if not uid.startswith("RES-"):
            continue
        decl = u.get("output_schema")
        op = str(u.get("output_path") or "").replace("\\", "/")
        p = REPO / op
        if not decl or not p.is_file():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            errs = SR.validate_artifact(doc, decl)
            cls = SR.resolve(decl).as_dict().get("artifact_class")
        except Exception:
            continue
        if errs:
            bad[cls] += 1
            bad_examples.setdefault(cls, []).append(uid)
        else:
            clean[cls] += 1
    return {"clean_by_class": dict(clean), "violating_by_class": dict(bad),
            "violating_examples": {k: v[:8] for k, v in bad_examples.items()}}


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    wu = cat.get("work_units")
    if not isinstance(wu, list):
        print("FAILED:catalog work_units not a list")
        return 1
    units = {u.get("id"): u for u in wu}

    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if mode == "population":
        pc = population_control(units)
        print(json.dumps(pc, indent=1))
        print("SUCCESS:population-control" if pc else "FAILED:population-control")
        return 0

    all_ok = True
    for uid in UNITS:
        r = check_unit(uid, units)
        OUT[uid] = r
        all_ok = all_ok and r["ok"]
        print(f"== {uid} {'OK' if r['ok'] else 'FAIL'}")
        print(f"   path={r.get('output_path')} bytes_lf={r.get('bytes_lf')}")
        print(f"   sha256={r.get('sha256')}")
        print(f"   artifact_state={r.get('artifact_state')} receipt={r.get('receipt_state')} "
              f"verdict={r.get('receipt_verdict')} indep={r.get('receipt_independent')}")
        print(f"   resolver: {r.get('schema_resolver')}")
        print(f"   direct:   {r.get('schema_direct')}")
        for n, p in (r.get("probes") or {}).items():
            print(f"   probe {n}: rc={p['rc']} marker={p['marker']}")
        for f in r["fails"]:
            print(f"   FAILCHECK: {f}")
        print(f"   {'SUCCESS:' if r['ok'] else 'FAILED:'}{uid}")

    ev_path = Path(r"C:\Users\Prekzursil\p2-g1\_rev-w2-shard17\verify-evidence-v2.json")
    ev_path.write_text(json.dumps(
        {"generated_at": now(), "reviewer": "independent-reviewer-shard17-w2-rerun",
         "all_ok": all_ok, "units": OUT}, indent=1) + "\n", encoding="utf-8")
    print("SUCCESS:shard17-w2 rerun all-green" if all_ok
          else "FAILED:shard17-w2 rerun one or more units red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

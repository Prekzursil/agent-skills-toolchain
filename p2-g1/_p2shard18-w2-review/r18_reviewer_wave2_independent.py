#!/usr/bin/env python3
"""Wave-2 shard-18 INDEPENDENT reviewer battery (fresh, current reviewer). v2.

v2 fix: every check is strictly BOOLEAN (the *_errors counts live in obs only).
v1 bug: `all(v is True ...)` treated the zero-error counters (int 0) as failures,
reporting false FAILs on all 12 units. Details in obs.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P  # noqa: E402  (canonical repo validator)

import jsonschema  # noqa: E402  (second, independent schema engine)

UNITS = ["RES-0112", "RES-0114", "RES-0128", "RES-0131", "RES-0132", "RES-0137",
         "RES-0140", "RES-0141", "RES-0144", "RES-0148", "RES-0149", "RES-0150"]
BAD_STATES = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
BAD_TEXTS = [b"UNIT-INCOMPLETE", b"UNIT-FAILED", b"NOT-DELIVERING"]


def sha_norm(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha_raw(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def norm_len(raw: bytes) -> int:
    return len(raw.replace(b"\r\n", b"\n"))


def jsonschema_errors(doc, schema_path: Path) -> list[str]:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"schema-unreadable: {exc}"]
    try:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        v = cls(schema)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
        out = []
        for e in errs[:10]:
            loc = "/".join(str(x) for x in e.absolute_path) or "<root>"
            out.append(f"{loc}: {e.message[:240]}")
        return out
    except Exception as exc:
        return [f"validator-error: {exc}"]


def run(cmd: list[str], timeout: int = 300) -> dict:
    try:
        pr = subprocess.run(cmd, cwd=str(WS), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
        return {"rc": pr.returncode, "stdout": pr.stdout or "",
                "stderr": (pr.stderr or "")[-2000:]}
    except Exception as exc:
        return {"rc": -1, "stdout": "", "stderr": repr(exc)[:2000]}


def review(uid: str, e: dict) -> dict:
    r: dict = {"unit_id": uid, "checks": {}, "obs": {}}
    c = r["checks"]
    out = WS.joinpath(*e["output_path"].split("/"))

    # -- 1. artifact
    c["artifact_exists"] = out.is_file()
    raw = out.read_bytes() if out.is_file() else b""
    c["artifact_nonempty"] = len(raw) > 0
    doc = None
    try:
        doc = json.loads(raw.decode("utf-8"))
        c["artifact_parses"] = isinstance(doc, dict)
    except Exception:
        c["artifact_parses"] = False
    sb = []
    if isinstance(doc, dict):
        for k in ("state", "status", "verdict", "result", "disposition"):
            if k in doc and str(doc[k]).strip().upper() in BAD_STATES:
                sb.append(f"{k}={doc[k]}")
    low = raw.lower()
    for t in BAD_TEXTS:
        if t.lower() in low:
            sb.append("text:" + t.decode())
    c["artifact_not_self_blocked"] = not sb
    r["obs"]["self_block_hits"] = sb

    # -- 2. schema (canonical repo validator + raw jsonschema)
    canon = P.validate(doc, e["output_schema"]) if isinstance(doc, dict) else ["artifact-unreadable"]
    js = jsonschema_errors(doc, WS.joinpath(*e["output_schema"].split("/"))) if isinstance(doc, dict) else ["artifact-unreadable"]
    c["schema_valid_canonical"] = not canon
    c["schema_valid_jsonschema"] = not js
    r["obs"]["schema_canonical_errors"] = [str(x)[:300] for x in canon[:5]]
    r["obs"]["schema_jsonschema_errors"] = js[:5]

    # -- 3. manifest
    man_p = WS / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    c["manifest_exists"] = man_p.is_file()
    nsha = sha_norm(raw)
    r["obs"]["live_norm_sha"] = nsha
    r["obs"]["live_raw_sha"] = sha_raw(raw)
    r["obs"]["live_raw_bytes"] = len(raw)
    r["obs"]["live_norm_bytes"] = norm_len(raw)
    if man_p.is_file():
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            c["manifest_parses"] = True
        except Exception:
            man = None
            c["manifest_parses"] = False
        rows = [a for a in (man or {}).get("artifacts", []) if a.get("role") == "primary"]
        prow = next((a for a in rows
                     if a.get("unit_id") == uid
                     and str(a.get("path", "")).replace("\\", "/") == e["output_path"]), None)
        c["manifest_primary_row_matches_path"] = prow is not None
        if prow:
            c["manifest_primary_present"] = prow.get("present") is True
            c["manifest_primary_sha_eq_norm_live"] = prow.get("sha256") == nsha
            c["manifest_primary_bytes_eq_live_raw"] = prow.get("bytes") == len(raw)
            r["obs"]["manifest_primary_declared_sha"] = prow.get("sha256")
        c["manifest_counts_consistent"] = bool(
            man and man.get("present") == man.get("expected") == len(man.get("artifacts", [])))
        sup_bad = []
        for a in (man or {}).get("artifacts", []):
            if a.get("role") == "primary":
                continue
            sp = WS.joinpath(*str(a.get("path", "")).split("/"))
            if not sp.is_file():
                sup_bad.append(f"missing:{a.get('path')}")
                continue
            sraw = sp.read_bytes()
            if a.get("sha256") not in (sha_norm(sraw), sha_raw(sraw)):
                sup_bad.append(f"sha-no-match:{a.get('path')}")
        c["manifest_supporting_rows_ok"] = not sup_bad
        r["obs"]["manifest_supporting_bad"] = sup_bad
    else:
        c["manifest_parses"] = False
        c["manifest_primary_row_matches_path"] = False
        c["manifest_counts_consistent"] = False
        c["manifest_supporting_rows_ok"] = False
    rec_p = WS / "command-center/receipts" / f"{uid}.json"
    if rec_p.is_file():
        try:
            rec = json.loads(rec_p.read_text(encoding="utf-8"))
            row = next((a for a in rec.get("artifacts", []) if a.get("role") == "primary"), None)
            if row:
                r["obs"]["receipt_primary_sha"] = row.get("sha256")
                r["obs"]["receipt_sha_is_raw"] = row.get("sha256") == r["obs"]["live_raw_sha"]
                r["obs"]["receipt_sha_is_norm"] = row.get("sha256") == nsha
            r["obs"]["receipt_state"] = rec.get("state")
            rv = rec.get("reviewer") or {}
            r["obs"]["receipt_reviewer_verdict"] = rv.get("verdict")
            r["obs"]["receipt_reviewer_independent"] = rv.get("independent")
            r["obs"]["receipt_failure_classification"] = (rec.get("failure") or {}).get("classification")
        except Exception as exc:
            r["obs"]["receipt_read_error"] = repr(exc)[:300]

    # -- 4+5. live probes + mutation watch
    sha_before = nsha
    pdir = WS / "command-center/p2-wave/probes" / uid
    scripts = sorted(p for p in os.listdir(pdir) if p.startswith("probe") and p.endswith(".py")) \
        if pdir.is_dir() else []
    r["obs"]["probe_scripts"] = scripts
    probes = []
    probes_ok = bool(scripts)
    for s in scripts:
        res = run([sys.executable, "-B", f"command-center/p2-wave/probes/{uid}/{s}"])
        marker = f"SUCCESS:{uid}"
        ok = res["rc"] == 0 and marker in res["stdout"]
        probes_ok = probes_ok and ok
        probes.append({"script": s, "rc": res["rc"], "marker_ok": ok,
                       "tail": (res["stdout"] or res["stderr"])[-500:]})
    c["probes_live_exit0_with_success_marker"] = probes_ok
    r["obs"]["probes"] = probes
    c["artifact_unmutated_by_probes"] = (out.is_file() and sha_norm(out.read_bytes()) == sha_before)

    # -- 6. canonical measure gate
    g = run([sys.executable, "-B", "command-center/p2-wave/_measure_one_delivered.py", uid])
    c["canonical_gate_delivered"] = g["rc"] == 0 and "SUCCESS:delivered" in g["stdout"]
    r["obs"]["canonical_gate_tail"] = (g["stdout"] or g["stderr"])[-400:]

    r["all_hold"] = all(c.values())
    return r


def main() -> int:
    cat = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
    byid = {u["id"]: u for u in cat["work_units"]}
    report = []
    for uid in UNITS:
        e = byid[uid]
        res = review(uid, e)
        report.append(res)
        fails = [k for k, v in res["checks"].items() if v is not True]
        print(f"{uid} {'PASS' if res['all_hold'] else 'FAIL'}"
              + ("" if res["all_hold"] else "  fails=" + "; ".join(fails)))
        for f in (res["obs"].get("schema_canonical_errors") or [])[:2]:
            print(f"    canonical: {f}")
        for f in (res["obs"].get("schema_jsonschema_errors") or [])[:2]:
            print(f"    jsonschema: {f}")
    outp = WS / "_p2shard18-w2-review" / "r18_reviewer_wave2_report.json"
    outp.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("report:", outp)
    n_pass = sum(1 for r in report if r["all_hold"])
    print(f"SUMMARY pass={n_pass} fail={len(report)-n_pass}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

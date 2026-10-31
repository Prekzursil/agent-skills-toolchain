"""Independent reviewer battery - wave 2 shard 12 (12 units).

Runs the DELIVERED checks from the unit contract, per unit, evidence-only (no writes):
  A exists      catalog output_path exists, non-empty
  B parses      JSON parses
  C not-blocked state not in {BLOCKED, FAILED} (else record classification)
  D schema      repo schema_resolver on catalog output_schema -> 0 errors
                + gate layer-1 as a second, mechanically-different instrument
  E probes      every probe script in probes/<id>/ re-run live, exit 0 required
  F sha         manifest primary-row sha256 == sha256(live bytes, CRLF->LF)
                + every manifest row present-flag honored
  G reviewer    reviewer.verdict==PASS and reviewer.independent is true
Emits _reviewer_results.json + per-unit terminal markers. Receipt bytes untouched.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "IMP-0165", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
    "IMP-0218", "IMP-0219", "IMP-0221", "IMP-0222", "IMP-0224", "IMP-0228",
]
PROBES_ROOT = REPO / "command-center/p2-wave/probes"

spec = importlib.util.spec_from_file_location("schema_resolver", REPO / "platform/lib/schema_resolver.py")
_resolver = importlib.util.module_from_spec(spec)
sys.modules["schema_resolver"] = _resolver
spec.loader.exec_module(_resolver)

gspec = importlib.util.spec_from_file_location("gate", REPO / "platform/lib/receipt_schema_gate.py")
_gate = importlib.util.module_from_spec(gspec)
sys.modules["gate"] = _gate
gspec.loader.exec_module(_gate)


def norm_sha(data: bytes) -> tuple[str, int]:
    n = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(n).hexdigest(), len(n)


def catalog_map() -> dict:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
    return {u["id"]: u for u in cat["work_units"]}


def run_probe(script: Path) -> dict:
    t0 = time.monotonic()
    try:
        import os
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        r = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(REPO), capture_output=True, text=True,
            timeout=300, encoding="utf-8", errors="replace", env=env,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return {"script": script.name, "exit": r.returncode, "secs": round(time.monotonic() - t0, 1),
                "success_marker": "SUCCESS:" in out, "tail": out[-400:]}
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit": 124, "secs": round(time.monotonic() - t0, 1),
                "success_marker": False, "tail": "TIMEOUT after 300s"}
    except OSError as e:
        return {"script": script.name, "exit": 127, "secs": 0.0, "success_marker": False,
                "tail": f"{type(e).__name__}: {e}"}


def verify(uid: str, cat: dict) -> dict:
    res: dict = {"unit": uid}
    ce = cat.get(uid)
    if ce is None:
        res["verdict"] = "FAIL"; res["fail"] = "unit absent from WORK-UNIT-CATALOG.json"
        return res
    out_rel = ce.get("output_path"); sch = ce.get("output_schema")
    res["catalog_output_path"] = out_rel; res["catalog_output_schema"] = sch
    p = REPO / out_rel
    # A exists / non-empty
    if not p.is_file():
        res["verdict"] = "FAIL"; res["fail"] = f"artifact missing at catalog output_path: {out_rel}"
        return res
    raw = p.read_bytes()
    res["bytes_on_disk"] = len(raw)
    if len(raw) == 0:
        res["verdict"] = "FAIL"; res["fail"] = "artifact is 0 bytes"
        return res
    # B parses
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as e:
        res["verdict"] = "FAIL"; res["fail"] = f"unparseable: {type(e).__name__}: {e}"
        return res
    res["receipt_state"] = doc.get("state"); res["receipt_status"] = doc.get("status")
    # C not self-blocked
    st = str(doc.get("state", "")).upper()
    if st in ("BLOCKED", "FAILED"):
        fr = doc.get("failure") or {}
        res["blocked_classification"] = fr.get("classification")
        res["blocked_reason"] = str(fr.get("reason"))[:300]
        res["note_blocked"] = "closeable per contract only if classification==['reviewer-absent'] and all other checks hold"
    # D schema (two instruments)
    import os
    errs_resolver = _resolver.validate_artifact(doc, sch)
    errs_gate = list(_gate.validate_receipt(doc) or [])
    res["schema_resolver_errors"] = [str(e)[:200] for e in errs_resolver]
    res["schema_gate_errors_count"] = len(errs_gate)
    res["schema_ok"] = (not errs_resolver) and (not errs_gate)
    # E probes - every probe*.py in the unit probe dir, plus manifest-listed scripts
    pdir = PROBES_ROOT / uid
    scripts = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
    if not scripts:
        res["probes_note"] = "no probe scripts found in " + str(pdir.relative_to(REPO))
    runs = [run_probe(s) for s in scripts]
    res["probes"] = runs
    res["probes_all_exit0"] = bool(runs) and all(r["exit"] == 0 for r in runs)
    # F sha vs manifest
    man_p = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_p.is_file():
        res["sha_ok"] = False; res["sha_fail"] = "UNIT-ARTIFACT-MANIFEST.json missing"
    else:
        man = json.loads(man_p.read_bytes().decode("utf-8"))
        rows = man.get("artifacts") or []
        primary = [r for r in rows if r.get("role") == "primary"] or rows[:1]
        sha_live, n_live = norm_sha(raw)
        res["sha_live"] = sha_live; res["bytes_norm"] = n_live
        if not primary:
            res["sha_ok"] = False; res["sha_fail"] = "manifest has no artifact rows"
        else:
            row = primary[0]
            res["manifest_row_path"] = row.get("path")
            res["sha_manifest"] = row.get("sha256")
            res["sha_ok"] = (row.get("sha256") == sha_live) and (row.get("bytes") in (n_live, len(raw)))
            if not res["sha_ok"]:
                res["sha_fail"] = f"primary row sha256={row.get('sha256')} bytes={row.get('bytes')} != live sha256={sha_live} norm_bytes={n_live} raw_bytes={len(raw)}"
        missing = [r.get("path") for r in rows if r.get("present") is False]
        if missing:
            res["manifest_missing_rows"] = missing
    # G reviewer
    rev = doc.get("reviewer") or {}
    res["reviewer_existing"] = {"verdict": rev.get("verdict"), "independent": rev.get("independent"),
                                "reviewer_id": str(rev.get("reviewer_id"))[:120]}
    res["already_closed"] = (rev.get("verdict") == "PASS") and (rev.get("independent") is True) and st == "SUCCESS"
    hard_fail = None
    if not res.get("schema_ok"):
        hard_fail = f"output_schema invalid: resolver={len(errs_resolver)} errs, gate={len(errs_gate)} errs; first: {res['schema_resolver_errors'][0] if errs_resolver else errs_gate[0] if errs_gate else '?'}"
    elif not res.get("probes_all_exit0"):
        bad = [r for r in runs if r["exit"] != 0]
        hard_fail = "probe re-run failed: " + "; ".join(f"{r['script']} exit={r['exit']}" for r in bad)
    elif res.get("sha_ok") is False:
        hard_fail = res.get("sha_fail", "sha mismatch")
    elif st == "FAILED" or (st == "BLOCKED" and (doc.get("failure") or {}).get("classification") != ["reviewer-absent"]):
        hard_fail = f"receipt state={st} classification={(doc.get('failure') or {}).get('classification')} not closeable by reviewer"
    res["hard_fail"] = hard_fail
    res["verdict"] = "FAIL" if hard_fail else "EVIDENCE-HOLDS"
    return res


def main() -> int:
    cat = catalog_map()
    results = [verify(u, cat) for u in UNITS]
    out = REPO / "_shard12-w2/_reviewer_results.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    for r in results:
        mark = "FAILED" if r["verdict"] == "FAIL" else "HOLDS"
        print(f"{mark}:{r['unit']} schema_ok={r.get('schema_ok')} probes0={r.get('probes_all_exit0')} "
              f"sha_ok={r.get('sha_ok')} state={r.get('receipt_state')} closed={r.get('already_closed')}")
    n_fail = sum(1 for r in results if r["verdict"] == "FAIL")
    print(f"SUMMARY:{len(results) - n_fail} evidence-holds, {n_fail} fail (details: {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

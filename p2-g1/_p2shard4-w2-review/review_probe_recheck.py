#!/usr/bin/env python3
"""Independent reviewer wave-2 shard-4: live probe re-runs + second-mechanism schema check.

Re-derives every DELIVERED predicate live; trusts no builder prose.
Writes review_out.json with per-unit probe results and two-mechanism schema verdicts.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard4-w2-review" / "review_out.json"
IDS = ["AUD-0043","AUD-0044","AUD-0047","AUD-0053","AUD-0055","AUD-0057",
       "AUD-0064","AUD-0066","AUD-0069","AUD-0071","AUD-0072","AUD-0075"]

sys.path.insert(0, str(REPO / "platform" / "lib"))
import importlib.util
spec = importlib.util.spec_from_file_location("sr", REPO / "platform" / "lib" / "schema_resolver.py")
sr = importlib.util.module_from_spec(spec); sys.modules["sr"] = sr; spec.loader.exec_module(sr)

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in cat.get("work_units") or [] if isinstance(u, dict)}


def raw_jsonschema_shim(doc, schema_path: Path):
    """Mechanically different mechanism #2: raw jsonschema on the shim file itself,
    RefResolver anchored at the shim path (follows file:// refs on disk)."""
    import jsonschema
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    resolver = jsonschema.RefResolver(base_uri=schema_path.as_uri(), referrer=schema)
    errs = []
    for e in jsonschema.Draft202012Validator(schema, resolver=resolver).iter_errors(doc):
        errs.append(f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message[:200]}")
    return errs


def run_probe(pname: str, uid: str, timeout: int = 420):
    exe = sys.executable.replace("\\", "/")
    rel = f"command-center/p2-wave/probes/{uid}/{pname}"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.time()
    try:
        p = subprocess.run([exe, "-B", rel], cwd=str(REPO), capture_output=True,
                           text=True, timeout=timeout, env=env)
        rc, raw = p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired as e:
        rc = -999
        raw = f"TIMEOUT after {timeout}s; partial={((e.stdout or b'') if isinstance(e.stdout, bytes) else (e.stdout or ''))!r:.200}"
    return {"probe": pname, "rc": rc, "seconds": round(time.time() - t0, 1),
            "success_marker": "SUCCESS:" in raw, "failed_marker": "FAILED:" in raw,
            "tail": raw[-500:]}


def main() -> int:
    report = {}
    for uid in IDS:
        u = byid[uid]
        out = REPO / str(u["output_path"]).replace("\\", "/")
        doc = json.loads(out.read_text(encoding="utf-8"))
        entry = {"output_path": str(u["output_path"]), "probes": {}, "schema": {}}
        # second-mechanism schema check
        sp = REPO / str(u["output_schema"]).replace("\\", "/")
        try:
            errs2 = raw_jsonschema_shim(doc, sp)
            entry["schema"]["raw_shim_errors"] = len(errs2)
            entry["schema"]["raw_shim_first"] = errs2[0][:220] if errs2 else ""
        except Exception as e:
            entry["schema"]["raw_shim_errors"] = f"EXC {type(e).__name__}"
            entry["schema"]["raw_shim_first"] = str(e)[:220]
        entry["schema"]["resolver_errors"] = len(sr.validate_artifact(doc, u["output_schema"]))
        # probes: every probe*.py in the unit's probes dir
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        for pf in sorted(pdir.glob("probe*.py")):
            entry["probes"][pf.name] = run_probe(pf.name, uid)
            report[uid] = entry
            OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
            r = entry["probes"][pf.name]
            print(f"{uid} {pf.name} rc={r['rc']} {r['seconds']}s SUCCESS={r['success_marker']} FAILED={r['failed_marker']}", flush=True)
    print("DONE:review-probe-recheck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

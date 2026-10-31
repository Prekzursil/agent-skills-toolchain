#!/usr/bin/env python3
"""Resume independent reviewer battery - wave 3 shard 20 (12 units), 2026-10-26 evening.

Fresh instance; did not build these units. Re-derives EVERY check against current disk
state (after the 06:07 first-pass verdicts and the 07:04 / 19:28 post-verdict mutations).

Per unit:
  C1  catalog entry present, output_path + output_schema agree with the shard slice
  C2  artifact (the receipt) exists / non-empty / parses
  C3  not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  C4  unit_id matches
  C5  state=SUCCESS requires reviewer verdict=PASS + independent=true (receipt_core)
  C6  honesty-sentinel: state=SUCCESS requires a SUCCESS:<unit> sentinel (no FAILED:)
  C7  open P1 defects attached while state=SUCCESS is forbidden (receipt_core)
  C8  manifest_registration.registered=true while state=SUCCESS (receipt_core)
  C9  every probe*.py in probes/<id>/ re-run LIVE by this reviewer: exit 0 + SUCCESS:<unit>
  C10 UNIT-ARTIFACT-MANIFEST.json primary row: sha256 (CRLF->LF) + bytes match live artifact
  C11 manifest supporting rows: every row re-hashed, must match
  C12 output_schema: jsonschema Draft2020-12 vs catalog $defs target (absolute $ref registry)
  C13 canonical admission crosscheck: receipt_validate.py --json (C2 layer-1) must ACCEPT

ALL hold -> PASS closure confirmed in place (receipt already carries a valid independent
closure; no rewrite, no manifest drift). ANY fails -> FAIL, receipt left untouched.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
HERE = Path(__file__).resolve().parent
OUTDIR = HERE / "results"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
SHARD = json.loads((REPO / "_p2-shard20-w3-entries.json").read_text(encoding="utf-8"))
CATALOG = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
CAT_BY_ID = {u.get("id"): u for u in CATALOG["work_units"] if isinstance(u, dict)}
PROBE_TIMEOUT = int(os.environ.get("PROBE_TIMEOUT", "420"))


def norm_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    p = unquote(parsed.path)
    if parsed.scheme == "file" and len(p) >= 3 and p[0] == "/" and p[2] == ":":
        p = p[1:]
    return Path(p)


def make_registry() -> Registry:
    cache: dict[str, Resource] = {}

    def retrieve(uri: str) -> Resource:
        if uri not in cache:
            data = json.loads(uri_to_path(uri).read_text(encoding="utf-8"))
            cache[uri] = Resource.from_contents(data, default_specification=DRAFT202012)
        return cache[uri]

    return Registry(retrieve=retrieve)


REG = make_registry()


def pointer_get(doc, frag: str):
    cur = doc
    for part in frag.lstrip("#/").split("/"):
        cur = cur[part.replace("~1", "/").replace("~0", "~")]
    return cur


def run_probe(unit: str, script: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-B", script.as_posix()],
            cwd=str(REPO), capture_output=True, text=True, timeout=PROBE_TIMEOUT, env=env,
        )
        out = (proc.stdout or "").strip()
        return {
            "script": script.name,
            "exit": proc.returncode,
            "sentinel": ("SUCCESS:" + unit) in out,
            "tail": out[-300:],
            "err": (proc.stderr or "").strip()[-160:],
            "secs": round(time.monotonic() - t0, 1),
        }
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit": "TIMEOUT", "sentinel": False,
                "tail": "", "err": f"timeout {PROBE_TIMEOUT}s", "secs": round(time.monotonic() - t0, 1)}


def c2_admission(unit: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "command-center/receipt_validate.py", "--json",
             f"command-center/receipts/{unit}.json"],
            cwd=str(REPO), capture_output=True, text=True, timeout=300, env=env,
        )
        try:
            data = json.loads(proc.stdout)
        except Exception:
            return {"rc": proc.returncode, "raw": (proc.stdout + proc.stderr)[-300:]}
        return {"rc": proc.returncode, "out": data}
    except subprocess.TimeoutExpired:
        return {"rc": "TIMEOUT", "raw": "timeout 300s"}


def verify(unit: str) -> dict:
    checks: list[dict] = []

    def add(name: str, ok, detail="") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})

    ent = SHARD[unit]
    output_path = ent["output_path"].replace("\\", "/")
    output_schema = ent.get("output_schema", "")
    cat = CAT_BY_ID.get(unit)
    add("C1a-catalog-entry", cat is not None)
    add("C1b-output_path-agrees", bool(cat) and cat.get("output_path", "").replace("\\", "/") == output_path)
    add("C1c-output_schema-agrees", bool(cat) and cat.get("output_schema", "") == output_schema, cat.get("output_schema") if cat else "")

    art = REPO / output_path
    add("C2a-exists", art.is_file(), output_path)
    doc = None
    if art.is_file():
        raw = art.read_bytes()
        add("C2b-nonempty", len(raw) > 0, f"{len(raw)} bytes")
        try:
            doc = json.loads(raw.decode("utf-8"))
            add("C2c-parses", True, f"{len(raw)} bytes")
        except Exception as exc:
            add("C2c-parses", False, f"{type(exc).__name__}: {exc}")
    if doc is None:
        res = {"unit": unit, "PASS": False, "checks": checks}
        (OUTDIR / f"{unit}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(unit, "FAIL", fails(checks))
        return res

    st = str(doc.get("state") or "").upper()
    rev = doc.get("reviewer") or {}
    add("C3-not-self-blocked", st not in NOT_DELIVERING, st)
    add("C4-unit_id", str(doc.get("unit_id") or doc.get("id") or "") == unit, str(doc.get("unit_id")))
    add("C5a-reviewer-block-present", st != "SUCCESS" or bool(rev))
    add("C5b-reviewer-PASS", st != "SUCCESS" or str(rev.get("verdict") or "").upper() == "PASS", str(rev.get("verdict")))
    add("C5c-reviewer-independent", st != "SUCCESS" or rev.get("independent") is True, repr(rev.get("independent")))
    sent = str(doc.get("sentinel") or doc.get("completion_marker") or doc.get("completion_sentinel") or "")
    add("C6-success-sentinel-honest", st != "SUCCESS" or sent.startswith("SUCCESS:" + unit), sent[:160])
    defects = doc.get("defects") or []
    open_p1 = [d.get("id") for d in defects if isinstance(d, dict)
               and str(d.get("severity", "")).upper() == "P1" and str(d.get("status", "")).lower() == "open"]
    add("C7-no-open-P1-when-SUCCESS", st != "SUCCESS" or not open_p1, ",".join(map(str, open_p1)))
    mreg = doc.get("manifest_registration") or {}
    add("C8-manifest-registered-when-SUCCESS", st != "SUCCESS" or mreg.get("registered") is True, json.dumps(mreg)[:200])

    pdir = REPO / "command-center/p2-wave/probes" / unit
    probes = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
    add("C9a-two-probe-scripts", len(probes) >= 2, f"n={len(probes)}")
    probe_res = []
    for ps in probes:
        r = run_probe(unit, ps)
        r["ok"] = r["exit"] == 0 and r["sentinel"]
        probe_res.append(r)
        add(f"C9b-exit0+sentinel:{ps.name}", r["ok"], f"exit={r['exit']} sent={r['sentinel']} tail={r['tail'][-140:]}")

    mpath = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    add("C10a-manifest-exists", mpath.is_file())
    if mpath.is_file():
        try:
            man = json.loads(mpath.read_text(encoding="utf-8"))
            rows = man.get("artifacts") or []
            prim = [r for r in rows if str(r.get("path", "")).replace("\\", "/") == output_path]
            add("C10b-primary-row", len(prim) == 1, f"rows={len(rows)} primary={len(prim)}")
            if prim:
                sha_n, nb_n = norm_sha(art)
                add("C10c-primary-sha-match", prim[0].get("sha256") == sha_n,
                    f"manifest={str(prim[0].get('sha256'))[:16]} live={sha_n[:16]}")
                add("C10d-primary-bytes", prim[0].get("bytes") in (nb_n, art.stat().st_size),
                    f"manifest={prim[0].get('bytes')} norm={nb_n} raw={art.stat().st_size}")
            bad = []
            for r in rows:
                rp = str(r.get("path", "")).replace("\\", "/")
                if rp == output_path:
                    continue
                rf = REPO / rp
                if not rf.is_file():
                    bad.append(rp + ": absent")
                    continue
                s_n, _ = norm_sha(rf)
                if str(r.get("sha256")) != s_n:
                    bad.append(f"{Path(rp).name}: {str(r.get('sha256'))[:10]}!={s_n[:10]}")
            add("C11-supporting-rows-match", not bad, "; ".join(bad)[:380])
        except Exception as exc:
            add("C10b-primary-row", False, f"manifest-parse {type(exc).__name__}: {exc}")

    if output_schema:
        try:
            base, _, frag = output_schema.partition("#")
            sch = json.loads((REPO / base).read_text(encoding="utf-8"))
            target = pointer_get(sch, frag) if frag else sch
            errs = sorted(jsonschema.Draft202012Validator(target, registry=REG).iter_errors(doc),
                          key=lambda e: list(e.absolute_path))
            add("C12-output_schema-valid", not errs,
                "; ".join(f"{list(e.absolute_path)}: {e.message[:150]}" for e in errs[:5])[:380])
        except Exception as exc:
            add("C12-output_schema-valid", False, f"validator-error {type(exc).__name__}: {exc}")
    else:
        add("C12-output_schema-valid", False, "no output_schema declared")

    adm = c2_admission(unit)
    ok13 = adm.get("rc") == 0
    add("C13-c2-admission-ACCEPT", ok13, json.dumps(adm.get("out") or adm.get("raw"), ensure_ascii=False)[:300])

    ok = all(c["ok"] for c in checks)
    res = {"unit": unit, "PASS": ok, "state": st,
           "reviewer_existing": {k: rev.get(k) for k in ("reviewer_id", "verdict", "independent", "vendor")},
           "checks": checks, "probes": probe_res, "c2": adm}
    (OUTDIR / f"{unit}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(unit, "PASS" if ok else "FAIL", fails(checks))
    return res


def fails(checks: list[dict]) -> str:
    return "fails=" + ",".join(c["check"] for c in checks if not c["ok"]) if any(not c["ok"] for c in checks) else ""


if __name__ == "__main__":
    units = sys.argv[1:] or list(SHARD.keys())
    tally = {"PASS": [], "FAIL": []}
    for u in units:
        r = verify(u)
        tally["PASS" if r["PASS"] else "FAIL"].append(u)
    print("TALLY", json.dumps({k: v for k, v in tally.items()}))

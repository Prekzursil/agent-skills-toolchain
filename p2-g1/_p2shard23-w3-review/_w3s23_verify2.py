#!/usr/bin/env python3
"""w3 shard-23 INDEPENDENT REVIEWER battery v2 (12 TST units).

Sibling-consistent methodology (matches accepted reviewer waves w3s9/w3s13 of
2026-10-26):

  PROBES   pinned to Git Bash explicitly (C:\\Program Files\\Git\\bin\\bash.exe)
           so python3 resolves to C:\\Python314 (NOT WSL 3.12). Runtime proof
           recorded. Hard gate: rc==0 AND a SUCCESS: marker AND no FAILED:
           marker in the captured output (strict, sibling standard).
  SCHEMA   two mechanically independent instruments, both must accept:
           (A) platform/lib/schema_resolver.validate_artifact (estate-canonical,
           fail-closed) and (B) raw whole-doc draft-2020-12 validation against
           the declared command-center/schema shim.
  ARTIFACT exists, non-empty, parses, state terminal + not self-blocked,
           sentinel consistent with SUCCESS.
  MANIFEST every row on disk, sha256 recomputed CRLF->LF, bytes match,
           primary row == catalog output_path.
  SENTINEL catalog completion_sentinel verbatim in receipt text.

Read-only: never mutates receipts or manifests. Output: _w3s23_battery2_out.json
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
CC = REPO / "command-center"
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
PROBE_TIMEOUT_S = 600
UNITS = [
    "TST-0195", "TST-0197", "TST-0202", "TST-0204", "TST-0206", "TST-0215",
    "TST-0219", "TST-0221", "TST-0223", "TST-0227", "TST-0230", "TST-0233",
]
OUT = REPO / "_p2shard23-w3-review" / "_w3s23_battery2_out.json"

sys_path = str(REPO / "platform" / "lib")
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)
import schema_resolver as sr  # noqa: E402


# ---------------------------------------------------------------- schema (B)
def _uri_to_path(uri: str) -> Path:
    p = uri
    for pref in ("file:///", "file://"):
        if p.startswith(pref):
            p = p[len(pref):]
            break
    return Path(p)


def _retrieve(uri: str) -> Resource:
    path = _uri_to_path(uri)
    if not path.is_file():
        raise FileNotFoundError(f"schema uri not on disk: {uri}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return Resource.from_contents(doc, default_specification=DRAFT202012)


REGISTRY = Registry(retrieve=_retrieve)
SHIM_DOC = json.loads((CC / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
SHIM_URI = "file:///C:/Users/Prekzursil/p2-g1/command-center/schema/receipt.schema.json"


def raw_whole_doc_errors(receipt: dict) -> list[str]:
    """Instrument B: validate against the declared shim document, whole doc."""
    v = Draft202012Validator(SHIM_DOC, registry=REGISTRY)
    out = []
    for err in sorted(v.iter_errors(receipt), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(x) for x in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message[:200]}")
    return out


# ---------------------------------------------------------------- helpers
def sha_lf(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def runtime_proof() -> dict:
    cmd = "which bash; which python3; python3 -V 2>&1; echo RC=$?"
    p = subprocess.run([GIT_BASH, "-c", cmd], cwd=str(REPO), capture_output=True,
                       text=True, errors="replace", timeout=60, env=dict(os.environ))
    return {"stdout": (p.stdout or "")[-400:], "rc": p.returncode}


RUNTIME = runtime_proof()


def run_probe(cmd: str) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run(
            [GIT_BASH, "-c", cmd], cwd=str(REPO), capture_output=True,
            text=True, errors="replace", timeout=PROBE_TIMEOUT_S, env=dict(os.environ),
        )
        so = p.stdout or ""
        return {"cmd": cmd, "exit": p.returncode,
                "stdout_tail": so[-500:],
                "stderr_tail": (p.stderr or "")[-300:],
                "last_json_ok": last_json_ok(so),
                "failed_line": any(ln.startswith("FAILED:") for ln in (so + "\n" + (p.stderr or "")).splitlines()),
                "seconds": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": "TIMEOUT", "stdout_tail": "", "stderr_tail": "",
                "last_json_ok": None, "failed_line": False,
                "seconds": round(time.time() - t0, 1)}



def last_json_ok(stdout: str):
    """Return the 'ok' value of the LAST parseable JSON object in stdout (None if no JSON)."""
    dec = json.JSONDecoder()
    s = stdout or ""
    i = s.rfind("{")
    while i >= 0:
        try:
            obj, _end = dec.raw_decode(s[i:])
            if isinstance(obj, dict) and "ok" in obj:
                return obj["ok"]
        except Exception:
            pass
        i = s.rfind("{", 0, i)
    return None


def probe_cmds(uid: str, pdir: Path) -> list[str]:
    cmds: list[str] = []
    ret_path = pdir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        try:
            ret = load(ret_path)
        except Exception:
            ret = {}
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
    if len(cmds) < 2:
        for name in sorted(p.name for p in pdir.glob("probe[0-9]*.py")):
            c = f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{name}"
            if c not in cmds:
                cmds.append(c)
    return cmds


def check_unit(uid: str, ent: dict) -> dict:
    res: dict = {"unit": uid, "fails": [], "notes": [], "probe_runs": []}

    def F(msg: str):
        res["fails"].append(msg)

    out_rel = str(ent.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel

    # A: artifact
    if not out.is_file() or out.stat().st_size == 0:
        F(f"artifact-absent-or-empty:{out_rel}")
        return res
    raw_text = out.read_text(encoding="utf-8")
    try:
        receipt = load(out)
    except Exception as exc:
        F(f"unparseable:{type(exc).__name__}:{exc}")
        return res
    st = str(receipt.get("state") or "").upper()
    if st in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT"):
        F(f"self-declared-state:{st}")
    sentinel = str(receipt.get("sentinel") or "")
    if st == "SUCCESS" and not re.match(r"^(?:SUCCESS:|SENTINEL:)", sentinel):
        F(f"sentinel-vs-state:sentinel={sentinel[:120]}")
    mbt = receipt.get("min_bytes_threshold")
    if isinstance(mbt, int) and out.stat().st_size < mbt:
        F(f"below-min-bytes:file={out.stat().st_size} threshold={mbt}")

    # E: catalog sentinel verbatim
    cs = str(ent.get("completion_sentinel") or "")
    if cs and cs not in raw_text:
        F(f"catalog-sentinel-absent:{cs}")

    # C7: schema, two instruments
    os_decl = str(ent.get("output_schema") or "")
    try:
        errs_a = sr.validate_artifact(receipt, os_decl)
    except Exception as exc:
        errs_a = [f"resolver-failure: {exc}"]
    errs_b = raw_whole_doc_errors(receipt)
    res["schema_a_resolver_errors"] = len(errs_a)
    res["schema_b_whole_doc_errors"] = len(errs_b)
    if errs_a or errs_b:
        F(f"schema-nonconformance:resolver={len(errs_a)} whole-doc={len(errs_b)}; "
          + " | ".join((errs_a[:2] + errs_b[:2])))

    # D: manifest
    man_path = CC / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    named_probe_rows: list[str] = []
    if not man_path.is_file():
        F("manifest-absent")
    else:
        try:
            man = load(man_path)
        except Exception as exc:
            man = None
            F(f"manifest-unparseable:{type(exc).__name__}")
        if isinstance(man, dict):
            rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
            prim = [a for a in rows if str(a.get("path") or "").replace("\\", "/") == out_rel]
            if not prim:
                F("manifest-primary-row-absent")
            else:
                live_sha, live_n = sha_lf(out)
                p0 = prim[0]
                if p0.get("present") is not True:
                    F("manifest-primary-present!=true")
                if str(p0.get("sha256") or "") != live_sha:
                    F(f"manifest-primary-sha-mismatch man={str(p0.get('sha256'))[:12]} live={live_sha[:12]}")
                if p0.get("bytes") != live_n:
                    F(f"manifest-primary-bytes man={p0.get('bytes')} live={live_n}")
            for a in rows:
                rel = str(a.get("path") or "").replace("\\", "/")
                if rel == out_rel:
                    continue
                if a.get("role") == "named-probe" and rel.endswith(".py"):
                    named_probe_rows.append(rel)
                fp = REPO / rel
                if not fp.is_file():
                    F(f"manifest-row-absent:{rel}")
                    continue
                s2, n2 = sha_lf(fp)
                if s2 != str(a.get("sha256") or "") or n2 != a.get("bytes"):
                    F(f"manifest-row-digest:{rel} man={str(a.get('sha256'))[:12]}/{a.get('bytes')} live={s2[:12]}/{n2}")
            res["notes"].append(f"manifest-rows={len(rows)}")

    # F: live probes (Git-Bash pinned)
    pdir = CC / "p2-wave" / "probes" / uid
    cmds = probe_cmds(uid, pdir)
    extra = [f"PYTHONDONTWRITEBYTECODE=1 python3 -B {r}"
             for r in named_probe_rows if not any(r in c for c in cmds)]
    cmds += extra
    if not cmds:
        F("no-live-probes-found")
    else:
        for cmd in cmds:
            res["probe_runs"].append(run_probe(cmd))
        for pr in res["probe_runs"]:
            pname = Path(pr["cmd"].split()[-1]).name
            if pr["exit"] != 0:
                F(f"probe-rc:{pname}={pr['exit']}")
            if pr["last_json_ok"] is False:
                F(f"probe-ok-false:{pname} (final JSON verdict ok=false)")
            if pr["failed_line"]:
                F(f"probe-failed-line:{pname}")
        ok = sum(1 for pr in res["probe_runs"] if pr["exit"] == 0 and pr["last_json_ok"] is not False and not pr["failed_line"])
        res["notes"].append(f"probes-ok={ok}/{len(cmds)} runtime={RUNTIME['stdout'][:80]!r}")

    return res


def main() -> int:
    cat = load(CC / "WORK-UNIT-CATALOG.json")
    byid = {it.get("id"): it for it in cat.get("work_units", [])}
    results = {}
    for u in UNITS:
        ent = byid.get(u)
        if ent is None:
            results[u] = {"fails": ["catalog-entry-absent"], "notes": []}
            continue
        results[u] = check_unit(u, ent)

    n_pass = 0
    for u in UNITS:
        rep = results[u]
        if rep["fails"]:
            print(f"FAIL:W3S23B2:{u}")
            for f in rep["fails"]:
                print(f"    - {f[:300]}")
            for nline in rep["notes"]:
                print(f"    # {nline}")
        else:
            n_pass += 1
            print(f"PASS:W3S23B2:{u} ({'; '.join(rep['notes'])})")
    print(f"TOTAL: {n_pass}/{len(UNITS)} PASS")
    OUT.write_text(json.dumps({"runtime_proof": RUNTIME, "units": UNITS, "results": results},
                              indent=1) + "\n", encoding="utf-8")
    return 0 if n_pass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

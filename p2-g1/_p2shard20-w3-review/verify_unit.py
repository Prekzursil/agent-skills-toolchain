#!/usr/bin/env python3
"""Independent reviewer battery - wave 3 shard 20 (12 units).

Per unit: (1) artifact exists/non-empty/parses/not-self-blocked;
(2) receipt_core closure (state=SUCCESS requires reviewer PASS+independent);
(3) live probes re-run, exit 0 + SUCCESS sentinel required;
(4) manifest sha256 row match (CRLF->LF normalized) incl. supporting rows;
(5) output_schema validation via jsonschema against the catalog $defs target;
(6) catalog entry presence + output_path/output_schema agreement.
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
OUTDIR = REPO / "_p2shard20-w3-review/results"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
SHARD_ENTRIES = json.loads((REPO / "_p2-shard20-w3-entries.json").read_text(encoding="utf-8"))
CATALOG = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
CATALOG_BY_ID = {u.get("id"): u for u in CATALOG["work_units"] if isinstance(u, dict)}

_probe_timeout = int(os.environ.get("PROBE_TIMEOUT", "420"))


def norm_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    p = unquote(parsed.path)
    if parsed.scheme == "file" and len(p) >= 3 and p[0] == "/" and p[2] == ":":
        p = p[1:]  # file:///C:/... -> C:/...
    return Path(p)


def make_registry() -> Registry:
    cache = {}

    def retrieve(uri: str) -> Resource:
        if uri in cache:
            return cache[uri]
        path = uri_to_path(uri)
        data = json.loads(path.read_text(encoding="utf-8"))
        res = Resource.from_contents(data, default_specification=DRAFT202012)
        cache[uri] = res
        return res

    return Registry(retrieve=retrieve)


REGISTRY = make_registry()


def pointer_get(doc: dict, fragment: str):
    cur = doc
    for part in fragment.lstrip("#/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        cur = cur[part]
    return cur


def resolve_schema_target(output_schema: str):
    path_part, _, frag = output_schema.partition("#")
    base_path = REPO / path_part
    doc = json.loads(base_path.read_text(encoding="utf-8"))
    if not frag:
        return doc
    return pointer_get(doc, frag)


def run_probe(unit: str, script: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(script.relative_to(REPO))],
            cwd=str(REPO), capture_output=True, text=True, timeout=_probe_timeout, env=env,
        )
        full_out = (proc.stdout or "").strip()
        return {
            "script": str(script.relative_to(REPO)),
            "exit": proc.returncode,
            "stdout_has_success_sentinel": ("SUCCESS:" + unit) in full_out,
            "stdout_tail": full_out[-400:],
            "stderr_tail": (proc.stderr or "").strip()[-200:],
            "secs": round(time.monotonic() - t0, 1),
        }
    except subprocess.TimeoutExpired:
        return {"script": str(script.relative_to(REPO)), "exit": "TIMEOUT", "stdout_tail": "",
                "stderr_tail": "timeout after %ds" % _probe_timeout,
                "secs": round(time.monotonic() - t0, 1)}


def verify(unit: str) -> dict:
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})

    ent = SHARD_ENTRIES[unit]
    output_path = ent["output_path"].replace("\\", "/")
    output_schema = ent.get("output_schema", "")

    cat = CATALOG_BY_ID.get(unit)
    add("catalog-entry-present", cat is not None)
    if cat:
        add("catalog-output_path-agrees", cat.get("output_path", "").replace("\\", "/") == output_path, cat.get("output_path", ""))
        add("catalog-output_schema-agrees", cat.get("output_schema", "") == output_schema, cat.get("output_schema", ""))

    art = REPO / output_path
    add("artifact-exists", art.is_file(), output_path)
    if not art.is_file():
        result = {"unit": unit, "PASS": False, "checks": checks}
        (OUTDIR / (unit + ".json")).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        print(unit, "FAIL fails=artifact-exists")
        return result
    raw = art.read_bytes()
    add("artifact-nonempty", len(raw) > 0, "%d bytes" % len(raw))
    try:
        doc = json.loads(raw.decode("utf-8"))
        add("artifact-parses", True, "%d bytes" % len(raw))
    except Exception as exc:
        add("artifact-parses", False, "%s: %s" % (type(exc).__name__, exc))
        result = {"unit": unit, "PASS": False, "checks": checks}
        (OUTDIR / (unit + ".json")).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        print(unit, "FAIL fails=artifact-parses")
        return result
    st = str(doc.get("state") or "").upper()
    add("not-self-blocked", st not in NOT_DELIVERING, st)
    add("unit_id-match", str(doc.get("unit_id") or doc.get("id") or "") == unit, str(doc.get("unit_id")))

    rev = doc.get("reviewer") or {}
    if st == "SUCCESS":
        add("receipt-core-reviewer-present", bool(rev), json.dumps({k: rev.get(k) for k in ("reviewer_id", "verdict", "independent")}, ensure_ascii=False))
        add("receipt-core-verdict-PASS", str(rev.get("verdict") or "").upper() == "PASS", str(rev.get("verdict")))
        add("receipt-core-independent-true", rev.get("independent") is True, repr(rev.get("independent")))

    pdir = REPO / "command-center/p2-wave/probes" / unit
    probe_scripts = sorted(pdir.glob("probe*.py"))
    add("probes-dir-present", pdir.is_dir(), str(pdir))
    add("probe-scripts-found>=2", len(probe_scripts) >= 2, "%d" % len(probe_scripts))
    probe_results = []
    for ps in probe_scripts:
        r = run_probe(unit, ps)
        r["sentinel-ok"] = (r["exit"] == 0) and bool(r.get("stdout_has_success_sentinel"))
        probe_results.append(r)
        add("probe-exit0:" + ps.name, r["exit"] == 0, "exit=%s out=%s" % (r["exit"], r["stdout_tail"][-160:]))
        add("probe-sentinel:" + ps.name, r["sentinel-ok"], r["stdout_tail"][:120])
    named = doc.get("named_probes") if isinstance(doc.get("named_probes"), list) else []
    n_rec = len(named)
    for e in doc.get("evidence") or []:
        if isinstance(e, dict):
            n_rec += len(e.get("probes") or []) + len(e.get("named_probes") or [])
    for t in doc.get("tests") or []:
        if isinstance(t, dict) and (t.get("command") or (t.get("id") and t.get("result"))):
            n_rec += 1
    add("probes-recorded>=2", n_rec >= 2, "n=%d" % n_rec)

    mpath = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    add("manifest-exists", mpath.is_file())
    if mpath.is_file():
        try:
            man = json.loads(mpath.read_text(encoding="utf-8"))
            add("manifest-parses", True)
        except Exception as exc:
            add("manifest-parses", False, str(exc))
            man = None
        if man is not None:
            rows = man.get("artifacts") or []
            primary = [r for r in rows if str(r.get("path", "")).replace("\\", "/") == output_path]
            add("manifest-primary-row-present", len(primary) == 1, "rows=%d primary=%d" % (len(rows), len(primary)))
            if primary:
                row = primary[0]
                sha_n, nb_n = norm_sha(art)
                add("manifest-sha-match", row.get("sha256") == sha_n, "manifest=%s live=%s" % (str(row.get("sha256"))[:16], sha_n[:16]))
                add("manifest-bytes-match", row.get("bytes") in (nb_n, len(raw)), "manifest=%s live_norm=%d live_raw=%d" % (row.get("bytes"), nb_n, len(raw)))
            bad_supp = []
            for r in rows:
                rp = str(r.get("path", "")).replace("\\", "/")
                if rp == output_path:
                    continue
                rf = REPO / rp
                if not rf.is_file():
                    bad_supp.append(rp + ": absent")
                    continue
                s_n, _ = norm_sha(rf)
                if str(r.get("sha256")) != s_n:
                    bad_supp.append("%s: sha drift %s vs %s" % (rp, str(r.get("sha256"))[:12], s_n[:12]))
            add("manifest-supporting-rows-match", not bad_supp, "; ".join(bad_supp)[:300])

    if output_schema:
        try:
            sub = resolve_schema_target(output_schema)
            validator = jsonschema.Draft202012Validator(sub, registry=REGISTRY)
            errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
            add("output_schema-valid", not errs, "; ".join(
                "%s: %s" % (list(e.absolute_path), e.message[:180]) for e in errs[:6]
            )[:900])
        except Exception as exc:
            add("output_schema-valid", False, "validator-error %s: %s" % (type(exc).__name__, str(exc)[:200]))

    ok = all(c["ok"] for c in checks)
    result = {"unit": unit, "PASS": ok, "state": st,
              "reviewer": {k: rev.get(k) for k in ("reviewer_id", "verdict", "independent")},
              "checks": checks, "probes": probe_results}
    (OUTDIR / (unit + ".json")).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    fails = [c["check"] for c in checks if not c["ok"]]
    print(unit, "PASS" if ok else "FAIL", "fails=" + ",".join(fails) if fails else "")
    return result


if __name__ == "__main__":
    units = sys.argv[1:] or list(SHARD_ENTRIES.keys())
    for u in units:
        verify(u)

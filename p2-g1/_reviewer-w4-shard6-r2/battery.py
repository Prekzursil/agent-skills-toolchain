#!/usr/bin/env python3
"""Independent reviewer battery, wave-4 shard-6 re-review (r2).

Re-verifies 12 units from scratch: catalog entry, artifact predicate,
manifest sha256/bytes (CRLF->LF), output_schema (canonical resolver +
direct jsonschema + receipt admission, plus sibling satisfiability
control), receipt reviewer-block genuineness, and live probe
re-execution. Emits battery_out.json.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(REPO / "command-center"))
import schema_resolver  # noqa: E402  canonical instrument 1
import receipt_validate  # noqa: E402  instrument 3: admission

NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
UNITS = [
    "BLD-0049", "BLD-0058", "BLD-0059", "CC-0009", "CC-0010", "CC-0012",
    "CC-0019", "CNF-0077", "CNF-0132", "CNF-0133", "CNF-0136", "CNF-0147",
]
OUT_DIR = REPO / "_reviewer-w4-shard6-r2"
LOG_DIR = OUT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def lf_sha(p: Path):
    raw = p.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(raw), len(norm)


def mt(p: Path) -> str:
    if not p.exists():
        return "ABSENT"
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_probe(probe: Path, log: Path) -> dict:
    t0 = time.time()
    cp = subprocess.run(
        [sys.executable, "-I", str(probe)],
        cwd=str(REPO), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        fh.write(cp.stdout or "")
        fh.write("\n--STDERR--\n")
        fh.write(cp.stderr or "")
    out = (cp.stdout or "") + (cp.stderr or "")
    marker = ""
    for line in out.splitlines():
        if line.startswith(("SUCCESS:", "FAILED:")):
            marker = line.strip()
            break
    return {"rc": cp.returncode, "secs": round(time.time() - t0, 1),
            "marker": marker[:200], "log": str(log)}


cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"] if isinstance(u.get("id"), str)}

# sibling index: which units declare each schema part
schema_decl = {}
for uid_, e in units.items():
    for part in [x.strip() for x in str(e.get("output_schema") or "").split("+") if x.strip()]:
        schema_decl.setdefault(part, []).append(uid_)

results = {}
for uid in UNITS:
    e = units.get(uid, {})
    out_rel = str(e.get("output_path", "")).replace("\\", "/")
    schemas = [x.strip() for x in str(e.get("output_schema", "")).split("+") if x.strip()]
    r = {"catalog_entry": bool(e), "output_path": out_rel, "output_schema": schemas, "fails": []}

    # S2 artifact predicate
    art = REPO / out_rel if out_rel else None
    r["artifact"] = {}
    doc = None
    if not art or not art.is_file() or art.stat().st_size == 0:
        r["fails"].append("S2 artifact absent/empty at catalog output_path")
        r["artifact"] = {"exists": False}
    else:
        try:
            doc = json.loads(art.read_text(encoding="utf-8"))
            state = str(doc.get("state", "")).upper() if isinstance(doc, dict) else ""
            r["artifact"] = {
                "exists": True, "bytes": art.stat().st_size, "mtime": mt(art),
                "parses": True, "state": state,
                "sentinel_present": bool(doc.get("sentinel")) if isinstance(doc, dict) else False,
                "self_blocked": state in NOT_DELIVERING,
            }
            if state in NOT_DELIVERING:
                r["fails"].append("S2 artifact self-declares state=" + state)
            if isinstance(doc, dict) and not doc.get("sentinel"):
                r["fails"].append("S2 completion_sentinel missing from artifact")
        except Exception as exc:
            r["fails"].append("S2 artifact unparseable: " + type(exc).__name__)
            r["artifact"] = {"exists": True, "bytes": art.stat().st_size, "parses": False}

    # S3 manifest rows
    man_p = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    r["manifest"] = {"exists": man_p.is_file()}
    if man_p.is_file() and doc is not None:
        man = json.loads(man_p.read_text(encoding="utf-8"))
        rows = man.get("artifacts") or man.get("rows") or man.get("files") or []
        checks = []
        for row in rows:
            rp = str(row.get("path", "")).replace("\\", "/")
            f = REPO / rp
            if not f.is_file():
                checks.append({"path": rp, "on_disk": False})
                continue
            sha, raw_b, lf_b = lf_sha(f)
            checks.append({
                "path": rp,
                "sha_match": sha == row.get("sha256"),
                "declared_sha": str(row.get("sha256"))[:12],
                "live_sha": sha[:12],
                "bytes_raw": raw_b, "bytes_lf": lf_b,
                "declared_bytes": row.get("bytes"),
                "bytes_match_raw": raw_b == row.get("bytes"),
                "bytes_match_lf": lf_b == row.get("bytes"),
            })
        r["manifest"]["n_rows"] = len(checks)
        r["manifest"]["rows"] = checks
        bad_sha = [c for c in checks if c.get("on_disk") is False or c.get("sha_match") is False]
        bad_bytes = [c for c in checks
                     if c.get("bytes_match_raw") is False and c.get("bytes_match_lf") is False]
        if bad_sha:
            r["fails"].append("S3 manifest sha/exists mismatch on %d row(s): %s"
                              % (len(bad_sha), [c["path"] for c in bad_sha]))
        if bad_bytes:
            r["fails"].append("S3 manifest bytes mismatch on %d row(s): %s"
                              % (len(bad_bytes),
                                 [(c["path"], c["declared_bytes"], c["bytes_raw"], c["bytes_lf"])
                                  for c in bad_bytes]))

    # S4 schema instruments
    r["schema"] = {}
    if doc is not None:
        for s in schemas:
            try:
                errs = schema_resolver.validate_artifact(doc, s)
            except Exception as exc:
                errs = ["resolver exception: %s: %s" % (type(exc).__name__, exc)]
            slot = r["schema"].setdefault(s, {})
            slot["instrument1_canonical_errors"] = [x[:200] for x in errs[:10]]
            slot["n1"] = len(errs)
            if errs:
                r["fails"].append("S4 schema %s: %d violation(s), first: %s" % (s, len(errs), errs[0]))

            sibs = [x for x in schema_decl.get(s, []) if x != uid]
            clean_sibs = 0
            for sid in sibs:
                sp = REPO / str(units[sid].get("output_path", "")).replace("\\", "/")
                if not sp.is_file():
                    continue
                try:
                    sd = json.loads(sp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                try:
                    if not schema_resolver.validate_artifact(sd, s):
                        clean_sibs += 1
                except Exception:
                    pass
            slot["siblings_total"] = len(sibs)
            slot["siblings_clean"] = clean_sibs

            # instrument 2: direct jsonschema, raw schema file, no shim registry
            spath = REPO / s
            try:
                raw_schema = json.loads(spath.read_text(encoding="utf-8"))
                from jsonschema import Draft202012Validator
                v = Draft202012Validator(raw_schema)
                errs2 = sorted(v.iter_errors(doc), key=lambda x: list(x.absolute_path))
                fmt = [("/".join(map(str, err.absolute_path)) or "<root>") + ": " + err.message[:160]
                       for err in errs2]
                slot["instrument2_direct_errors"] = fmt[:10]
                slot["n2"] = len(fmt)
            except Exception as exc:
                slot["instrument2_direct_errors"] = ["instrument2 n/a: %s: %s" % (type(exc).__name__, exc)]
                slot["n2"] = None

        # instrument 3: receipt admission
        try:
            verdict, _u, reason = receipt_validate.admit_doc(doc, REPO)
            r["receipt_admission"] = {"verdict": verdict, "reason": reason[:300]}
        except Exception as exc:
            r["receipt_admission"] = {"verdict": "ERROR", "reason": "%s: %s" % (type(exc).__name__, exc)}

        # S5 reviewer-block genuineness + receipt_core rule
        rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else None
        r["reviewer_block"] = rev if rev else None
        if doc.get("state") == "SUCCESS":
            if not rev:
                r["fails"].append("S5 state=SUCCESS without reviewer block (receipt_core)")
            else:
                rid = str(rev.get("reviewer_id", ""))
                stamped = (rid == uid + "-independent-reviewer"
                           or "probe" in rid.lower()
                           or "fabricated" in rid.lower())
                r["reviewer_block_stamped"] = stamped
                if rev.get("verdict") != "PASS" or not rev.get("independent"):
                    r["fails"].append("S5 reviewer verdict/independent invalid: verdict=%s independent=%s"
                                      % (rev.get("verdict"), rev.get("independent")))
                if stamped:
                    r["fails"].append("S5 reviewer identity stamped/probe-derived, not a genuine "
                                      "independent closure: " + rid)

    # P probes
    pdir = REPO / "command-center/p2-wave/probes" / uid
    probes = sorted(pdir.glob("probe*.py"))
    r["probes"] = {}
    for pb in probes:
        res = run_probe(pb, LOG_DIR / (uid + "__" + pb.name + ".log"))
        r["probes"][pb.name] = res
        if res["rc"] != 0:
            r["fails"].append("P probe %s exit %d" % (pb.name, res["rc"]))
        elif not res["marker"].startswith("SUCCESS:"):
            r["fails"].append("P probe %s no SUCCESS marker: %s" % (pb.name, res["marker"][:120]))

    r["verdict"] = "FAIL" if r["fails"] else "PASS"
    results[uid] = r
    print("[%s] %s fails=%d" % (uid, r["verdict"], len(r["fails"])))
    for f_ in r["fails"]:
        print("   -", f_[:300])

my_schemas = sorted({x for u in UNITS for x in
                     [p.strip() for p in str(units[u].get("output_schema") or "").split("+") if p.strip()]})
out = {
    "reviewer": "review:w4s6-r2 independent re-review",
    "at": datetime.now(timezone.utc).isoformat(),
    "schema_mtimes": {s: mt(REPO / s) for s in my_schemas},
    "units": results,
}
(OUT_DIR / "battery_out.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("DONE", sum(1 for x in results.values() if x["verdict"] == "PASS"), "PASS /", len(results))

#!/usr/bin/env python3
"""Fresh independent reviewer battery - wave 2 shard 10 (12 units).

Written new from the fail-closed contract by the reviewer agent (not a re-run
of a prior instrument). Read-only on receipts: never executes builder scripts
(only the named probe*.py per unit)."""
import hashlib
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CC = REPO / "command-center"
PROBES = CC / "p2-wave" / "probes"
UNITS = ["IMP-0035", "IMP-0036", "IMP-0037", "IMP-0038", "IMP-0041", "IMP-0044",
         "IMP-0051", "IMP-0068", "IMP-0070", "IMP-0084", "IMP-0090", "IMP-0093"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
TMO = 300


def norm_sha(p: Path):
    b = p.read_bytes()
    raw = len(b)
    b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest(), raw, len(b)


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def schema_errs(schema_path: Path, inst):
    from jsonschema import Draft202012Validator
    from jsonschema.validators import RefResolver
    sch = load(schema_path)
    res = RefResolver(base_uri=schema_path.parent.as_uri() + "/", referrer=sch)
    v = Draft202012Validator(sch, resolver=res)
    out = []
    for e in v.iter_errors(inst):
        loc = "$" + "/".join(str(x) for x in e.absolute_path)
        out.append(loc + ": " + e.message[:200])
    return out


def main():
    catalog = load(CC / "WORK-UNIT-CATALOG.json")["work_units"]
    by_id = {u["id"]: u for u in catalog if isinstance(u, dict) and u.get("id")}
    results = []
    overall = True

    for uid in UNITS:
        fails, advises, probes_log = [], [], {}
        t0 = time.time()
        entry = by_id.get(uid)
        if entry is None:
            results.append({"unit": uid, "verdict": "FAIL",
                            "fails": ["catalog-entry missing"]})
            overall = False
            print("== " + uid + ": FAIL (no catalog entry)")
            continue
        out_rel = entry.get("output_path") or ""
        schema_rel = entry.get("output_schema") or ""
        art = REPO / out_rel
        if entry.get("owner_approval_required") is True:
            fails.append("owner-gate set (unexpected for this shard)")

        # 1. artifact: exists/non-empty/parses/not-self-blocked/closure
        doc = None
        rows = []
        if not art.is_file():
            fails.append("artifact-exists :: missing " + out_rel)
        else:
            if art.stat().st_size == 0:
                fails.append("artifact-nonempty :: 0 bytes")
            try:
                doc = load(art)
            except Exception as e:
                fails.append("artifact-parses-json :: " + str(e)[:160])
            if doc is not None:
                state = str(doc.get("state") or "").upper()
                if state in NOT_DELIVERING:
                    fails.append("state-self-declared :: " + state)
                rid = str(doc.get("unit_id") or doc.get("id") or "")
                if rid != uid:
                    fails.append("receipt-unit-id :: %r != %r" % (rid, uid))
                sent = str(doc.get("sentinel") or doc.get("completion_sentinel") or "")
                if sent and not sent.startswith("SUCCESS:" + uid):
                    fails.append("sentinel-form :: " + sent[:100])
                rev = doc.get("reviewer") or {}
                if state == "SUCCESS" and not (
                        rev.get("verdict") == "PASS" and rev.get("independent") is True):
                    fails.append(
                        "closure :: state=SUCCESS needs reviewer PASS+independent, "
                        "got %r/%r" % (rev.get("verdict"), rev.get("independent")))
                fcl = set(str(x).lower() for x in
                          ((doc.get("failure") or {}).get("classification") or []))
                if fcl & {"reviewer-absent", "reviewer-unavailable",
                          "reviewer-unavailable-cross-vendor"}:
                    advises.append("failure.classification reviewer-absent mark: "
                                   + str(sorted(fcl))[:120])

        # 2. live probes re-run by the reviewer
        pdir = PROBES / uid
        probes_files = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
        if not probes_files:
            fails.append("probes-present :: none found in " + str(pdir))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for pf in probes_files:
            try:
                r = subprocess.run([sys.executable, "-B", str(pf)], cwd=str(REPO),
                                   capture_output=True, text=True, timeout=TMO, env=env)
                rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired:
                rc, out = 124, "TIMEOUT"
            lines = [ln for ln in out.strip().splitlines() if ln.strip()]
            marker = lines[-1][:130] if lines else "(silent)"
            ok_marker = any(ln.startswith("SUCCESS:" + uid) for ln in lines)
            probes_log[pf.name] = rc
            if rc != 0:
                fails.append("probe-exit0:%s :: rc=%d :: %s" % (pf.name, rc, marker))
            elif not ok_marker:
                fails.append("probe-success-marker:%s :: last=%s" % (pf.name, marker))

        # 3. manifest sha256 (CRLF->LF) vs live artifact, post-probe re-read
        man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_path.is_file():
            fails.append("manifest-exists :: missing")
        else:
            try:
                man = load(man_path)
            except Exception as e:
                man = None
                fails.append("manifest-parses :: " + str(e)[:140])
            if man is not None:
                rows = man.get("artifacts") or man.get("rows") or []
                if not rows:
                    fails.append("manifest-rows :: empty")
                row = next((a for a in rows
                            if Path(str(a.get("path", ""))).as_posix()
                            == Path(out_rel).as_posix()), None)
                if row is None:
                    fails.append("manifest-row-for-output-path :: none for " + out_rel)
                else:
                    live, _, _ = norm_sha(art)
                    if row.get("sha256") != live:
                        fails.append("sha256-match :: manifest=%s live=%s (CRLF->LF)"
                                     % (str(row.get("sha256"))[:12], live[:12]))
                    try:
                        load(art)
                    except Exception as e:
                        fails.append("artifact-stable-post-probes :: " + str(e)[:140])
                for a in rows:
                    if a is row:
                        continue
                    ap = REPO / str(a.get("path", ""))
                    if ap.is_file():
                        ash, _, _ = norm_sha(ap)
                        if ash != a.get("sha256"):
                            advises.append("manifest-row-drift(advisory): "
                                           + str(a.get("path"))[:90])
                    else:
                        advises.append("manifest-row-missing(advisory): "
                                       + str(a.get("path"))[:90])

        # 4. output_schema validation (primary; secondary = advisory discovery)
        if schema_rel:
            parts = [p.strip().split()[0] for p in schema_rel.split("+")]
            primary = REPO / parts[0]
            if not primary.is_file():
                fails.append("schema-file-exists :: " + parts[0])
            elif doc is not None:
                errs = schema_errs(primary, doc)
                if errs:
                    fails.append("output-schema-valid :: [%d errors] %s"
                                 % (len(errs), " | ".join(errs[:3])[:420]))
                else:
                    for extra in parts[1:]:
                        ep = REPO / extra
                        if not ep.is_file():
                            advises.append("secondary-schema-missing: " + extra)
                            continue
                        cands = []
                        if pdir.is_dir():
                            cands += [p for p in sorted(pdir.glob("*.json"))
                                      if p.name not in ("UNIT-ARTIFACT-MANIFEST.json",
                                                        "SUBAGENT-RETURN.json")]
                        for a2 in rows:
                            ap2 = REPO / str(a2.get("path", ""))
                            if ap2.is_file() and ap2.suffix == ".json" and ap2 != art:
                                cands.append(ap2)
                        hits = []
                        for c in cands:
                            try:
                                if not schema_errs(ep, load(c)):
                                    hits.append(c)
                            except Exception:
                                pass
                        if hits:
                            advises.append("secondary-schema-ok:" + ep.name + " <- "
                                           + ",".join(h.name for h in hits[:3]))
                        else:
                            advises.append("secondary-schema:" + ep.name
                                           + " no clean candidate found among "
                                           + str([c.name for c in cands])[:120])

        # 5. cross-instrument: the repo's own admission gate
        try:
            ra = subprocess.run(
                [sys.executable, "command-center/receipt_validate.py", str(art)],
                cwd=str(REPO), capture_output=True, text=True, timeout=120)
            txt = [ln for ln in ((ra.stdout or "") + (ra.stderr or "")).splitlines()
                   if ln.strip()]
            adm_line = txt[-1][:200] if txt else "rc=%d" % ra.returncode
            if ra.returncode != 0:
                fails.append("repo-admission-validator :: " + adm_line)
        except Exception as e:
            fails.append("repo-admission-validator :: exec-error " + str(e)[:100])

        verdict = "PASS" if not fails else "FAIL"
        if fails:
            overall = False
        results.append({"unit": uid, "verdict": verdict, "artifact": out_rel,
                        "probes_rc": probes_log, "advisories": advises,
                        "fails": fails, "seconds": round(time.time() - t0, 1)})
        print("== %s: %s (%.1fs)" % (uid, verdict, time.time() - t0))
        for f in fails:
            print("   FAIL:", f)
        for a in advises:
            print("   [adv]", a)

    outp = REPO / "_reviewer10w2" / "rerun" / "independent_results.json"
    outp.write_text(json.dumps(results, indent=1), encoding="utf-8")
    n_ok = sum(1 for r in results if r["verdict"] == "PASS")
    tail = ("SUCCESS:shard10-w2-review all hold" if overall
            else "FAILED:shard10-w2-review")
    print("\nBATTERY: %d/%d PASS -> %s" % (n_ok, len(UNITS), tail))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Independent reviewer battery, wave-3 shard-21 round 3 (fresh code).

Per unit: catalog entry / artifact / state-coherence / manifest rows (all,
CRLF->LF sha) / live probe re-runs (named + every probe*.py) / no-mutation
witness / output_schema via TWO transports (T1 resolver, T2 own registry).
Writes incremental results to results.json; log to battery.log.
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, time, traceback
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = ROOT / "_reviewer-w3s21-r3-mine"
UNITS = ["TST-0151", "TST-0155", "TST-0158", "TST-0161", "TST-0162", "TST-0163",
         "TST-0164", "TST-0165", "TST-0166", "TST-0168", "TST-0169", "TST-0171"]

sys.path.insert(0, str(ROOT / "platform" / "lib"))
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def log(msg: str):
    with open(OUT / "battery.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ---------------- T2 independent schema transport ----------------
_T2_REG = None


def build_t2():
    """Own registry: map the source/ast-integrate file:// URIs to THIS root."""
    from jsonschema import Draft202012Validator  # noqa: F401
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
    prefix = "file:///C:/Users/Prekzursil/source/ast-integrate/"

    def retrieve(uri: str):
        assert uri.startswith(prefix), "T2: unexpected uri " + uri
        rel = uri[len(prefix):]
        p = ROOT / rel.replace("/", os.sep)
        if not p.is_file():
            raise FileNotFoundError(str(p))
        doc = json.loads(p.read_text(encoding="utf-8"))
        return Resource.from_contents(doc, default_specification=DRAFT202012)

    reg = Registry(retrieve=retrieve)
    for rel in ("command-center/schema/receipt.schema.json",
                "platform/schema/artifact-class-profiles.schema.json",
                "platform/schema/receipt.schema.json"):
        p = ROOT / rel.replace("/", os.sep)
        doc = json.loads(p.read_text(encoding="utf-8"))
        reg = reg.with_resource(doc["$id"],
                                Resource.from_contents(doc, default_specification=DRAFT202012))
    return reg


def t2_errors(artifact, declared: str):
    """Parse the catalog ref myself, walk the shim fragment, validate."""
    global _T2_REG
    from jsonschema import Draft202012Validator
    if _T2_REG is None:
        _T2_REG = build_t2()
    m = re.match(r"^(.+\.json)#/(\$defs/)(.+)$", declared)
    if not m:
        return ["T2: cannot parse declared ref " + declared]
    shim_rel = m.group(1)
    frag = m.group(3)
    shim_rel = shim_rel.split("ast-integrate/")[-1]
    shim_path = ROOT / shim_rel.replace("/", os.sep)
    if not shim_path.is_file():
        return ["T2: shim missing " + str(shim_path)]
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    node = shim.get("$defs", {}).get(frag)
    if node is None:
        return ["T2: shim fragment missing " + frag]
    schema = {"$ref": node["$ref"]} if isinstance(node, dict) and "$ref" in node else node
    v = Draft202012Validator(schema, registry=_T2_REG)
    errs = []
    for e in v.iter_errors(artifact):
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(loc + ": " + e.message)
    return sorted(errs)


# ---------------- probe collection ----------------
def collect_probes(uid: str):
    """Named probes from SUBAGENT-RETURN first, then every probe*.py in dir."""
    d = ROOT / "command-center" / "p2-wave" / "probes" / uid
    named, scripts = [], []
    sr = d / "SUBAGENT-RETURN.json"
    if sr.is_file():
        try:
            s = json.loads(sr.read_text(encoding="utf-8"))
            for np in s.get("named_probes", []):
                cmd = np.get("command", "")
                mm = re.search(r"([A-Za-z0-9_/.-]+\.py)", cmd)
                if mm:
                    named.append((np.get("id", "?"), mm.group(1)))
        except Exception as e:
            log(uid + ": SUBAGENT-RETURN parse error " + repr(e))
    if d.is_dir():
        for f in sorted(d.glob("probe*.py")):
            rel = str(f.relative_to(ROOT)).replace(os.sep, "/")
            if not any(rel == n[1] for n in named):
                scripts.append(("extra:" + f.name, rel))
    return named + scripts


def run_probe(rel: str):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT / "tools") + os.pathsep + env.get("PYTHONPATH", "")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-B", rel], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, timeout=600)
        rc, out = p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        rc, out = 124, "TIMEOUT after 600s"
    except Exception as e:
        rc, out = 1, type(e).__name__ + ": " + str(e)
    return {"probe": rel, "rc": rc, "secs": round(time.time() - t0, 1), "tail": out[-400:]}


# ---------------- main ----------------
def witness_sha(uid):
    rp = ROOT / "command-center" / "receipts" / (uid + ".json")
    mp = ROOT / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    return {str(p): (lf_sha(p) if p.is_file() else None) for p in (rp, mp)}


def save(results):
    with open(OUT / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)


def main():
    from schema_resolver import validate_artifact as t1_validate
    cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wus = {u["id"]: u for u in cat["work_units"] if u.get("id")}
    results = {}
    for uid in UNITS:
        log("=== " + uid + " start " + time.strftime("%H:%M:%S") + " ===")
        R = {"unit": uid, "checks": {}, "probe_runs": [], "failing": []}
        try:
            u = wus.get(uid)
            R["checks"]["catalog-entry-present"] = u is not None
            if u is None:
                R["failing"].append("catalog-entry-present")
                results[uid] = R
                save(results)
                continue
            out_path = u.get("output_path")
            rp = ROOT / out_path.replace("/", os.sep)
            R["output_path"] = out_path
            # B: artifact
            R["checks"]["artifact-exists"] = rp.is_file()
            R["checks"]["artifact-nonempty"] = rp.is_file() and rp.stat().st_size > 0
            doc = None
            try:
                doc = json.loads(rp.read_text(encoding="utf-8"))
                R["checks"]["artifact-parses"] = True
            except Exception as e:
                R["checks"]["artifact-parses"] = False
                R["failing"].append("artifact-parses: " + repr(e))
            if doc is not None:
                R["checks"]["unit_id-match"] = doc.get("unit_id") == uid or doc.get("id") == uid
                state = str(doc.get("state") or "").upper()
                R["state"] = state
                sent = str(doc.get("sentinel") or "")
                csent = str(doc.get("completion_sentinel") or "")
                R["sentinel"] = sent[:120]
                R["completion_sentinel"] = csent[:120]
                R["failure_classification"] = doc.get("failure_classification")
                R["checks"]["not-self-blocked-or-failed"] = state not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
                rev = doc.get("reviewer") or {}
                rev_ok = isinstance(rev, dict) and rev.get("verdict") == "PASS" and rev.get("independent") is True
                if state == "SUCCESS":
                    R["checks"]["closure-consistent"] = rev_ok
                    R["checks"]["sentinel-coherent"] = not re.match(r"^(FAILED|BLOCKED|TIMEOUT|SEVERED)", sent)
                elif state == "BLOCKED":
                    R["checks"]["closure-consistent"] = True
                    R["checks"]["sentinel-coherent"] = True
                else:
                    R["checks"]["closure-consistent"] = False
                    R["checks"]["sentinel-coherent"] = False
                R["reviewer_now"] = ({k: rev.get(k) for k in ("reviewer_id", "verdict", "independent")}
                                     if isinstance(rev, dict) else None)
                R["checks"]["catalog-sentinel-text-present"] = (csent.split(" ")[0] in rp.read_text(encoding="utf-8", errors="replace")) if csent else False
                # F: schema BOTH transports
                t1 = t1_validate(doc, u.get("output_schema"))
                t2 = t2_errors(doc, u.get("output_schema"))
                R["schema_t1_errors"] = len(t1)
                R["schema_t2_errors"] = len(t2)
                R["schema_t1_sample"] = t1[:3]
                R["schema_t2_sample"] = t2[:3]
                R["schema_t1_eq_t2"] = (len(t1) == len(t2))
                R["checks"]["output_schema-valid"] = (len(t1) == 0 and len(t2) == 0)
            # E: manifest
            mp = ROOT / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
            R["checks"]["manifest-present"] = mp.is_file()
            if mp.is_file():
                try:
                    m = json.loads(mp.read_text(encoding="utf-8"))
                    R["checks"]["manifest-parses"] = True
                    rows = m.get("artifacts", [])
                    row_results = []
                    for a in rows:
                        apath = ROOT / a["path"].replace("/", os.sep)
                        ok_exists = apath.is_file()
                        ok_sha = ok_exists and lf_sha(apath) == a.get("sha256")
                        row_results.append({"path": a["path"], "role": a.get("role"),
                                            "exists": ok_exists, "sha": ok_sha})
                    R["manifest_rows"] = row_results
                    R["checks"]["manifest-all-rows-match"] = all(r["exists"] and r["sha"] for r in row_results)
                    prim = [r for r in row_results if r["role"] == "primary"]
                    R["checks"]["manifest-primary-row"] = len(prim) == 1 and prim[0]["exists"] and prim[0]["sha"]
                    R["checks"]["manifest-primary-is-catalog-path"] = bool(rows) and any(
                        a.get("role") == "primary" and a["path"].replace("/", os.sep) == out_path.replace("/", os.sep)
                        for a in rows)
                except Exception as e:
                    R["checks"]["manifest-parses"] = False
                    R["failing"].append("manifest-parses: " + repr(e))
            results[uid] = R
            save(results)
            # D: live probes
            pre = witness_sha(uid)
            probes = collect_probes(uid)
            R["checks"]["probes-registered"] = len(probes) > 0
            for pid, rel in probes:
                res = run_probe(rel)
                res["id"] = pid
                R["probe_runs"].append(res)
                log(uid + " probe " + rel + " rc=" + str(res["rc"]) + " " + str(res["secs"]) + "s")
                save(results)
            post = witness_sha(uid)
            R["checks"]["no-mutation-by-probes"] = (pre == post)
            R["checks"]["probes-all-exit0"] = (len(R["probe_runs"]) > 0 and
                                               all(p["rc"] == 0 for p in R["probe_runs"]))
            results[uid] = R
            save(results)
            log("=== " + uid + " done probes_all0=" + str(R["checks"].get("probes-all-exit0")) + " ===")
        except Exception:
            R["failing"].append("battery-exception: " + traceback.format_exc()[-600:])
            results[uid] = R
            save(results)
    log("ALL UNITS DONE")


if __name__ == "__main__":
    main()

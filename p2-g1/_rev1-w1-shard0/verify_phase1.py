#!/usr/bin/env python3
"""Independent reviewer phase-1: mechanical verification of 12 shard0/w1 units.

Read-only except probe side-effects (nc_live.json etc. which the probes own).
Writes phase1_report.json next to this script.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, time
from pathlib import Path
import jsonschema

REPO = Path.home() / "p2-g1"
CC = REPO / "command-center"
IDS = ["ADV-0006", "ADV-0019", "ADV-0027", "ADV-0028", "ADV-0029", "ADV-0033",
       "ADV-0037", "ADV-0038", "ADV-0060", "ADV-0096", "ADV-0124", "ADV-0127"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 300


def sha_norm(p: Path) -> tuple[str, int]:
    raw = p.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def sha_raw(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_probe(script: Path) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    t0 = time.time()
    try:
        cp = subprocess.run([sys.executable, "-B", str(script)], cwd=str(REPO),
                            capture_output=True, text=True, timeout=PROBE_TIMEOUT, env=env)
        out = (cp.stdout or "") + (cp.stderr or "")
        return {"script": script.name, "exit": cp.returncode,
                "secs": round(time.time() - t0, 1), "tail": out.strip()[-220:]}
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit": -99, "secs": round(time.time() - t0, 1),
                "tail": "TIMEOUT after %ss" % PROBE_TIMEOUT}
    except Exception as e:
        return {"script": script.name, "exit": -98, "secs": round(time.time() - t0, 1),
                "tail": "SPAWN-ERR %s: %s" % (type(e).__name__, e)}


def main() -> int:
    report = {}
    cat = json.loads((CC / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wu = {u["id"]: u for u in cat["work_units"]}

    for uid in IDS:
        r = {"unit": uid}
        entry = wu.get(uid)
        r["in_catalog"] = entry is not None
        if not entry:
            report[uid] = r
            continue
        out_path = REPO / entry["output_path"]
        r["output_path"] = entry["output_path"]

        # artifact: exists / non-empty / parses / not self-blocked
        art = {"exists": out_path.exists()}
        doc = None
        if art["exists"]:
            art["size"] = out_path.stat().st_size
            art["nonempty"] = art["size"] > 0
            try:
                doc = json.loads(out_path.read_text(encoding="utf-8"))
                art["parses"] = True
            except Exception as e:
                art["parses"] = False
                art["parse_err"] = ("%s: %s" % (type(e).__name__, e))[:150]
            if art.get("parses") and isinstance(doc, dict):
                ts = str(doc.get("state") or "")
                art["top_state"] = ts
                art["self_blocked"] = ts.upper() in NOT_DELIVERING
                art["unit_id_matches"] = doc.get("unit_id") in (None, uid)
            elif art.get("parses"):
                art["self_blocked"] = False
                art["unit_id_matches"] = True
        r["artifact"] = art

        # schema validation
        sch_rel = entry.get("output_schema")
        sch = {"path": sch_rel, "exists": False, "valid": False, "errors": []}
        if sch_rel:
            sp = REPO / sch_rel
            sch["exists"] = sp.exists()
            if sch["exists"] and art.get("parses"):
                try:
                    schema = json.loads(sp.read_text(encoding="utf-8"))
                    v = jsonschema.Draft202012Validator(schema)
                    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
                    sch["n_errors"] = len(errs)
                    sch["errors"] = ["%s: %s" % (list(e.path), e.message[:160]) for e in errs[:5]]
                    sch["valid"] = len(errs) == 0
                except Exception as e:
                    sch["errors"] = [("validator-crash %s: %s" % (type(e).__name__, e))[:160]]
        r["schema"] = sch

        # manifest + live sha
        man_rel = "command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid
        mp = REPO / man_rel
        m = {"path": man_rel, "exists": mp.exists()}
        if m["exists"]:
            try:
                man = json.loads(mp.read_text(encoding="utf-8"))
                rows = man.get("artifacts", [])
                m["n_rows"] = len(rows)
                prim = [a for a in rows if a.get("path") == entry["output_path"]]
                m["primary_row_present_flag"] = prim[0].get("present") if prim else None
                if prim:
                    sn, ln = sha_norm(out_path)
                    sr = sha_raw(out_path)
                    m["live_sha_lf"] = sn
                    m["live_sha_raw"] = sr
                    m["manifest_sha"] = prim[0].get("sha256")
                    m["sha_match_lf"] = sn == prim[0].get("sha256")
                    m["sha_match_raw"] = sr == prim[0].get("sha256")
                    m["manifest_bytes"] = prim[0].get("bytes")
                    m["live_norm_bytes"] = ln
                    m["bytes_match_norm"] = ln == prim[0].get("bytes")
                else:
                    m["primary_row"] = "MISSING"
                m["missing_support_rows"] = [a["path"] for a in rows
                                             if not (REPO / a["path"]).exists()]
            except Exception as e:
                m["error"] = ("%s: %s" % (type(e).__name__, e))[:160]
        r["manifest"] = m

        # probes: receipt-named pair + standard delivery-predicate / independent-recheck
        core_p = REPO / ("command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid)
        named, core = [], {}
        if core_p.exists():
            try:
                core = json.loads(core_p.read_text(encoding="utf-8"))
                for p in core.get("named_probes", []):
                    if isinstance(p, dict):
                        parts = p.get("command", "").split()
                        if parts:
                            named.append(parts[-1])
            except Exception as e:
                core = {"_err": str(e)}
        here = REPO / ("command-center/p2-wave/probes/%s" % uid)
        scripts, seen = [], set()
        for rel in named + ["probe1_delivery_predicate.py", "probe2_independent_recheck.py"]:
            sp = here / Path(rel).name
            if sp.exists() and str(sp) not in seen:
                seen.add(str(sp))
                scripts.append(sp)
        r["core_state"] = core.get("state")
        r["core_failure"] = (core.get("failure", {}).get("classification")
                             if isinstance(core.get("failure"), dict) else None)
        r["core_reviewer"] = core.get("reviewer")
        probes = [run_probe(s) for s in scripts]
        r["probes"] = probes
        r["probes_all_zero"] = bool(probes) and all(p["exit"] == 0 for p in probes)
        report[uid] = r

    out = Path(__file__).resolve().parent / "phase1_report.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")

    for uid, r in report.items():
        a = r.get("artifact", {})
        art_ok = a.get("exists") and a.get("parses") and not a.get("self_blocked", False)
        m = r.get("manifest", {})
        print("%s: art_ok=%s size=%s top_state=%s schema_valid=%s sha_lf=%s sha_raw=%s "
              "bytes_norm=%s probes0=%s core_state=%s" % (
                  uid, art_ok, a.get("size"), a.get("top_state"),
                  r.get("schema", {}).get("valid"), m.get("sha_match_lf"),
                  m.get("sha_match_raw"), m.get("bytes_match_norm"),
                  r.get("probes_all_zero"), r.get("core_state")))
        if r.get("schema", {}).get("errors"):
            print("    schema-err: %s" % r["schema"]["errors"][0])
        for p in r.get("probes", []):
            mark = "" if p["exit"] == 0 else "  <<< %s" % p["tail"][:150]
            print("    %s: exit=%s (%ss)%s" % (p["script"], p["exit"], p["secs"], mark))
    return 0


if __name__ == "__main__":
    sys.exit(main())

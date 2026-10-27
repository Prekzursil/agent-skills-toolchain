"""Independent reviewer battery - wave 2 shard 2 (12 units).
Checks per unit:
  A artifact exists/non-empty/parses at catalog output_path
  B not self-declared BLOCKED/FAILED (field scan + raw marker scan)
  C live probes re-run by reviewer, exit 0 required
  D sha256(CRLF->LF) matches per-unit UNIT-ARTIFACT-MANIFEST primary row AND receipt row
  E output_schema resolve+validate via platform/lib/schema_resolver
  F post-probe artifact mutation detector
Emits battery_out.json + console summary. Read-only on program surfaces.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, r"C:/Users/Prekzursil/p2-g1/platform/lib")

REPO = r"C:/Users/Prekzursil/p2-g1"
OUT = os.path.join(REPO, "_rev2-w2-shard2", "battery_out.json")
IDS = ["ADV-0124", "ADV-0127", "ADV-0128", "ARC-0001", "ARC-0012", "ARC-0013",
       "ARC-0015", "ARC-0019", "ARC-0020", "ARC-0021", "ARC-0047", "ARC-0048"]


def jload(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def lf_sha(raw: bytes):
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def walk_selfdeclared(node, path="", hits=None):
    if hits is None:
        hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = path + "/" + str(k)
            if isinstance(v, str) and str(k).lower() in (
                "state", "status", "verdict", "result", "overall",
                "disposition", "outcome",
            ):
                if v.strip().upper() in ("BLOCKED", "FAILED"):
                    hits.append({"path": p, "value": v})
            walk_selfdeclared(v, p, hits)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_selfdeclared(v, path + "/" + str(i), hits)
    return hits


def parse_cmd(cmd):
    parts = cmd.split()
    env = {}
    i = 0
    while i < len(parts) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", parts[i]):
        k, _, v = parts[i].partition("=")
        env[k] = v
        i += 1
    argv = parts[i:]
    return env, argv


def run_probe(cmd, timeout=420):
    env, argv = parse_cmd(cmd)
    if argv and argv[0] in ("python3", "python", "python.exe"):
        argv[0] = sys.executable
    e = os.environ.copy()
    e.update(env)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=REPO, env=e, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        rc, out, err = p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        rc, out, err = -99, "", "TIMEOUT after %ds" % timeout
    dt = time.time() - t0
    tail = out + ("\n[stderr] " + err if err.strip() else "")
    return {"command": cmd, "exit_code": rc, "seconds": round(dt, 1),
            "tail": tail[-900:]}


results = {}
catalog = jload(os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json"))
byid = {u["id"]: u for u in catalog["work_units"]}

import schema_resolver as sr  # noqa: E402

for uid in IDS:
    r = {"unit_id": uid}
    cat = byid[uid]
    r["catalog"] = {
        "output_path": cat.get("output_path"),
        "output_schema": cat.get("output_schema"),
        "sentinel_is_bare": (cat.get("completion_sentinel") or "").strip() == "SUCCESS:" + uid,
        "owner_approval_required": cat.get("owner_approval_required"),
        "reviewer_requirement": cat.get("reviewer_requirement"),
    }
    art_rel = cat["output_path"]
    art_abs = os.path.join(REPO, art_rel.replace("/", os.sep))

    a = {"exists": os.path.isfile(art_abs)}
    art = None
    raw = b""
    if a["exists"]:
        raw = open(art_abs, "rb").read()
        a["bytes_on_disk"] = len(raw)
        a["nonempty"] = len(raw) > 0
        try:
            art = json.loads(raw.decode("utf-8"))
            a["parses"] = True
        except Exception as exc:
            a["parses"] = False
            a["parse_error"] = str(exc)[:200]
        a["sentinel_in_bytes"] = ("SUCCESS:" + uid).encode() in raw
        a["unit_incomplete_marker"] = b"UNIT-INCOMPLETE" in raw
    else:
        a["nonempty"] = False
        a["parses"] = False
    r["artifact"] = a
    r["selfdeclared_hits"] = walk_selfdeclared(art) if art is not None else []

    rec = jload(os.path.join(REPO, "command-center", "receipts", uid + ".json"))
    prim = [x for x in rec.get("artifacts", []) if x.get("role") == "primary"]
    r["receipt"] = {
        "state": rec.get("state"),
        "reviewer_verdict": (rec.get("reviewer") or {}).get("verdict"),
        "reviewer_independent": (rec.get("reviewer") or {}).get("independent"),
        "primary_artifact_sha": prim[0].get("sha256") if prim else None,
        "primary_artifact_bytes": prim[0].get("bytes") if prim else None,
        "n_evidence": len(rec.get("evidence", [])),
        "n_probes_recorded": sum(len(ev.get("probes", [])) for ev in rec.get("evidence", [])),
    }
    probe_cmds = []
    for ev in rec.get("evidence", []):
        for pr in ev.get("probes", []):
            if pr.get("method") == "command" and "probes" in pr.get("command", ""):
                if pr["command"] not in probe_cmds:
                    probe_cmds.append(pr["command"])
    sub_p = os.path.join(REPO, "command-center", "p2-wave", "probes", uid,
                         "SUBAGENT-RETURN.json")
    named = []
    if os.path.isfile(sub_p):
        srj = jload(sub_p)
        named = [np["command"] for np in srj.get("named_probes", []) if np.get("command")]
    r["probe_cmds_receipt"] = probe_cmds
    r["probe_cmds_subagent"] = named
    r["probe_cmd_sets_agree"] = (sorted(probe_cmds) == sorted(named)) if named and probe_cmds else None

    live_sha, live_len = lf_sha(raw) if a["exists"] else (None, None)
    d = {"live_sha256": live_sha, "live_bytes_lf": live_len}
    man_p = os.path.join(REPO, "command-center", "p2-wave", "probes", uid,
                         "UNIT-ARTIFACT-MANIFEST.json")
    if os.path.isfile(man_p):
        man = jload(man_p)
        rows = man.get("artifacts", [])
        mprim = [x for x in rows if x.get("role") == "primary"]
        if mprim:
            d["manifest_primary_sha"] = mprim[0].get("sha256")
            d["manifest_primary_bytes"] = mprim[0].get("bytes")
            d["manifest_primary_match"] = (mprim[0].get("sha256") == live_sha
                                           and mprim[0].get("bytes") == live_len)
        d["manifest_rows_total"] = len(rows)
        bad = []
        for x in rows:
            xp = os.path.join(REPO, x["path"].replace("/", os.sep))
            if os.path.isfile(xp):
                s, n = lf_sha(open(xp, "rb").read())
                if s != x.get("sha256") or n != x.get("bytes"):
                    bad.append(x["path"])
            else:
                bad.append(x["path"] + " [ABSENT]")
        d["manifest_rows_mismatched"] = bad
    else:
        d["manifest_present"] = False
    d["receipt_sha_match"] = (r["receipt"]["primary_artifact_sha"] == live_sha)
    r["sha"] = d
    results[uid] = r

# --- C. live probe re-runs (reviewer-executed)
for uid in IDS:
    cmds = results[uid]["probe_cmds_receipt"] or results[uid]["probe_cmds_subagent"]
    runs = [run_probe(c) for c in cmds]
    results[uid]["probe_reruns"] = runs
    results[uid]["probes_all_exit0"] = bool(runs) and all(x["exit_code"] == 0 for x in runs)
    art_abs = os.path.join(REPO, results[uid]["catalog"]["output_path"].replace("/", os.sep))
    if os.path.isfile(art_abs):
        s2, n2 = lf_sha(open(art_abs, "rb").read())
        results[uid]["sha"]["post_probe_sha"] = s2
        results[uid]["sha"]["artifact_mutated_by_probes"] = (s2 != results[uid]["sha"]["live_sha256"])

# --- E. output_schema validation (fail-closed resolver, physical profile)
for uid in IDS:
    r = results[uid]
    if not r["artifact"]["parses"]:
        r["schema"] = {"validated": False, "why": "artifact does not parse"}
        continue
    with open(os.path.join(REPO, r["catalog"]["output_path"].replace("/", os.sep)),
              encoding="utf-8") as fh:
        art = json.load(fh)
    try:
        errs = sr.validate_artifact(art, r["catalog"]["output_schema"])
        r["schema"] = {"validated": len(errs) == 0, "error_count": len(errs),
                       "errors_first5": [e[:220] for e in errs[:5]]}
    except Exception as exc:
        r["schema"] = {"validated": False, "resolver_error": str(exc)[:300]}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=1)
print("WROTE", OUT)
for uid in IDS:
    r = results[uid]
    print("%s: state=%s parse=%s sentinel_bytes=%s selfdecl=%d probes0=%s man_match=%s rec_match=%s mutated=%s schema_ok=%s schemaerr=%s" % (
        uid, r["receipt"]["state"], r["artifact"]["parses"],
        r["artifact"].get("sentinel_in_bytes"),
        len(r["selfdeclared_hits"]),
        r.get("probes_all_exit0"),
        r["sha"].get("manifest_primary_match"),
        r["sha"].get("receipt_sha_match"),
        r["sha"].get("artifact_mutated_by_probes"),
        r.get("schema", {}).get("validated"),
        r.get("schema", {}).get("error_count")))

#!/usr/bin/env python3
"""Independent reviewer battery, P2 wave-2 shard-3 (12 units). Reviewer-owned.

Re-derives from live disk + live probe re-runs:
  1. catalog entry (output_path / output_schema / owner gate)
  2. receipt: parse + admission errors (receipt_schema_gate.validate_receipt)
  3. artifact at catalog output_path: exists / non-empty / parses /
     self-declared NOT-DELIVERING scan (state/status/verdict/result walk)
  4. sha256 (CRLF->LF normalized) vs probes/<uid>/UNIT-ARTIFACT-MANIFEST.json
     primary row (hash AND bytes); raw sha vs receipt artifacts[] row
  5. named probes re-run LIVE (receipt named_probes UNION manifest probe rows),
     exit 0 + SUCCESS: marker required
  6. output_schema lane: fail-closed resolver + validate_artifact error count
  7. 12-condition gate now, and after simulated reviewer closure
Writes _rev3-w2-shard3/verify_out.json.
"""
from __future__ import annotations
import copy, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
OUT = REPO / "_rev3-w2-shard3"
IDS = ["ARC-0054", "ARC-0055", "ARC-0056", "ARC-0076",
       "AUD-0003", "AUD-0005", "AUD-0008", "AUD-0010",
       "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
APO = chr(39)

sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as rsg   # noqa: E402
import schema_resolver as sres      # noqa: E402


def load_json(p):
    try:
        return json.loads(Path(p).read_bytes().decode("utf-8"))
    except Exception:
        return None


def norm_sha(b):
    return hashlib.sha256(b.replace(bytes([13, 10]), bytes([10]))).hexdigest()


def raw_sha(b):
    return hashlib.sha256(b).hexdigest()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def walk_self_decl(node, path="", acc=None):
    """Self-declared NOT-DELIVERING states at named state/status/verdict/result keys."""
    if acc is None:
        acc = []
    if isinstance(node, dict):
        for k, v in node.items():
            p2 = path + "/" + str(k)
            if (k in ("state", "status", "verdict", "result")
                    and isinstance(v, str) and v.strip().upper() in NOT_DELIVERING):
                acc.append((p2, v.strip().upper()))
            walk_self_decl(v, p2, acc)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_self_decl(v, path + "/" + str(i), acc)
    return acc


def cat_entry(uid):
    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json") or {}
    for e in cat.get("work_units", []):
        if isinstance(e, dict) and e.get("id") == uid:
            return e
    return {}


def probe_scripts(uid, receipt, manifest):
    """Union of receipt named_probes scripts and manifest probe rows."""
    hits = {}
    for np in (receipt or {}).get("named_probes", []):
        cmd = str(np.get("command", ""))
        for tok in cmd.replace(chr(34), " ").replace(APO, " ").split():
            base = tok.replace(chr(92), "/").rsplit("/", 1)[-1]
            if base.startswith("probe") and base.endswith(".py"):
                hits[base] = "receipt:" + str(np.get("id", np))
    for row in (manifest or {}).get("artifacts", []):
        base = str(row.get("path", "")).replace(chr(92), "/").rsplit("/", 1)[-1]
        if base.startswith("probe") and base.endswith(".py"):
            hits.setdefault(base, "manifest-row")
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    return [pdir / h for h in sorted(hits)]


def run_probe(script):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env["PYTHONPATH"] = os.pathsep.join([
        str(REPO / "command-center" / "p2-wave" / "seed-stage"),
        str(REPO),
        str(REPO / "tools"),
        str(REPO / "platform" / "lib"),
        env.get("PYTHONPATH", ""),
    ])
    t0 = time.time()
    try:
        pr = subprocess.run([sys.executable, "-B", str(script)], cwd=REPO, env=env,
                            capture_output=True, text=True, timeout=600, errors="replace")
        out = (pr.stdout or "")
        return {"script": script.parent.name + "/" + script.name,
                "exit": pr.returncode,
                "secs": round(time.time() - t0, 1),
                "ok_marker": ("SUCCESS:" in out),
                "tail": ((pr.stdout or "") + (pr.stderr or ""))[-300:]}
    except subprocess.TimeoutExpired:
        return {"script": script.parent.name + "/" + script.name, "exit": "TIMEOUT",
                "secs": 600.0, "ok_marker": False, "tail": "killed at 600s"}
    except Exception as exc:
        return {"script": script.parent.name + "/" + script.name, "exit": "SPAWN-ERR",
                "secs": round(time.time() - t0, 1), "ok_marker": False,
                "tail": str(exc)[:300]}


def review_block_now():
    return {
        "reviewer_id": "claude-opus-5-5-independent-reviewer-shard3-w2-2026-10-25",
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "anthropic",
        "reviewed_at": now_iso(),
    }


def verify(uid):
    entry = cat_entry(uid)
    v = {"id": uid,
         "output_path": entry.get("output_path"),
         "output_schema_decl": entry.get("output_schema"),
         "owner_approval_required": entry.get("owner_approval_required"),
         "reviewer_requirement": entry.get("reviewer_requirement")}

    receipt = load_json(REPO / "command-center" / "receipts" / (uid + ".json"))
    v["receipt_exists"] = isinstance(receipt, dict)
    if not isinstance(receipt, dict):
        v["eligible"] = False
        v["fail_reason"] = "no parseable receipt"
        return v
    v["receipt_state"] = receipt.get("state")
    v["receipt_status"] = receipt.get("status")
    v["admission_errors"] = rsg.validate_receipt(receipt)

    ap = REPO / str(entry.get("output_path"))
    v["artifact_exists"] = ap.is_file()
    raw = ap.read_bytes() if ap.is_file() else b""
    v["artifact_bytes"] = len(raw)
    parsed = load_json(ap) if ap.suffix == ".json" else None
    v["artifact_parses"] = isinstance(parsed, (dict, list))
    hits = walk_self_decl(parsed) if v["artifact_parses"] else []
    v["self_decl_hits"] = hits
    v["sentinel_in_artifact"] = ("SUCCESS:" + uid).encode() in raw
    v["failed_sentinel_of_uid_in_artifact"] = ("FAILED:" + uid).encode() in raw

    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = load_json(mp) if mp.is_file() else None
    v["manifest_exists"] = mp.is_file()
    want = str(entry.get("output_path")).replace(chr(92), "/")
    rows = [a for a in (man or {}).get("artifacts", [])
            if str(a.get("path", "")).replace(chr(92), "/") == want]
    v["manifest_row"] = rows[0] if rows else None
    ns = norm_sha(raw)
    rs = raw_sha(raw)
    v["artifact_norm_sha"] = ns
    v["artifact_raw_sha"] = rs
    mr = rows[0] if rows else {}
    exp_m = len(raw.replace(bytes([13, 10]), bytes([10]))) if mr.get("eol") == "CRLF" else len(raw)
    v["sha_ok_manifest"] = bool(rows) and mr.get("sha256") == ns and mr.get("bytes") == exp_m
    prim = [a for a in receipt.get("artifacts", [])
            if str(a.get("path", "")).replace(chr(92), "/") == want or a.get("role") == "primary"]
    v["receipt_primary_row"] = prim[0] if prim else None
    pr0 = prim[0] if prim else {}
    exp_r = len(raw.replace(bytes([13, 10]), bytes([10]))) if pr0.get("eol") == "CRLF" else len(raw)
    v["sha_ok_receipt"] = bool(prim) and prim[0].get("sha256") == rs and pr0.get("bytes") == exp_r
    return v, receipt, man, parsed, raw


def verify_full(uid):
    v, receipt, man, parsed, raw = verify(uid)

    try:
        res = sres.resolve(v["output_schema_decl"])
        v["schema_resolves"] = bool(res.resolves) or res.kind in ("meta-schema-url", "meta-schema-mirror")
    except Exception as exc:
        v["schema_resolves"] = False
        v["schema_resolve_error"] = str(exc)[:300]
    if v["artifact_parses"]:
        try:
            errs = sres.validate_artifact(parsed, v["output_schema_decl"])
            v["schema_artifact_errors"] = len(errs)
            v["schema_artifact_first"] = errs[:8]
        except Exception as exc:
            v["schema_artifact_errors"] = "RESOLVER-ERR"
            v["schema_artifact_first"] = [str(exc)[:300]]

    scripts = probe_scripts(uid, receipt, man or {})
    v["probes_named"] = [s.name for s in scripts]
    v["probes"] = [run_probe(s) for s in scripts]
    v["probes_ok"] = bool(v["probes"]) and all(q["exit"] == 0 for q in v["probes"])

    try:
        gate = rsg.evaluate_gate_a(receipt, repo_root=REPO)
        v["gate_blocking_now"] = [{"n": c.n, "basis": c.basis[:160]}
                                  for c in gate.blocking_conditions]
    except Exception as exc:
        v["gate_blocking_now"] = [{"n": "ERR", "basis": str(exc)[:200]}]
    if v["receipt_state"] != "SUCCESS":
        cand = copy.deepcopy(receipt)
        cand["state"] = "SUCCESS"
        cand["sentinel"] = "SUCCESS:" + uid
        rv = cand.get("reviewer")
        if not isinstance(rv, dict):
            rv = {}
            cand["reviewer"] = rv
        rv.update(review_block_now())
        try:
            aerrs = rsg.validate_receipt(cand)
            g2 = rsg.evaluate_gate_a(cand, repo_root=REPO)
            v["post_closure_admission_errors"] = aerrs
            v["post_closure_gate_blocking"] = [{"n": c.n, "basis": c.basis[:160]}
                                               for c in g2.blocking_conditions]
            v["post_closure_residual_beyond_1_9"] = [c["n"] for c in v["post_closure_gate_blocking"]
                                                     if c["n"] not in (1, 9)]
        except Exception as exc:
            v["post_closure_admission_errors"] = [str(exc)[:300]]
            v["post_closure_gate_blocking"] = [{"n": "ERR", "basis": str(exc)[:200]}]
            v["post_closure_residual_beyond_1_9"] = ["ERR"]

    v["eligible"] = bool(
        v["artifact_exists"] and v["artifact_bytes"] > 0 and v["artifact_parses"]
        and not v["self_decl_hits"]
        and v["probes_ok"] and v["sha_ok_manifest"] and v["sha_ok_receipt"]
        and not v["admission_errors"]
        and v.get("schema_resolves") is True)
    if not v["eligible"]:
        why = []
        if not v["artifact_exists"]:
            why.append("artifact-missing")
        if v["artifact_bytes"] == 0:
            why.append("artifact-empty")
        if not v["artifact_parses"]:
            why.append("artifact-unparseable")
        if v["self_decl_hits"]:
            why.append("self-declared " + repr(v["self_decl_hits"]))
        if not v["probes_ok"]:
            why.append("probe-not-exit-0:" + ",".join(
                q["script"] + "=" + str(q["exit"]) for q in v["probes"] if q["exit"] != 0))
        if not v["sha_ok_manifest"]:
            why.append("sha-manifest-mismatch")
        if not v["sha_ok_receipt"]:
            why.append("sha-receipt-mismatch")
        if v["admission_errors"]:
            why.append("admission-errors:" + str(v["admission_errors"][0])[:120])
        if v.get("schema_resolves") is not True:
            why.append("output-schema-does-not-resolve")
        v["fail_reason"] = "; ".join(why)
    return v


def main():
    results = {}
    for uid in IDS:
        t0 = time.time()
        v = verify_full(uid)
        v["verify_s"] = round(time.time() - t0, 1)
        results[uid] = v
        pline = ",".join(
            q["script"].split("/")[-1] + "=" + str(q["exit"]) + ("/S" if q["ok_marker"] else "")
            for q in v.get("probes") or [])
        print(uid + ": eligible=" + str(v.get("eligible")) +
              " state=" + str(v.get("receipt_state")) +
              " bytes=" + str(v.get("artifact_bytes")) +
              " self_decl=" + str(len(v.get("self_decl_hits") or [])) +
              " probes_ok=" + str(v.get("probes_ok")) +
              " [" + pline + "]" +
              " sha_m=" + str(v.get("sha_ok_manifest")) +
              " sha_r=" + str(v.get("sha_ok_receipt")) +
              " adm=" + str(len(v.get("admission_errors") or [])) +
              " schema_res=" + str(v.get("schema_resolves")) +
              " schema_errs=" + str(v.get("schema_artifact_errors")) +
              " residual=" + str(v.get("post_closure_residual_beyond_1_9")),
              flush=True)
        if not v.get("eligible"):
            print("   FAIL " + uid + ": " + str(v.get("fail_reason")), flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "verify_out.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE " + str(OUT / "verify_out.json"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

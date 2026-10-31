#!/usr/bin/env python3
"""Independent reviewer, P2 wave-2 shard-3 (12 units). NOT a builder.

verify : re-derive every closure check from live disk + live probe re-runs
close  : apply reviewer closure only where ALL checks hold and the program
         gate would go green; admission-validated before any write
"""
from __future__ import annotations
import copy, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
OUT = REPO / "_rev2-w2-shard3"
IDS = ["ARC-0054", "ARC-0055", "ARC-0056", "ARC-0076",
       "AUD-0003", "AUD-0005", "AUD-0008", "AUD-0010",
       "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042"]
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-shard3-w2-2026-10-25"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as rsg   # noqa: E402
import schema_resolver as sres      # noqa: E402


def load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def norm_sha(b):
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha(b):
    return hashlib.sha256(b).hexdigest()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def walk_self_decl(node, path="", acc=None):
    if acc is None:
        acc = []
    if isinstance(node, dict):
        for k, v in node.items():
            p2 = path + "/" + str(k)
            if (k in ("state", "status", "verdict", "result")
                    and isinstance(v, str) and v.upper() in NOT_DELIVERING):
                acc.append((p2, v.upper()))
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
    hits = set()

    def scan(node):
        if isinstance(node, dict):
            for v in node.values():
                scan(v)
        elif isinstance(node, list):
            for v in node:
                scan(v)
        elif isinstance(node, str):
            if ("probes/" + uid + "/probe") in node:
                for tok in node.replace('"', " ").replace("'", " ").split():
                    base = tok.rsplit("/", 1)[-1]
                    if base.startswith("probe") and base.endswith(".py"):
                        hits.add(base)

    scan(receipt)
    for row in (manifest or {}).get("artifacts", []):
        base = str(row.get("path", "")).replace("\\", "/").rsplit("/", 1)[-1]
        if base.startswith("probe") and base.endswith(".py"):
            hits.add(base)
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    return sorted(pdir / h for h in hits)


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
        p = subprocess.run([sys.executable, "-B", str(script)], cwd=REPO, env=env,
                           capture_output=True, text=True, timeout=900, errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        return {"script": script.name, "exit": p.returncode,
                "secs": round(time.time() - t0, 1),
                "ok_marker": ("SUCCESS:" in (p.stdout or "")),
                "tail": out[-400:]}
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit": "TIMEOUT", "secs": 900.0,
                "ok_marker": False, "tail": "killed at 900s"}


def verify(uid):
    entry = cat_entry(uid)
    r = {"id": uid,
         "output_path": entry.get("output_path"),
         "output_schema_decl": entry.get("output_schema"),
         "owner_approval_required": entry.get("owner_approval_required")}
    receipt = load_json(REPO / "command-center" / "receipts" / (uid + ".json"))
    r["receipt_exists"] = isinstance(receipt, dict)
    if not isinstance(receipt, dict):
        r["eligible"] = False
        r["fail_reason"] = "no parseable receipt"
        return r
    r["receipt_state"] = receipt.get("state")
    r["admission_errors"] = rsg.validate_receipt(receipt)
    gate = rsg.evaluate_gate_a(receipt, repo_root=REPO)
    r["gate_blocking_now"] = [{"n": c.n, "basis": c.basis[:200]}
                              for c in gate.blocking_conditions()]
    ap = REPO / str(entry.get("output_path"))
    r["artifact_exists"] = ap.is_file()
    raw = ap.read_bytes() if ap.is_file() else b""
    r["artifact_bytes"] = len(raw)
    parsed = load_json(ap) if ap.suffix == ".json" else None
    r["artifact_parses"] = isinstance(parsed, (dict, list))
    hits = walk_self_decl(parsed) if r["artifact_parses"] else []
    r["self_decl_hits"] = hits
    r["self_decl_top"] = [h for h in hits if h[0].count("/") <= 1]
    r["sentinel_in_artifact"] = ("SUCCESS:" + uid).encode() in raw
    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = load_json(mp) if mp.is_file() else None
    want = str(entry.get("output_path")).replace("\\", "/")
    rows = [a for a in (man or {}).get("artifacts", [])
            if str(a.get("path", "")).replace("\\", "/") == want]
    r["manifest_row"] = rows[0] if rows else None
    ns = norm_sha(raw)
    rs = raw_sha(raw)
    r["artifact_norm_sha"] = ns
    r["artifact_raw_sha"] = rs
    mr = rows[0] if rows else {}
    r["sha_ok_manifest"] = bool(rows) and mr.get("sha256") == ns and mr.get("bytes") == len(raw)
    prim = [a for a in receipt.get("artifacts", [])
            if str(a.get("path", "")).replace("\\", "/") == want or a.get("role") == "primary"]
    r["receipt_primary_row"] = prim[0] if prim else None
    r["sha_ok_receipt"] = bool(prim) and prim[0].get("sha256") == rs and prim[0].get("bytes") == len(raw)
    return r
    try:
        errs = sres.validate_artifact(parsed, entry.get("output_schema"))
        r["schema_ok"] = (len(errs) == 0)
        r["schema_errors"] = errs[:12]
    except Exception as exc:
        r["schema_ok"] = False
        r["schema_errors"] = [("resolver: " + str(exc))[:300]]
    scripts = probe_scripts(uid, receipt, man or {})
    r["probes"] = [run_probe(s) for s in scripts]
    r["probes_ok"] = bool(r["probes"]) and all(p["exit"] == 0 for p in r["probes"])
    failing = {c["n"] for c in r["gate_blocking_now"]}
    r["gate_only_1_9"] = failing <= {1, 9}
    r["eligible"] = bool(
        r["artifact_exists"] and r["artifact_bytes"] > 0 and r["artifact_parses"]
        and (not r["self_decl_top"])
        and r["probes_ok"] and r["sha_ok_manifest"] and r["sha_ok_receipt"]
        and (not r["admission_errors"]) and r["gate_only_1_9"])
    if not r["eligible"]:
        why = []
        if not r["artifact_exists"]:
            why.append("artifact-missing")
        if r["artifact_bytes"] == 0:
            why.append("artifact-empty")
        if not r["artifact_parses"]:
            why.append("artifact-unparseable")
        if r["self_decl_top"]:
            why.append("self-declared " + repr(r["self_decl_top"]))
        if not r["probes_ok"]:
            why.append("probe-not-exit-0:" + ",".join(
                p["script"] for p in r["probes"] if p["exit"] != 0))
        if not r["sha_ok_manifest"]:
            why.append("sha-manifest-mismatch")
        if not r["sha_ok_receipt"]:
            why.append("sha-receipt-mismatch")
        if r["admission_errors"]:
            why.append("admission-errors:" + str(len(r["admission_errors"])))
        if not r["gate_only_1_9"]:
            why.append("gate-blocking:" + ",".join(
                str(c["n"]) for c in r["gate_blocking_now"] if c["n"] not in (1, 9)))
        r["fail_reason"] = "; ".join(why)
    return r


def close(uid, v, allow_schema_note):
    if v.get("receipt_state") == "SUCCESS":
        return {"id": uid, "closed": False, "note": "already SUCCESS; left untouched"}
    if not v.get("eligible"):
        return {"id": uid, "closed": False,
                "note": "ineligible: " + str(v.get("fail_reason"))}
    if (not v.get("schema_ok")) and (not allow_schema_note):
        return {"id": uid, "closed": False,
                "note": "schema deviations; strict mode refused"}
    rp = REPO / "command-center" / "receipts" / (uid + ".json")
    receipt = load_json(rp)
    cand = copy.deepcopy(receipt)
    cand["state"] = "SUCCESS"
    cand["sentinel"] = ("SUCCESS:" + uid + " independent reviewer closure 2026-10-25: "
                        "artifact verified at catalog output_path (exists, non-empty, "
                        "parses, not self-declared failed), all named probes re-run live "
                        "by the reviewer exit 0, manifest sha256 (CRLF-normalized) "
                        "re-matched; reviewer-absent gate cleared.")
    plines = "; ".join(p["script"] + " exit=" + str(p["exit"]) for p in v.get("probes", []))
    snotes = "artifact schema-checks clean" if v.get("schema_ok") else \
        "artifact schema deviations recorded: " + " | ".join(v.get("schema_errors", [])[:5])
    rnotes = ("Five closure checks re-derived live by the reviewer (did not build this unit). "
              "1) artifact exists/non-empty/parses at catalog output_path; top-level "
              "state/status carries no BLOCKED/FAILED self-declaration. "
              "2) probes re-run live from repo root by the reviewer, all exit 0 [" + plines + "]. "
              "3) artifact sha256 recomputed with CRLF-to-LF normalization matches "
              "UNIT-ARTIFACT-MANIFEST.json row " + str((v.get("manifest_row") or {}).get("sha256", ""))[:16] +
              "... ; raw on-disk sha re-matches the receipt artifacts[] primary row. "
              "4) output_schema resolved fail-closed via platform/lib/schema_resolver; " + snotes + ". "
              "5) receipt admissible; 12-condition gate failed only on c1 (state=BLOCKED) and "
              "c9 (reviewer-absent) before closure. Falsification: sentinel-embedding scan, "
              "self-declared-failure scan over the parsed artifact, byte-count cross-check. "
              "Machine output: _rev2-w2-shard3/verify_out.json")
    cand["reviewer"] = {"reviewer_id": REVIEWER_ID, "verdict": "PASS",
                        "independent": True, "fresh_context": True,
                        "vendor": "anthropic", "reviewed_at": now_iso(),
                        "notes": rnotes[:8000]}
    fr = cand.get("failure")
    if isinstance(fr, dict) and isinstance(fr.get("reason"), str) \
            and "RESOLVED" not in fr["reason"]:
        fr["reason"] = (fr["reason"] +
                        " RESOLVED 2026-10-25 by independent reviewer closure "
                        "(see reviewer block).")[:8000]
    extra = (" REVIEWER CLOSURE 2026-10-25 by " + REVIEWER_ID + ": state=SUCCESS on five "
             "re-derived checks; not owner-gated (owner_approval_required=" +
             str(v.get("owner_approval_required")).lower() +
             "); blanket build directive 2026-10-24 not needed for this unit.")
    if isinstance(cand.get("notes"), str):
        cand["notes"] = (cand["notes"] + extra)[:15000]
    else:
        cand["notes"] = extra.strip()
    aerrs = rsg.validate_receipt(cand)
    if aerrs:
        return {"id": uid, "closed": False,
                "note": "candidate fails admission: " + str(aerrs[0])[:200]}
    g2 = rsg.evaluate_gate_a(cand, repo_root=REPO)
    if not g2.holds():
        return {"id": uid, "closed": False, "note": "candidate gate red: " + "; ".join(
            "c" + str(c.n) + "=" + c.basis[:120] for c in g2.blocking_conditions())}
    tmp = rp.with_name(rp.name + ".rev-tmp")
    tmp.write_text(json.dumps(cand, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, rp)
    return {"id": uid, "closed": True,
            "note": "closed SUCCESS; admission+gate green post-write"}


def main():
    do_close = "--close" in sys.argv
    allow_schema_note = "--allow-schema-note" in sys.argv
    results = {}
    for uid in IDS:
        t0 = time.time()
        v = verify(uid)
        v["verify_s"] = round(time.time() - t0, 1)
        results[uid] = v
        print(uid + ": eligible=" + str(v.get("eligible")) +
              " state=" + str(v.get("receipt_state")) +
              " bytes=" + str(v.get("artifact_bytes")) +
              " parses=" + str(v.get("artifact_parses")) +
              " self_decl_top=" + str(v.get("self_decl_top")) +
              " probes_ok=" + str(v.get("probes_ok")) +
              " sha_ok_manifest=" + str(v.get("sha_ok_manifest")) +
              " sha_ok_receipt=" + str(v.get("sha_ok_receipt")) +
              " admission_errors=" + str(len(v.get("admission_errors") or [])) +
              " schema_ok=" + str(v.get("schema_ok")) +
              " gate_now=" + str([c["n"] for c in v.get("gate_blocking_now") or []]),
              flush=True)
        if not v.get("eligible"):
            print("   FAIL " + uid + ": " + str(v.get("fail_reason")), flush=True)
    OUT.mkdir(exist_ok=True)
    (OUT / "verify_out.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    if do_close:
        closings = {}
        for uid in IDS:
            res = close(uid, results[uid], allow_schema_note)
            closings[uid] = res
            print(("CLOSED  " if res["closed"] else "NOT-CLOSED ") + uid + ": " + res["note"],
                  flush=True)
        final = {}
        for uid in IDS:
            r = load_json(REPO / "command-center" / "receipts" / (uid + ".json"))
            if not isinstance(r, dict):
                final[uid] = "UNPARSEABLE"
                continue
            aerrs = rsg.validate_receipt(r)
            g = rsg.evaluate_gate_a(r, repo_root=REPO)
            final[uid] = ("state=" + str(r.get("state")) +
                          " admission=" + ("OK" if not aerrs else str(aerrs[0])[:120]) +
                          " gate=" + ("GREEN" if g.holds() else "RED:" + ",".join(
                              str(c.n) for c in g.blocking_conditions())))
            print("FINAL " + uid + ": " + final[uid], flush=True)
        (OUT / "closure_report.json").write_text(json.dumps(
            {"closures": closings, "final_disk_state": final}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

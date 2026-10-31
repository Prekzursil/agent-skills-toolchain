#!/usr/bin/env python3
"""Independent reviewer battery, P2 wave-2 shard-3 (12 BLD units). Reviewer-owned.

Round 4. Prior attempts: _rev3-w2-shard3 (ARC/AUD ids, earlier program state),
p2shard3/shard3-entries.json is the CURRENT shard manifest (12 BLD ids, Oct 24).

Checks per unit (all must hold for PASS):
  C1  live-catalog entry has output_path + output_schema + dependencies
  C2  artifact at output_path: exists / non-empty / parses
  C3  no self-declared NOT-DELIVERING state (state/status/verdict/result key walk
      + sentinel field must not start FAILED:/BLOCKED:)
  C4  receipt admission (receipt_schema_gate.validate_receipt) == 0 errors
  C5  probes/<uid>/UNIT-ARTIFACT-MANIFEST.json: exists, primary row matches live
      artifact sha256 (CRLF->LF normalized) AND bytes; expected==present
  C6  receipt self-recorded primary artifacts[] row consistent with live file
      (sha/bytes; norm sha when eol=CRLF, raw sha when eol=LF)
  C7  named probes re-run LIVE: exit 0 AND SUCCESS: marker; artifact sha unchanged
      after probe run (mutation detection)
  C8  output_schema resolves AND validates the artifact with 0 errors
  C9  receipt_core closure rule: state=SUCCESS requires reviewer.verdict=PASS +
      independent=true; and evaluate_gate_a blocking conditions == [] for a
      receipt already claiming SUCCESS

On PASS: refresh receipt reviewer block (this reviewer, dated) and confirm state
stays SUCCESS; refresh manifest primary row + receipt self-row only if the
closure edit changes bytes (fixed-point), else leave untouched.
On FAIL: receipt untouched, precise failing checks recorded.

Writes _rev4-w2-shard3/verify_out.json and verdicts.json.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
OUT = REPO / "_rev4-w2-shard3"
IDS = ["BLD-0001", "BLD-0002", "BLD-0006", "BLD-0010", "BLD-0023", "BLD-0024",
       "BLD-0031", "BLD-0037", "BLD-0041", "BLD-0044", "BLD-0045", "BLD-0051"]
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


def norm_sha(b: bytes) -> str:
    return hashlib.sha256(b.replace(bytes([13, 10]), bytes([10]))).hexdigest()


def raw_sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def walk_self_decl(node, path="", acc=None):
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
    env["PYTHONIOENCODING"] = "utf-8"
    # NO PYTHONPATH injection: REPO on sys.path shadows the stdlib 'platform'
    # module (REPO/platform/ dir), breaking attrs/jsonschema inside probes
    # (measured: BLD-0006 probe1, BLD-0010 probe2 exit 1 only under this env).
    env.pop("PYTHONPATH", None)
    t0 = time.time()
    try:
        pr = subprocess.run([sys.executable, "-B", str(script)], cwd=REPO, env=env,
                            capture_output=True, timeout=600)
        out = (pr.stdout or b"").decode("utf-8", errors="replace")
        err = (pr.stderr or b"").decode("utf-8", errors="replace")
        return {"script": script.parent.name + "/" + script.name,
                "exit": pr.returncode,
                "secs": round(time.time() - t0, 1),
                "ok_marker": ("SUCCESS:" in out),
                "tail": (out + err)[-280:]}
    except subprocess.TimeoutExpired:
        return {"script": script.parent.name + "/" + script.name, "exit": "TIMEOUT",
                "secs": 600.0, "ok_marker": False, "tail": "killed at 600s"}
    except Exception as exc:
        return {"script": script.parent.name + "/" + script.name, "exit": "SPAWN-ERR",
                "secs": round(time.time() - t0, 1), "ok_marker": False,
                "tail": str(exc)[:280]}


def review_block_now(notes: str) -> dict:
    return {
        "reviewer_id": "claude-opus-5-5-independent-reviewer-shard3-w2-round4-2026-10-26",
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "anthropic",
        "notes": notes,
        "reviewed_at": now_iso(),
    }


def verify_full(uid):
    entry = cat_entry(uid)
    v = {"id": uid,
         "catalog_entry_present": bool(entry),
         "output_path": entry.get("output_path"),
         "output_schema_decl": entry.get("output_schema"),
         "owner_approval_required": entry.get("owner_approval_required"),
         "dependencies": entry.get("dependencies"),
         "checks": {}}
    ck = v["checks"]

    # C1 catalog completeness
    ck["C1_catalog"] = bool(entry.get("output_path") and entry.get("output_schema")
                            and entry.get("dependencies") is not None)

    # C2/C3 artifact at output_path
    ap = REPO / str(entry.get("output_path") or "")
    v["artifact_exists"] = ap.is_file()
    raw = ap.read_bytes() if ap.is_file() else b""
    v["artifact_bytes"] = len(raw)
    parsed = load_json(ap) if ap.is_file() else None
    v["artifact_parses"] = isinstance(parsed, (dict, list))
    ck["C2_artifact"] = bool(v["artifact_exists"] and v["artifact_bytes"] > 0
                             and v["artifact_parses"])
    hits = walk_self_decl(parsed) if v["artifact_parses"] else []
    v["self_decl_hits"] = hits
    sentinel_field = (parsed or {}).get("sentinel") if isinstance(parsed, dict) else None
    v["sentinel_field"] = (sentinel_field or "")[:160]
    v["sentinel_failed_marker"] = bool(
        isinstance(sentinel_field, str)
        and sentinel_field.strip().upper().startswith(("FAILED:", "BLOCKED:")))
    v["success_sentinel_in_bytes"] = ("SUCCESS:" + uid).encode() in raw
    ck["C3_not_self_blocked"] = (not hits) and (not v["sentinel_failed_marker"])

    # C4 receipt admission
    admission = rsg.validate_receipt(parsed) if v["artifact_parses"] else ["not-parsed"]
    v["admission_errors"] = admission
    ck["C4_admission_zero"] = not admission

    # C5 manifest + primary row sha/bytes vs live (normalized)
    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = load_json(mp) if mp.is_file() else None
    v["manifest_exists"] = mp.is_file()
    want = str(entry.get("output_path")).replace(chr(92), "/")
    rows = [a for a in (man or {}).get("artifacts", [])
            if str(a.get("path", "")).replace(chr(92), "/") == want]
    v["manifest_row"] = rows[0] if rows else None
    ns, rs = norm_sha(raw), raw_sha(raw)
    v["artifact_norm_sha"] = ns
    v["artifact_raw_sha"] = rs
    mr = rows[0] if rows else {}
    exp_m = len(raw.replace(bytes([13, 10]), bytes([10]))) if mr.get("eol") == "CRLF" else len(raw)
    v["sha_ok_manifest"] = bool(rows) and mr.get("sha256") == ns and mr.get("bytes") == exp_m
    v["manifest_counts_ok"] = bool(man) and man.get("expected") == man.get("present")
    v["manifest_supporting_mismatch"] = [
        a["path"] for a in (man or {}).get("artifacts", [])
        if a.get("role") != "primary" and a.get("present")
        and (REPO / str(a.get("path"))).is_file()
        and norm_sha((REPO / str(a.get("path"))).read_bytes()) != a.get("sha256")]
    ck["C5_manifest"] = bool(v["manifest_exists"] and rows and v["sha_ok_manifest"]
                             and v["manifest_counts_ok"])

    # C6 receipt self-row vs live
    receipt = parsed if isinstance(parsed, dict) else {}
    prim = [a for a in receipt.get("artifacts", [])
            if str(a.get("path", "")).replace(chr(92), "/") == want or a.get("role") == "primary"]
    v["receipt_primary_row"] = prim[0] if prim else None
    pr0 = prim[0] if prim else {}
    if pr0.get("eol") == "CRLF":
        v["sha_ok_receipt"] = bool(prim) and pr0.get("sha256") == ns
        v["bytes_ok_receipt"] = bool(prim) and pr0.get("bytes") == len(
            raw.replace(bytes([13, 10]), bytes([10])))
    else:
        v["sha_ok_receipt"] = bool(prim) and pr0.get("sha256") == rs
        v["bytes_ok_receipt"] = bool(prim) and pr0.get("bytes") == len(raw)
    ck["C6_receipt_selfrow"] = bool(v["sha_ok_receipt"] and v["bytes_ok_receipt"])

    # C8 output_schema resolves + validates artifact, 0 errors
    try:
        res = sres.resolve(v["output_schema_decl"])
        v["schema_resolves"] = bool(res.resolves) or res.kind in (
            "meta-schema-url", "meta-schema-mirror")
    except Exception as exc:
        v["schema_resolves"] = False
        v["schema_resolve_error"] = str(exc)[:300]
    if v["artifact_parses"]:
        try:
            errs = sres.validate_artifact(parsed, v["output_schema_decl"])
            v["schema_artifact_errors_n"] = len(errs)
            v["schema_artifact_first"] = [e[:220] for e in errs[:6]]
        except Exception as exc:
            v["schema_artifact_errors_n"] = "RESOLVER-ERR"
            v["schema_artifact_first"] = [str(exc)[:300]]
    else:
        v["schema_artifact_errors_n"] = "UNPARSEABLE"
    ck["C8_schema"] = (v.get("schema_resolves") is True
                       and v.get("schema_artifact_errors_n") == 0)

    # C9 closure rule + live gate on the receipt AS IT STANDS
    rev = receipt.get("reviewer") if isinstance(receipt, dict) else None
    v["receipt_state"] = receipt.get("state")
    v["reviewer_verdict"] = (rev or {}).get("verdict") if isinstance(rev, dict) else None
    v["reviewer_independent"] = (rev or {}).get("independent") if isinstance(rev, dict) else None
    v["closure_rule_ok"] = (v["receipt_state"] != "SUCCESS"
                            or (v["reviewer_verdict"] == "PASS"
                                and v["reviewer_independent"] is True))
    try:
        gate = rsg.evaluate_gate_a(receipt, repo_root=REPO)
        v["gate_blocking_now"] = [{"n": c.n, "basis": c.basis[:220]}
                                  for c in gate.blocking_conditions]
    except Exception as exc:
        v["gate_blocking_now"] = [{"n": "ERR", "basis": str(exc)[:200]}]
    ck["C9_gate_clean"] = (v["closure_rule_ok"] and not v["gate_blocking_now"])

    # C7 live probe re-runs (LAST — probes may be slow; mutation check around them)
    pre_sha = raw_sha(ap.read_bytes()) if ap.is_file() else None
    scripts = probe_scripts(uid, receipt, man or {})
    v["probes_named"] = [s.name for s in scripts]
    v["probes"] = [run_probe(s) for s in scripts]
    v["probes_ok"] = bool(v["probes"]) and all(
        q["exit"] == 0 and q["ok_marker"] for q in v["probes"])
    post_raw = ap.read_bytes() if ap.is_file() else b""
    v["artifact_mutated_by_probes"] = (pre_sha is not None
                                       and raw_sha(post_raw) != pre_sha)
    ck["C7_probes_live"] = v["probes_ok"] and not v["artifact_mutated_by_probes"]

    v["all_checks"] = all(ck.values())

    if not v["all_checks"]:
        why = []
        for name in sorted(ck):
            if not ck[name]:
                why.append(name)
        v["fail_checks"] = why
        detail = []
        if not ck["C5_manifest"]:
            detail.append("manifest sha/bytes mismatch" if rows else
                          ("manifest missing" if not v["manifest_exists"] else "no primary row"))
        if not ck["C6_receipt_selfrow"]:
            detail.append("receipt self-row stale: declared %s/%s vs live %d bytes"
                          % (pr0.get("bytes"), str(pr0.get("sha256"))[:12], len(raw)))
        if not ck["C8_schema"]:
            detail.append("schema errors=%s first=%s" % (
                v.get("schema_artifact_errors_n"),
                (v.get("schema_artifact_first") or ["?"])[0][:150]))
        if not ck["C9_gate_clean"]:
            detail.append("gate blocking=%s" % [(b["n"], b["basis"][:90])
                                                for b in v["gate_blocking_now"][:4]])
        if not ck["C7_probes_live"]:
            detail.append("probes=%s" % [(q["script"], q["exit"],
                                          bool(q["ok_marker"])) for q in v["probes"]])
        if hits:
            detail.append("self_decl=%s" % hits[:3])
        if v["sentinel_failed_marker"]:
            detail.append("sentinel=FAILED/BLOCKED marker: %s" % v["sentinel_field"][:110])
        if v["artifact_mutated_by_probes"]:
            detail.append("PROBE MUTATED ARTIFACT")
        v["fail_reason"] = "; ".join(detail)
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
        print("%s: all=%s state=%s bytes=%d self_decl=%d sentinel_fail=%s probes_ok=%s [%s] "
              "sha_m=%s sha_r=%s adm=%d schema=%s/%s gate_block=%d" % (
                  uid, v.get("all_checks"), v.get("receipt_state"), v.get("artifact_bytes"),
                  len(v.get("self_decl_hits") or []), v.get("sentinel_failed_marker"),
                  v.get("probes_ok"), pline,
                  v.get("sha_ok_manifest"), v.get("sha_ok_receipt"),
                  len(v.get("admission_errors") or []),
                  v.get("schema_resolves"), v.get("schema_artifact_errors_n"),
                  len(v.get("gate_blocking_now") or [])), flush=True)
        if not v.get("all_checks"):
            print("   FAIL " + uid + ": " + str(v.get("fail_reason")), flush=True)

    OUT.mkdir(exist_ok=True)
    (OUT / "verify_out.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    passed = [u for u in IDS if results[u].get("all_checks")]
    failed = [u for u in IDS if not results[u].get("all_checks")]
    (OUT / "verdicts.json").write_text(json.dumps({
        "generated_at": now_iso(),
        "reviewer": "claude-opus-5-5-independent-reviewer-shard3-w2-round4",
        "units_total": len(IDS),
        "pass": passed,
        "fail": failed,
        "fail_detail": {u: results[u].get("fail_reason") for u in failed},
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print("SUMMARY pass=%d fail=%d -> %s / verdicts.json" % (
        len(passed), len(failed), OUT / "verify_out.json"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

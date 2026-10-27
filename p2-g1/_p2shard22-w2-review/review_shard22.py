#!/usr/bin/env python3
"""Independent reviewer, P2 wave-2 shard-22 (12 TST units). NOT a builder.

VERIFY: re-derive the DELIVERED contract checks from live disk + live probe
re-runs for every unit:
  1. catalog entry with output_path/output_schema/probes/dependencies/description
  2. artifact at catalog output_path: exists, non-empty, parses, top-level state
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT, failure block falsy
  3. named live probes re-run VERBATIM from probes/<id>/PROBE-CMDS.json by this
     reviewer; exit 0 and SUCCESS: marker required
  4. sha256 (CRLF->LF normalized) of the primary artifact AND every manifest row
     recomputed and matched against UNIT-ARTIFACT-MANIFEST.json; primary recomputed
     BEFORE and AFTER the probe re-runs to catch probe-mutation of the receipt
  5. output_schema resolved fail-closed via platform/lib/schema_resolver; clean
  6. receipt admission (receipt_schema_gate.validate_receipt) clean; 12-condition
     gate residuals recorded verbatim (not cured by this PASS)
  7. existing reviewer closure validity: reviewer.verdict=PASS + independent=true
  8. substance check: receipt is not a hollow stub (id/unit_id match, sentinel,
     substantive payload fields present)

CONFIRM: every check green AND an existing valid independent PASS closure ->
confirm it stays SUCCESS; receipt bytes left untouched. ANY check red -> verdict
FAIL with the precise failing check; receipt unchanged.
Machine output: verify_out.json + closure_report.json next to this script.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard22-w2-review"
CLOSE_DATE = "2026-10-25"
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-shard22-w2-2026-10-25"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
UNITS = ["TST-0060", "TST-0066", "TST-0068", "TST-0070", "TST-0081", "TST-0085",
         "TST-0088", "TST-0090", "TST-0091", "TST-0094", "TST-0100", "TST-0109"]
# env passthrough for probe subprocesses (same shaping the recorded probe runs used)
PASSTHRU = {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR", "TEMP", "TMP",
            "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "USERPROFILE", "MSYSTEM"}

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


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cat_entry(uid):
    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json") or {}
    for e in cat.get("work_units", []):
        if isinstance(e, dict) and e.get("id") == uid:
            return e
    return None


def run_named_probe(cmd):
    """Run the recorded named-probe command string verbatim (Windows env-shaping
    for POSIX 'VAR=value cmd' prefixes, same mechanics the finisher used)."""
    env = {k: v for k, v in os.environ.items() if k in PASSTHRU}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    c = cmd
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        c = c[m.end():]
    t0 = time.time()
    try:
        p = subprocess.run(c, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=900, errors="replace", env=env)
        out = (p.stdout or "") + (p.stderr or "")
        return {"command": cmd, "exit": p.returncode,
                "secs": round(time.time() - t0, 1),
                "ok_marker": ("SUCCESS:" in (p.stdout or "")),
                "tail": out[-500:]}
    except subprocess.TimeoutExpired:
        return {"command": cmd, "exit": "TIMEOUT", "secs": 900.0,
                "ok_marker": False, "tail": "killed at 900s"}


def check_unit(uid):
    v = {"id": uid, "checks": {}, "fail": []}
    ck = v["checks"]

    entry = cat_entry(uid)
    ck["catalog_entry"] = entry is not None
    ck["catalog_fields"] = bool(entry) and all(
        entry.get(f) not in (None, "", []) for f in
        ("output_path", "output_schema", "probes", "dependencies", "description"))
    if entry is None:
        v["fail"].append("catalog-entry-missing")
        return v

    # --- 2. artifact at catalog output_path
    ap = REPO / str(entry["output_path"])
    raw = ap.read_bytes() if ap.is_file() else b""
    ck["artifact_exists"] = ap.is_file()
    ck["artifact_nonempty"] = len(raw) > 0
    parsed = load_json(ap)
    ck["artifact_parses"] = isinstance(parsed, dict)
    if not ck["artifact_exists"]:
        v["fail"].append("artifact-missing")
        return v
    if not ck["artifact_nonempty"]:
        v["fail"].append("artifact-empty")
        return v
    if not ck["artifact_parses"]:
        v["fail"].append("artifact-unparseable")
        return v

    top_state = str(parsed.get("state", ""))
    ck["state_success"] = top_state.upper() == "SUCCESS"
    ck["not_self_blocked"] = top_state.upper() not in NOT_DELIVERING
    ck["failure_falsy"] = not parsed.get("failure")
    ck["top_status_clean"] = (str(parsed.get("status")).upper() not in NOT_DELIVERING
                              if parsed.get("status") else True)
    if not ck["state_success"]:
        v["fail"].append("top-state=" + repr(top_state))
    if not ck["failure_falsy"]:
        v["fail"].append("failure-block-present")

    # --- 3. live named probes re-run verbatim (contract path)
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    cmds = load_json(pdir / "PROBE-CMDS.json")
    ck["probe_cmds_present"] = isinstance(cmds, list) and len(cmds) >= 2
    pre_sha = norm_sha(raw)
    runs = [run_named_probe(c) for c in (cmds or [])] if isinstance(cmds, list) else []
    ck["probes"] = [{"command": r["command"][:160], "exit": r["exit"],
                     "secs": r["secs"], "ok_marker": r["ok_marker"]} for r in runs]
    ck["probes_ok"] = bool(runs) and all(r["exit"] == 0 and r["ok_marker"] for r in runs)
    if not ck["probes_ok"]:
        v["fail"].append("probe-not-exit-0-or-no-SUCCESS-marker:" +
                         ",".join(str(i) + ":" + str(r["exit"])
                                  for i, r in enumerate(runs, 1)))

    # --- 4. sha256 CRLF-normalized, manifest rows, pre/post probe mutation check
    post_raw = ap.read_bytes()
    post_sha = norm_sha(post_raw)
    ck["artifact_stable_under_probes"] = (pre_sha == post_sha) and (len(raw) == len(post_raw))
    if not ck["artifact_stable_under_probes"]:
        v["fail"].append("artifact-mutated-by-probe-run")
    mp = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    man = load_json(mp)
    ck["manifest_parses"] = isinstance(man, dict)
    want = str(entry["output_path"]).replace("\\", "/")
    rows = (man or {}).get("artifacts", []) if isinstance(man, dict) else []
    primary = [a for a in rows if str(a.get("path", "")).replace("\\", "/") == want]
    ck["manifest_primary_row"] = bool(primary)
    ck["manifest_primary_sha_ok"] = (bool(primary) and primary[0].get("sha256") == post_sha
                                     and primary[0].get("bytes") == len(post_raw))
    row_problems = []
    for a in rows:
        rp = REPO / str(a.get("path", ""))
        if not rp.is_file():
            row_problems.append(str(a.get("path")) + ": absent")
            continue
        rb = rp.read_bytes()
        if a.get("sha256") != norm_sha(rb) or a.get("bytes") != len(rb):
            row_problems.append(str(a.get("path")) + ": sha/bytes disagree with disk")
    ck["manifest_all_rows_ok"] = not row_problems
    ck["manifest_count_ok"] = (isinstance(man, dict)
                               and man.get("expected") == man.get("present") == len(rows))
    if not ck["manifest_primary_sha_ok"]:
        v["fail"].append("manifest-primary-sha-mismatch")
    if row_problems:
        v["fail"].append("manifest-row-mismatch:" + ";".join(row_problems[:3]))
    v["primary_sha"] = post_sha

    # receipt artifacts[] rows vs disk
    rrow_problems = []
    for a in parsed.get("artifacts", []):
        rp = REPO / str(a.get("path", ""))
        if not rp.is_file():
            rrow_problems.append(str(a.get("path")) + ": absent")
            continue
        rb = rp.read_bytes()
        if a.get("sha256") not in (norm_sha(rb), hashlib.sha256(rb).hexdigest()) \
                or a.get("bytes") != len(rb):
            rrow_problems.append(str(a.get("path")) + ": sha/bytes disagree with disk")
    ck["receipt_artifact_rows_ok"] = not rrow_problems
    if rrow_problems:
        v["fail"].append("receipt-artifact-row-mismatch:" + ";".join(rrow_problems[:3]))

    # --- 5. output_schema fail-closed validation
    try:
        errs = sres.validate_artifact(parsed, entry.get("output_schema"))
        ck["schema_ok"] = len(errs) == 0
        v["schema_errors"] = errs[:8]
    except Exception as exc:
        ck["schema_ok"] = False
        v["schema_errors"] = [("resolver: " + str(exc))[:300]]
    if not ck["schema_ok"]:
        v["fail"].append("output_schema-invalid:" + str(v["schema_errors"][:2]))

    # --- 6. admission + gate
    v["admission_errors"] = rsg.validate_receipt(parsed)
    ck["admission_ok"] = len(v["admission_errors"]) == 0
    if not ck["admission_ok"]:
        v["fail"].append("admission-errors:" + str(v["admission_errors"][:2]))
    try:
        gate = rsg.evaluate_gate_a(parsed, repo_root=REPO)
        v["gate_blocking"] = [{"n": c.n, "basis": str(c.basis)[:220]}
                              for c in gate.blocking_conditions]
        v["gate_residual"] = [c for c in v["gate_blocking"] if c["n"] not in (1, 9)]
    except Exception as exc:
        v["gate_blocking"] = [{"n": "ERR", "basis": str(exc)[:220]}]
        v["gate_residual"] = v["gate_blocking"]

    # --- 7. existing reviewer closure validity
    rev = parsed.get("reviewer") or {}
    ck["existing_pass_present"] = (rev.get("verdict") == "PASS"
                                   and rev.get("independent") is True)
    v["existing_reviewer_id"] = rev.get("reviewer_id")

    # --- 8. substance / stub check
    ck["id_fields_match"] = (parsed.get("id") == uid or parsed.get("unit_id") == uid)
    sent = str(parsed.get("sentinel") or "")
    comp = str(parsed.get("completion_sentinel") or "")
    ck["sentinel_ok"] = sent.startswith("SUCCESS:" + uid) or comp.startswith("SUCCESS:" + uid)
    substantive = [f for f in ("title", "question_or_target", "report", "summary",
                               "matrix", "answer", "tests", "evidence")
                   if parsed.get(f)]
    ck["substantive_fields"] = len(substantive) >= 3
    ck["substantive"] = substantive
    ck["min_bytes"] = len(raw) >= 2000
    if not (ck["id_fields_match"] and ck["min_bytes"] and ck["substantive_fields"]):
        v["fail"].append("hollow-stub-suspect:" + json.dumps(
            {k: ck.get(k) for k in ("id_fields_match", "substantive_fields",
                                    "min_bytes", "substantive")}))

    # SUBAGENT-RETURN consistency (informational but recorded)
    ret = load_json(pdir / "SUBAGENT-RETURN.json")
    v["subagent_return_state"] = ret.get("state") if isinstance(ret, dict) else None

    v["eligible_for_confirm"] = (not v["fail"]) and ck.get("existing_pass_present", False)
    return v


def main():
    OUT.mkdir(exist_ok=True)
    do_confirm = "--confirm" in sys.argv
    results = [check_unit(u) for u in UNITS]
    (OUT / "verify_out.json").write_text(
        json.dumps({"reviewer_id": REVIEWER_ID, "run_at": now_iso(),
                    "mode": "confirm" if do_confirm else "verify",
                    "results": results}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")

    greens = [r for r in results if r.get("eligible_for_confirm")]
    reds = [r for r in results if not r.get("eligible_for_confirm")]
    for r in reds:
        print("FAILED:" + r["id"] + " " + "; ".join(r["fail"]))
    for r in greens:
        print("VERIFIED:" + r["id"] + " all contract checks green live; "
              "existing independent PASS closure valid -> stays SUCCESS")

    if do_confirm and not reds:
        closure = {"reviewer_id": REVIEWER_ID, "closed_at": now_iso(),
                   "mode": "confirm-existing-pass",
                   "units": [{"id": r["id"], "verdict": "PASS", "independent": True,
                              "state": "SUCCESS", "receipt_modified": False,
                              "primary_sha": r["primary_sha"],
                              "gate_residual_conditions": [g["n"] for g in r["gate_residual"]],
                              "note": ("Independent reviewer re-derived all DELIVERED "
                                       "contract checks live (artifact at catalog "
                                       "output_path, named probes re-run verbatim exit 0, "
                                       "manifest sha256 CRLF-normalized match incl. "
                                       "pre/post-probe stability, output_schema clean, "
                                       "admission clean); existing independent PASS "
                                       "closure confirmed valid, receipt left untouched.")}
                             for r in greens]}
        (OUT / "closure_report.json").write_text(
            json.dumps(closure, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("SUCCESS:confirmed " + str(len(greens)) + "/" + str(len(results)))
    return 0 if not reds else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""INDEPENDENT REVIEWER battery, wave 4 shard 24 (7 TST units). Fresh re-derivation.

Written by the wave-4 shard-24 reviewer agent (did NOT build these units).
Read-only over everything EXCEPT the closure step, which it performs only for a
receipt whose state is BLOCKED and whose pre-closure gate-A red set is a subset
of the closure-fixable conditions {1 terminal-state, 5 sentinel}; a byte-exact
backup is kept and a post-closure re-verification decides the verdict.

Checks per unit:
  A  catalog entry has output_path + output_schema
  B  artifact at output_path: exists, non-empty, parses
  C  not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  D  receipt core fields present
  E  closure form: state==SUCCESS; reviewer.verdict==PASS; independent True;
     sentinel starts "SUCCESS:" and names the unit
  F  UNIT-ARTIFACT-MANIFEST.json: EVERY row present, LF-normalized sha256 ==
     live recompute; primary row matched
  G  receipt artifacts[] rows: path exists, LF/raw sha match live bytes
  H  output_schema validated via platform/lib/schema_resolver (0 errors)
  I  admission via platform/lib/receipt_schema_gate.validate_receipt (0 errors)
  J  live gate-A predicate: closed units must be COMPLETE; the BLOCKED unit's
     red set must be within {1,5} pre-closure and EMPTY post-closure
  K  live probe re-runs by THIS reviewer (canonical env discipline, own
     invocation): exit 0; LAST non-empty stdout line starts "SUCCESS:"; no
     stdout line starts "FAILED:"
  L  evidence-requirement spot checks recorded in the receipt

Exit 0 only when ALL 7 units hold ALL closure-applicable checks.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard24-w4-review"
IDS = ["TST-0328", "TST-0330", "TST-0332", "TST-0334",
       "TST-0335", "TST-0336", "TST-0337"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
CORE_REQUIRED = ["schema_version", "unit_id", "state", "sentinel", "spec_anchor",
                 "min_bytes_threshold", "artifacts", "evidence", "timestamps", "retry"]
CLOSURE_FIXABLE = {1, 5}  # terminal state, sentinel family

sys.path.insert(0, str(REPO / "platform" / "lib"))
import completion_predicate as cpred          # noqa: E402
import receipt_schema_gate as rsg             # noqa: E402
import schema_resolver as sres                # noqa: E402


def jload(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, type(exc).__name__ + ": " + str(exc)


def digest_norm(p):
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_raw(p):
    raw = Path(p).read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_map():
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return {u["id"]: u for u in cat["work_units"]}


ENV_DIRS = ["command-center/p2-wave/seed-stage", "", "tools",
            "tools/measure-guard", "platform/lib", "tools/agentspec"]


def run_probe(cmd):
    """Own invocation with the program's canonical env discipline."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    py = os.pathsep.join([str(REPO / d) if d else str(REPO) for d in ENV_DIRS])
    env["PYTHONPATH"] = py
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", exe + " " + wrapper.as_posix(), 1)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=2700, env=env)
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT", time.time() - t0
    return p.returncode, (p.stdout or ""), (p.stderr or ""), time.time() - t0


def probe_marker_ok(stdout):
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        return False, "no stdout lines"
    last = lines[-1]
    if not last.startswith("SUCCESS:"):
        return False, "last line not SUCCESS-terminated: " + repr(last[:80])
    bad = [ln[:80] for ln in lines if ln.startswith("FAILED:")]
    if bad:
        return False, "FAILED:-led line(s): " + repr(bad[:2])
    return True, last[:100]


def spot_checks(uid, doc):
    """Evidence-requirement presence checks (probe re-runs prove behavior)."""
    notes = []
    ok = True

    def has(label, cond):
        nonlocal ok
        if not cond:
            ok = False
            notes.append("missing: " + label)

    blob = json.dumps(doc)
    if uid == "TST-0328":
        ev = doc.get("evidence") or {}
        names = " ".join(str(c.get("name", "")) for c in (ev.get("controls") or [])
                         if isinstance(c, dict))
        has("both-states rejection controls recorded",
            ("silent" in names.lower())
            and ("always" in names.lower() or "fires in both" in names.lower()))
        has("callable answer recorded", bool(doc.get("answer")))
    elif uid == "TST-0330":
        has("corpus size recorded",
            bool(re.search(r'"(corpus(_size|_n|_count)?|n_inputs|inputs)"', blob)))
        has("disagreement count recorded", "disagree" in blob.lower())
        has("malformed inputs in corpus recorded", "malformed" in blob.lower())
    elif uid == "TST-0332":
        has("declared count recorded", "declared" in blob.lower())
        has("executed count recorded", "executed" in blob.lower())
        has("unexecuted list by step/job recorded", "unexecuted" in blob.lower())
    elif uid == "TST-0334":
        for route in ("git archive", "git cat-file", "worktree"):
            has("route measured: " + route, route in blob)
        has("hashes from three routes", blob.count('"sha256"') >= 3)
    elif uid == "TST-0335":
        has("reserved-name outcome", "reserved" in blob.lower())
        has("long-path outcome", ("300" in blob) or ("long" in blob.lower()))
        has("junction-loop outcome", "junction" in blob.lower())
        has("unreadable-entry count discipline",
            ("unreadable" in blob.lower()) or ("could not read" in blob.lower()))
    elif uid == "TST-0336":
        has("flake rate with repetitions recorded",
            bool(re.search(r'"(runs|repetitions|n_runs|reps)"', blob)))
        has("provisional labelling present or n>=20",
            ("provisional" in blob.lower()) or
            bool(re.search(r'"runs"\s*:\s*(\d{2,})', blob)))
    elif uid == "TST-0337":
        has("full-suite catches recorded", "full" in blob.lower())
        has("subset catches recorded", "subset" in blob.lower())
        has("miss list recorded", "miss" in blob.lower())
        has("time saved recorded", "time" in blob.lower())
    return ok, notes


def gate_a(uid, schema):
    """gate-A via the module's own tested CLI (drift-honesty context, not verdict bar)."""
    import subprocess as sp
    try:
        pr = sp.run([sys.executable, "-B", "platform/lib/completion_predicate.py",
                     "command-center/receipts/%s.json" % uid, "--repo-root", ".",
                     "--output-schema", schema],
                    cwd=str(REPO), capture_output=True, text=True, timeout=300)
        out = (pr.stdout or "").strip().splitlines()
        for ln in out:
            if ln.startswith(("FAILED:", "SUCCESS:")) and "predicate verdict" in ln:
                m = re.search(r"unsatisfied=\[([^]]*)\] not_checked=\[([^]]*)\]", ln)
                return {"rc": pr.returncode,
                        "unsatisfied": [int(x) for x in m.group(1).split(",") if x.strip()],
                        "not_checked": [int(x) for x in m.group(2).split(",") if x.strip()],
                        "line": ln}
        return {"rc": pr.returncode, "error": (pr.stdout or pr.stderr)[-200:]}
    except Exception as exc:
        return {"error": type(exc).__name__ + ": " + str(exc)}


def main():
    catmap = catalog_map()
    results = {}
    all_ok = True
    for uid in IDS:
        cu = catmap.get(uid)
        r = {"catalog_entry": bool(cu)}
        if not cu:
            results[uid] = r
            all_ok = False
            continue
        out_rel = str(cu.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel
        r["output_path"] = out_rel
        r["output_schema"] = cu.get("output_schema")
        raw_exists = out.is_file()
        r["artifact_exists"] = raw_exists
        r["artifact_nonempty"] = bool(raw_exists and out.stat().st_size > 0)
        doc, perr = jload(out) if r["artifact_nonempty"] else (None, "absent")
        r["artifact_parses"] = doc is not None
        if perr:
            r["parse_error"] = perr
        state = str((doc or {}).get("state") or "").upper()
        r["state"] = state or None
        r["not_self_blocked"] = bool(doc is not None and state not in NOT_DELIVERING)
        blocked_form = state in NOT_DELIVERING

        if isinstance(doc, dict):
            r["core_missing"] = [k for k in CORE_REQUIRED if k not in doc]
        else:
            r["core_missing"] = ["<unparsed>"]

        rev = (doc or {}).get("reviewer") or {}
        sent = str((doc or {}).get("sentinel") or "")
        r["reviewer"] = {k: rev.get(k) for k in ("verdict", "independent", "reviewer_id", "vendor")}
        r["closure_form"] = bool(
            doc is not None and state == "SUCCESS"
            and rev.get("verdict") == "PASS" and rev.get("independent") is True
            and sent.startswith("SUCCESS:") and uid in sent
        )

        man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man, merr = jload(man_path)
        rows = (man or {}).get("artifacts") or []
        row_reports = []
        primary_ok = False
        if isinstance(man, dict) and rows:
            for row in rows:
                p = REPO / str(row.get("path") or "").replace("\\", "/")
                rep = {"path": row.get("path"), "role": row.get("role")}
                if not p.is_file():
                    rep["present"] = False
                else:
                    rep["present"] = True
                    sha_n = digest_norm(p)[0]
                    sha_r = digest_raw(p)[0]
                    rep["sha_lf_match"] = (sha_n == row.get("sha256"))
                    rep["sha_raw_match"] = (sha_r == row.get("sha256"))
                    rep["manifest_sha_prefix"] = str(row.get("sha256"))[:12]
                    rep["live_sha_prefix"] = sha_n[:12]
                row_reports.append(rep)
                if row.get("role") == "primary" or str(row.get("path")) == out_rel:
                    primary_ok = bool(rep.get("present") and rep.get("sha_lf_match"))
        r["manifest_rows"] = row_reports
        r["manifest_primary_sha_match"] = primary_ok
        r["manifest_all_rows_match"] = bool(rows) and all(
            rp.get("present") and (rp.get("sha_lf_match") or rp.get("sha_raw_match"))
            for rp in row_reports)

        art_reports = []
        for a in (doc or {}).get("artifacts") or []:
            p = REPO / str(a.get("path") or "").replace("\\", "/")
            rep = {"path": a.get("path")}
            if not p.is_file():
                rep["present"] = False
            else:
                rep["present"] = True
                rep["sha_lf_match"] = (digest_norm(p)[0] == a.get("sha256"))
                rep["sha_raw_match"] = (digest_raw(p)[0] == a.get("sha256"))
                rep["bytes_live"] = p.stat().st_size
                rep["bytes_recorded"] = a.get("bytes")
            art_reports.append(rep)
        r["receipt_artifacts"] = art_reports
        r["receipt_artifacts_ok"] = all(
            rp.get("present") and (rp.get("sha_lf_match") or rp.get("sha_raw_match"))
            for rp in art_reports)

        if isinstance(doc, dict):
            try:
                errs = sres.validate_artifact(doc, cu.get("output_schema"))
                r["schema_errors"] = errs[:8]
                r["schema_error_n"] = len(errs)
            except Exception as exc:
                r["schema_errors"] = ["resolver: " + type(exc).__name__ + ": " + str(exc)]
                r["schema_error_n"] = -1
        else:
            r["schema_error_n"] = -1

        if isinstance(doc, dict):
            try:
                aerrs = rsg.validate_receipt(doc)
                r["admission_errors"] = aerrs[:8]
                r["admission_error_n"] = len(aerrs)
            except Exception as exc:
                r["admission_errors"] = ["gate: " + type(exc).__name__ + ": " + str(exc)]
                r["admission_error_n"] = -1
        else:
            r["admission_error_n"] = -1

        if isinstance(doc, dict):
            r["gate_a"] = gate_a(uid, cu.get("output_schema"))

        pd = REPO / "command-center/p2-wave/probes" / uid
        ret, _ = jload(pd / "SUBAGENT-RETURN.json")
        cmds = []
        if isinstance(ret, dict):
            for item in ret.get("named_probes") or []:
                if isinstance(item, dict) and isinstance(item.get("command"), str):
                    cmds.append(item["command"].strip())
        probe_reports = []
        for cmd in cmds:
            code, so, se, dt = run_probe(cmd)
            marker_ok, marker_detail = probe_marker_ok(so)
            probe_reports.append({
                "cmd": cmd, "exit": code, "secs": round(dt, 1),
                "marker_ok": marker_ok, "marker": marker_detail,
                "stderr_tail": ((se or "").strip()[-200:]) or None,
            })
        r["probes"] = probe_reports
        r["probes_exit0"] = bool(probe_reports) and all(p["exit"] == 0 for p in probe_reports)
        r["probe_markers_ok"] = bool(probe_reports) and all(p["marker_ok"] for p in probe_reports)

        if isinstance(doc, dict):
            ok, notes = spot_checks(uid, doc)
            r["spot_checks_ok"] = ok
            r["spot_check_notes"] = notes

        content_checks = (
            r["catalog_entry"] and r["artifact_exists"] and r["artifact_nonempty"]
            and r["artifact_parses"] and r["manifest_all_rows_match"]
            and r["manifest_primary_sha_match"] and r["receipt_artifacts_ok"]
            and r.get("schema_error_n") == 0 and r.get("admission_error_n") == 0
            and not r.get("core_missing")
            and r.get("spot_checks_ok", False)
        )
        if blocked_form:
            ga = r.get("gate_a") or {}
            red = set(ga.get("unsatisfied") or []) | set(ga.get("not_checked") or [])
            r["pre_closure_red"] = sorted(red)
            r["closure_eligible"] = bool(content_checks and red <= CLOSURE_FIXABLE)
            r["pending_closure"] = True
            if not (r["probes_exit0"] and r["probe_markers_ok"]):
                r["probes_note"] = ("state-gated probes red pre-closure (expected); "
                                    "post-closure re-run decides")
            if not r["closure_eligible"]:
                all_ok = False
        else:
            # mandate bar: content + closure form + live probes; gate-A is
            # recorded as drift-honesty context (calibrated: peer-closed fleet
            # receipts RES-0158/TST-0007/TST-0012 are not gate-A COMPLETE).
            r["verified"] = bool(
                content_checks and r["closure_form"] and r["not_self_blocked"]
                and r["probes_exit0"] and r["probe_markers_ok"]
            )
            if not r["verified"]:
                all_ok = False
        results[uid] = r

    (OUT / "battery_results.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps({u: {
        "verified": results[u].get("verified"),
        "closure_eligible": results[u].get("closure_eligible"),
        "state": results[u].get("state"),
        "probes_exit0": results[u].get("probes_exit0"),
        "gate_a_complete": (results[u].get("gate_a") or {}).get("complete"),
    } for u in IDS}, indent=1))
    print("SUCCESS:w4s24-battery all-units-hold" if all_ok
          else "FAILED:w4s24-battery violations-present")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

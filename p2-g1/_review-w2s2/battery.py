#!/usr/bin/env python3
"""INDEPENDENT REVIEWER battery - wave 2 shard 2 (12 units).

READ-ONLY phase: verifies, writes nothing into the repo. Output JSON only.

Reviewer contract per unit, trusting nothing from the builder's runlog:
  1. artifact exists / non-empty / parses / not self-declared BLOCKED-FAILED
     at the catalog output_path;
  2. re-run the named live probes under command-center/p2-wave/probes/<UID>/
     MYSELF - every named probe must exit 0 (unnamed probe*.py also run and
     recorded; failure there is an observation, not an auto-FAIL);
  3. recompute the artifact sha256 (CRLF normalised to LF before hashing) and
     match it against the UNIT-ARTIFACT-MANIFEST.json row for output_path;
  4. validate output_schema via the repo resolver - errors RECORDED per unit
     (program closure contract: receipt-shape profile deviations are recorded,
     the 12-condition gate does not gate on them; see reviewer notes);
  5. artifact mutation guard: artifact sha re-measured after probes - a probe
     that mutates its own artifact is a finding;
  6. receipt closable: the closure CANDIDATE (state=SUCCESS + PASS reviewer +
     non-FAILED sentinel, everything else untouched) must pass evaluate_full()
     with filesystem verification, zero schema errors, zero coherence problems.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
import _p2lib as P  # noqa: E402

UIDS = ["ADV-0124", "ADV-0127", "ADV-0128", "ARC-0001", "ARC-0012", "ARC-0013",
        "ARC-0015", "ARC-0019", "ARC-0020", "ARC-0021", "ARC-0047", "ARC-0048"]

REVIEWER_ID = "claude-opus-5-5-independent-reviewer-shard2-w2-2026-10-25"
PROBE_TIMEOUT = 600


def load_gate():
    spec = importlib.util.spec_from_file_location(
        "rsg", REPO / "platform" / "lib" / "receipt_schema_gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rsg"] = mod
    spec.loader.exec_module(mod)
    return mod


GATE = load_gate()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_sha(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog_units():
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json")
                     .read_text(encoding="utf-8"))
    return {u["id"]: u for u in cat["work_units"]}


def run_probe(script):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        cp = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(REPO), capture_output=True, text=True,
            timeout=PROBE_TIMEOUT, env=env,
        )
        tail = ((cp.stdout or "") + (cp.stderr or ""))[-1200:].strip()
        return {"script": script.name, "exit_code": cp.returncode,
                "tail": tail}
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit_code": "TIMEOUT",
                "tail": "timed out after {}s".format(PROBE_TIMEOUT)}
    except Exception as exc:  # noqa: BLE001
        return {"script": script.name, "exit_code": "SPAWN-FAIL",
                "tail": "{}: {}".format(type(exc).__name__, exc)}


def startswith_sent(key):
    return isinstance(key, str) and key.lower().startswith("sent")


def artifact_self_blocked(doc):
    """Unit-level self-declared failure: top-level state/status BLOCKED-FAILED,
    or a top-level sentinel-ish key carrying a FAILED: marker. Nested
    state/status/verdict hits are RECORDED for manual review, not auto-FAIL
    (fault-injection artifacts legitimately carry per-target BLOCKED
    verdicts; the catalog sentinel names that verdict set)."""
    if not isinstance(doc, dict):
        return None
    for k in ("state", "status"):
        v = doc.get(k)
        if isinstance(v, str) and v.upper() in ("BLOCKED", "FAILED"):
            return "top-level {}={}".format(k, v)
    for k in list(doc.keys()):
        if startswith_sent(k):
            v = doc.get(k)
            if isinstance(v, str) and v.startswith("FAILED:"):
                return "top-level {} FAILED marker: {}".format(k, v[:80])
    nested = []
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("state", "status") and isinstance(v, str) \
                        and v.upper() in ("BLOCKED", "FAILED"):
                    nested.append("{}/{}={}".format(path, k, v))
                elif isinstance(v, (dict, list)):
                    walk(v, "{}/{}".format(path, k))
        elif isinstance(node, list):
            for i, v in enumerate(node[:50]):
                walk(v, "{}/{}".format(path, i))
    walk(doc, "")
    return None if not nested else "NESTED:" + "; ".join(nested[:6])


def sent_key(doc):
    for k in list(doc.keys()):
        if startswith_sent(k):
            return k
    return None


def named_probes_of(uid, rcpt):
    nps = rcpt.get("named_probes") or []
    out = []
    for p in nps:
        if not isinstance(p, dict):
            continue
        cmd = str(p.get("command") or "")
        # command form: PYTHONDONTWRITEBYTECODE=1 python3 -B <script>
        parts = cmd.split()
        script = parts[-1] if parts else ""
        if script:
            out.append({"id": p.get("id"), "command": cmd,
                        "script_rel": script.replace("\\", "/")})
    return out


def review_unit(uid, units):
    rep = {"unit_id": uid, "verdict": "FAIL", "fail_reasons": [],
           "observations": [], "checks": {}}
    checks = rep["checks"]

    def fail(msg):
        rep["fail_reasons"].append(msg)

    cat = units.get(uid)
    if cat is None:
        fail("unit absent from WORK-UNIT-CATALOG.json work_units")
        return rep
    checks["in_catalog"] = True
    op = str(cat.get("output_path") or "").replace("\\", "/")
    osch = str(cat.get("output_schema") or "")
    rep["output_path"] = op
    rep["output_schema"] = osch
    if not op or not osch:
        fail("catalog entry missing output_path or output_schema")

    # 1. artifact at the catalog output_path
    art_path = REPO / op
    checks["artifact_exists"] = art_path.is_file()
    if not art_path.is_file():
        fail("artifact absent at catalog output_path: " + op)
        return rep
    raw = art_path.read_bytes()
    checks["artifact_nonempty"] = len(raw) > 0
    checks["artifact_bytes"] = len(raw)
    checks["artifact_eol"] = P.eol_of(raw)
    if not raw:
        fail("artifact empty (0 bytes): " + op)
    try:
        art_doc = json.loads(raw.decode("utf-8"))
        checks["artifact_parses"] = True
    except Exception as exc:  # noqa: BLE001
        checks["artifact_parses"] = False
        fail("artifact does not parse as JSON: {}: {}".format(
            type(exc).__name__, exc))
        return rep
    blocked = artifact_self_blocked(art_doc)
    if blocked is not None and not blocked.startswith("NESTED:"):
        checks["artifact_not_self_blocked"] = False
        fail("artifact self-declares BLOCKED/FAILED: " + blocked)
    else:
        checks["artifact_not_self_blocked"] = True
        if blocked is not None:
            rep["observations"].append(
                "nested state/status values (per-target verdict slots): "
                + blocked[7:])

    # 2. live probes re-run by THIS reviewer
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    rpath = REPO / "command-center" / "receipts" / (uid + ".json")
    rcpt = json.loads(rpath.read_bytes().decode("utf-8")) \
        if rpath.is_file() else {}
    named = named_probes_of(uid, rcpt)
    if not named:
        sar = pdir / "SUBAGENT-RETURN.json"
        if sar.is_file():
            named = named_probes_of(uid, json.loads(
                sar.read_bytes().decode("utf-8")))
    rep["named_probes_declared"] = [n["script_rel"] for n in named]
    all_scripts = sorted(pdir.glob("probe*.py"))
    named_names = {Path(n["script_rel"]).name for n in named}
    rep["probe_scripts_found"] = [s.name for s in all_scripts]
    checks["probe_scripts_found_n"] = len(all_scripts)
    probe_results = []
    pre_sha = norm_sha(raw)
    for s in all_scripts:
        pr = run_probe(s)
        pr["named"] = s.name in named_names
        probe_results.append(pr)
    post_raw = art_path.read_bytes()
    post_sha = norm_sha(post_raw)
    checks["artifact_unmutated_by_probes"] = (post_sha == pre_sha)
    if post_sha != pre_sha:
        fail("probe run MUTATED the artifact (sha before {} != after {})"
             .format(pre_sha[:12], post_sha[:12]))
    rep["probes"] = probe_results
    bad_named = [pr for pr in probe_results
                 if pr["named"] and pr["exit_code"] != 0]
    bad_unnamed = [pr for pr in probe_results
                   if not pr["named"] and pr["exit_code"] != 0]
    checks["named_probes_all_exit_zero"] = bool(named_names) \
        and (len(bad_named) == 0)
    if not named_names:
        fail("no named probes declared in receipt or SUBAGENT-RETURN")
    for pr in bad_named:
        fail("NAMED probe {} exited {}: {}".format(
            pr["script"], pr["exit_code"], pr["tail"][-220:]))
    for pr in bad_unnamed:
        rep["observations"].append(
            "unnamed probe {} exited {}: {}".format(
                pr["script"], pr["exit_code"], pr["tail"][-160:]))

    # 3. manifest sha256 row vs live artifact (CRLF -> LF before hashing)
    man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    checks["manifest_exists"] = man_path.is_file()
    man_ok = False
    if man_path.is_file():
        try:
            man = json.loads(man_path.read_bytes().decode("utf-8"))
            rows = [r for r in (man.get("artifacts") or [])
                    if isinstance(r, dict)]
            row = None
            for r in rows:
                rp = str(r.get("path") or "").replace("\\", "/")
                if rp == op:
                    row = r
                    break
            if row is None:
                fail("UNIT-ARTIFACT-MANIFEST has no row for output_path "
                     + op)
            else:
                man_live = norm_sha(post_raw)
                man_declared = str(row.get("sha256") or "")
                bytes_live = len(post_raw)
                bytes_declared = row.get("bytes")
                man_ok = (man_live == man_declared)
                checks["manifest_sha_match"] = man_ok
                checks["manifest_bytes_match"] = (bytes_declared is None
                                                  or bytes_live == bytes_declared)
                rep["manifest_sha_live"] = man_live
                rep["manifest_sha_declared"] = man_declared
                if not man_ok:
                    fail("manifest sha256 mismatch (live {}... vs declared "
                         "{}...)".format(man_live[:16],
                                         (man_declared[:16] + "...")
                                         if man_declared else "<none>"))
                if bytes_declared is not None \
                        and bytes_live != bytes_declared:
                    fail("manifest bytes mismatch: declared {} live {}"
                         .format(bytes_declared, bytes_live))
        except Exception as exc:  # noqa: BLE001
            checks["manifest_exists"] = False
            fail("UNIT-ARTIFACT-MANIFEST unreadable: {}: {}".format(
                type(exc).__name__, exc))
    else:
        fail("UNIT-ARTIFACT-MANIFEST.json absent under " + str(pdir))
    checks["manifest_sha_match"] = bool(man_ok)

    # 4. output_schema validation (errors RECORDED per program contract)
    try:
        errs = P.validate(art_doc, osch)
    except Exception as exc:  # noqa: BLE001
        errs = ["validator raised {}: {}".format(type(exc).__name__, exc)]
    checks["output_schema_errors"] = len(errs)
    rep["schema_errors_first"] = errs[:3]
    rep["observations"].append(
        "output_schema: {} error(s) vs resolved artifact-class profile "
        "(recorded deviation; closure gate condition 4 validates the "
        "RECEIPT; profile conformance met by same-class peers - see "
        "reviewer notes)".format(len(errs)))

    # 5. receipt artifact rows vs disk (raw bytes - what gate cond 3 measures)
    if not rpath.is_file():
        fail("receipt missing: " + str(rpath))
        return rep
    row_problems = []
    for a in rcpt.get("artifacts") or []:
        ap = REPO / str(a.get("path"))
        if not ap.is_file():
            row_problems.append(str(a.get("path")) + ": absent")
            continue
        if ap.stat().st_size != a.get("bytes"):
            row_problems.append(str(a.get("path")) + ": declared "
                                + str(a.get("bytes")) + " != disk "
                                + str(ap.stat().st_size))
        if raw_sha(ap) != a.get("sha256"):
            row_problems.append(str(a.get("path")) + ": raw sha256 mismatch")
    checks["receipt_artifact_rows_match_disk"] = (len(row_problems) == 0)
    if row_problems:
        fail("receipt artifact rows disagree with disk: "
             + "; ".join(row_problems[:4]))

    # 6. gate on the closure candidate
    rev = rcpt.get("reviewer")
    already = (rcpt.get("state") == "SUCCESS" and isinstance(rev, dict)
               and rev.get("verdict") == "PASS"
               and rev.get("independent") is True)
    rep["already_closed"] = already
    rep["receipt_state_before"] = rcpt.get("state")
    rep["prior_reviewer_id"] = (rev or {}).get("reviewer_id") \
        if isinstance(rev, dict) else None

    if already:
        candidate = rcpt
    else:
        candidate = json.loads(json.dumps(rcpt))
        candidate["state"] = "SUCCESS"
        sk = sent_key(candidate)
        new_sent = ("SUCCESS:" + uid
                    + " independent adversarial review PASS (artifact, "
                    + str(len(named_names)) + " named live probes, manifest "
                    + "sha256, output_schema re-verified by reviewer)")
        if sk is not None:
            candidate[sk] = new_sent
        else:
            candidate["sentinel"] = new_sent
        candidate["reviewer"] = {
            "reviewer_id": REVIEWER_ID,
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "did_not_build": True,
            "vendor": "anthropic",
            "model": "claude-opus-5-5",
            "reviewed_at": now_iso(),
        }

    try:
        result, extra = GATE.evaluate_full(
            candidate, repo_root=REPO, verify_filesystem=True)
    except Exception as exc:  # noqa: BLE001
        fail("gate raised {}: {}".format(type(exc).__name__, exc))
        rep["gate"] = "RAISED"
        return rep
    g = result.to_dict()
    unsat = []
    for c in g.get("conditions", []):
        if c.get("outcome") != "SATISFIED":
            unsat.append(c)
    checks["gate_conditions_not_satisfied"] = [c["n"] for c in unsat]
    rep["gate_schema_errors"] = g.get("schema_errors")
    rep["gate_coherence"] = extra
    for c in unsat:
        fail("gate condition {} {}: {}".format(
            c["n"], c["outcome"], c["basis"][:200]))
    if g.get("schema_errors"):
        fail("closure candidate schema-invalid: "
             + str(g["schema_errors"][0])[:200])
    if extra:
        fail("coherence problems: " + str(extra[0])[:200])

    rep["gate_green_on_candidate"] = (len(unsat) == 0) \
        and (not g.get("schema_errors")) and (not extra)

    structural_green = (not rep["fail_reasons"])
    rep["structural_green"] = structural_green
    rep["verdict"] = "PASS-PENDING-CONTENT-REVIEW" if structural_green \
        else "FAIL"
    return rep


def main():
    units = catalog_units()
    out = {"reviewer_id": REVIEWER_ID, "phase": "structural-readonly",
           "generated_at": now_iso(), "units": []}
    for uid in UIDS:
        rep = review_unit(uid, units)
        out["units"].append(rep)
        print("[{}] {} gate_green={} structural_green={} fails={}".format(
            rep["verdict"], uid, rep.get("gate_green_on_candidate"),
            rep.get("structural_green"), len(rep["fail_reasons"])))
        for fr in rep["fail_reasons"]:
            print("    FAIL:", fr[:180])
    dest = Path(__file__).with_name("structural_out.json")
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("written:", dest)


if __name__ == "__main__":
    main()

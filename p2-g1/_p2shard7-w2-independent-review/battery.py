#!/usr/bin/env python3
"""INDEPENDENT REVIEWER battery - wave 2 shard 7 (12 units). Fresh, written by the reviewer.

Lanes per unit (nothing trusted from builders or prior batteries):
  A1 artifact exists at catalog output_path   A2 non-empty
  A3 parses as JSON (utf-8)                   A4 not self-declared BLOCKED/FAILED
  M1 manifest exists+parses                   M2 manifest has row for output_path
  M3 LF-normalized sha256(live artifact) == row.sha256
  M4 ALL manifest rows match live disk (normalized sha; registered instrument truth)
  S1 canonical output_schema validation (schema_resolver.validate_artifact),
     classified ENVELOPE-DRIFT vs CONTENT-DEFECT
  PR all probe*.py under probes/<id>/ re-run by this reviewer, exit 0 required
  RV receipt reviewer block: verdict/independent/reviewer_id (recorded + classified)

Adjudication (unit contract in spawn prompt): gating = A1..A4 + M2 + M3 + PR + no
CONTENT-DEFECT schema class + M4. Envelope-absence (program-wide census drift,
receipt_gate-documented) is disclosed per unit, not unit-fatal.
Phase B (closure writes) only for PASS units, executed after Phase A review.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "lib"))
from schema_resolver import validate_artifact, SchemaResolutionError  # noqa: E402

UIDS = ["BLD-0043", "BLD-0044", "BLD-0045", "BLD-0049", "BLD-0050", "BLD-0058",
        "BLD-0059", "BLD-0061", "CC-0003", "CC-0010", "CC-0019", "CNF-0070"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 300
REVIEWER_ID = "independent-reviewer-shard7-w2-claude-opus-fresh"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def run_probe(script: Path):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        cp = subprocess.run([sys.executable, "-B", str(script)], cwd=str(REPO),
                            capture_output=True, text=True, timeout=PROBE_TIMEOUT, env=env)
        tail = ((cp.stdout or "") + (cp.stderr or "")).strip().splitlines()
        tail_s = " | ".join(tail[-3:])[-400:] if tail else ""
        return {"script": script.name, "exit_code": cp.returncode, "tail": tail_s}
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit_code": "TIMEOUT", "tail": "timeout after %ds" % PROBE_TIMEOUT}
    except Exception as exc:
        return {"script": script.name, "exit_code": "SPAWN-FAIL",
                "tail": "%s: %s" % (type(exc).__name__, exc)}


def self_blocked(doc):
    if not isinstance(doc, dict):
        return None
    st = doc.get("state")
    if isinstance(st, str) and st.strip().upper() in NOT_DELIVERING:
        return "top-level state=" + st
    for k, v in doc.items():
        if isinstance(v, str) and (k.lower().startswith("sent") or k == "completion_marker"):
            if v.startswith(("FAILED:", "BLOCKED:")):
                return k + "=" + v[:80]
    return None


def classify_schema_errors(errs, doc):
    """Split canonical validation errors into envelope-absence vs content defects."""
    env_missing, content = [], []
    root_keys = set(doc.keys()) if isinstance(doc, dict) else set()
    for e in errs:
        loc, _, msg = e.partition(": ")
        msg_l = msg.lower()
        if loc == "<root>" and "is a required property" in msg_l:
            prop = msg.split("'")[1] if "'" in msg else msg
            if prop not in root_keys:
                env_missing.append(prop)
                continue
            content.append(e)
            continue
        if loc == "<root>" and ("is not valid under any of the given schemas" in msg_l
                                or "is valid under each of" in msg_l
                                or "is not of type 'null'" in msg_l):
            continue  # aggregate noise from oneOf branches
        content.append(e)
    cls = "CLEAN" if not errs else ("ENVELOPE-DRIFT" if not content else "CONTENT-DEFECT")
    return cls, sorted(set(env_missing)), content


def review_unit(uid, units):
    rep = {"unit_id": uid, "verdict": "FAIL", "fail_reasons": [], "checks": {}}
    checks, fails = rep["checks"], rep["fail_reasons"]

    def fail(msg):
        fails.append(msg)

    cat = units.get(uid)
    if cat is None:
        fail("unit absent from WORK-UNIT-CATALOG.json work_units")
        return rep
    rep["catalog"] = {"output_path": cat.get("output_path"),
                      "output_schema": cat.get("output_schema"),
                      "dependencies": cat.get("dependencies")}
    op = str(cat.get("output_path") or "").replace("\\", "/")
    osch = str(cat.get("output_schema") or "")

    # A1-A4
    art = REPO / op
    checks["artifact_exists"] = art.is_file()
    if not art.is_file():
        fail("artifact absent at catalog output_path: " + op)
        return rep
    raw = art.read_bytes()
    checks["artifact_nonempty"] = len(raw) > 0
    if not raw:
        fail("artifact empty (0 bytes): " + op)
    try:
        doc = json.loads(raw.decode("utf-8"))
        checks["artifact_parses"] = True
    except Exception as exc:
        checks["artifact_parses"] = False
        fail("artifact does not parse as JSON: %s: %s" % (type(exc).__name__, exc))
        return rep
    sb = self_blocked(doc)
    checks["artifact_not_self_blocked"] = sb is None
    if sb is not None:
        fail("artifact self-declares non-delivery: " + sb)
    rep["artifact_state"] = doc.get("state")
    rep["artifact_sentinel"] = (doc.get("sentinel") or doc.get("completion_sentinel")
                                or doc.get("completion_marker"))

    # M1-M4
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    checks["manifest_exists"] = man_path.is_file()
    primary_row = None
    stale_rows = []
    if not man_path.is_file():
        fail("UNIT-ARTIFACT-MANIFEST.json missing under " + str(pdir))
    else:
        try:
            man = json.loads(man_path.read_bytes().decode("utf-8"))
        except Exception as exc:
            fail("manifest unparsable: %s: %s" % (type(exc).__name__, exc))
            man = None
        if man is not None:
            rows = [r for r in (man.get("artifacts") or []) if isinstance(r, dict)]
            rep["manifest_rows_total"] = len(rows)
            for r in rows:
                rp = str(r.get("path") or "").replace("\\", "/")
                if rp == op:
                    primary_row = r
                ap = REPO / rp
                if not ap.is_file():
                    stale_rows.append(rp + ": absent")
                    continue
                live_norm = norm_sha(ap.read_bytes())
                if live_norm != str(r.get("sha256") or ""):
                    stale_rows.append(rp + ": sha-drift")
            if primary_row is None:
                fail("manifest has no row for output_path " + op)
                checks["manifest_primary_row"] = False
            else:
                checks["manifest_primary_row"] = True
                live_norm = norm_sha((REPO / op).read_bytes())
                declared = str(primary_row.get("sha256") or "")
                checks["manifest_primary_sha_match"] = (live_norm == declared)
                rep["manifest_primary_sha_live"] = live_norm
                rep["manifest_primary_sha_declared"] = declared
                if live_norm != declared:
                    fail("manifest sha256 row mismatch for %s: live %s... vs declared %s..."
                         % (op, live_norm[:16], declared[:16]))
            checks["manifest_stale_rows"] = stale_rows
            if stale_rows:
                fail("manifest rows stale vs live disk: " + "; ".join(stale_rows[:6]))

    # S1 canonical schema validation
    try:
        errs = validate_artifact(doc, osch)
    except SchemaResolutionError as exc:
        errs = ["schema resolver failed: %s" % exc]
    except Exception as exc:
        errs = ["validator raised %s: %s" % (type(exc).__name__, exc)]
    cls, env_missing, content = classify_schema_errors(errs, doc)
    checks["schema_class"] = cls
    checks["schema_errors_total"] = len(errs)
    checks["schema_envelope_missing"] = env_missing
    rep["schema_content_errors"] = content[:8]
    if cls == "CONTENT-DEFECT":
        fail("output_schema CONTENT defects (%d): %s"
             % (len(content), "; ".join(c[:120] for c in content[:3])))
    elif cls == "ENVELOPE-DRIFT":
        rep["schema_disclosure"] = ("ENVELOPE-DRIFT: %d envelope keys absent (%s); program census "
                                    "class per receipt_gate (drift tracked, non-gating); unit "
                                    "contract DELIVERED requires parse, not envelope completeness"
                                    % (len(env_missing), ", ".join(env_missing[:8])))

    # PR probe re-runs
    scripts = sorted(pdir.glob("probe*.py"))
    checks["probe_scripts_found"] = len(scripts)
    probe_results = [run_probe(s) for s in scripts]
    rep["probes"] = probe_results
    bad = [pr for pr in probe_results if pr["exit_code"] != 0]
    checks["probes_all_exit_zero"] = bool(scripts) and not bad
    if not scripts:
        fail("no probe scripts under " + str(pdir))
    for pr in bad:
        fail("probe %s exit=%s: %s" % (pr["script"], pr["exit_code"], pr["tail"][-260:]))

    # RV receipt reviewer block
    rev = doc.get("reviewer")
    rep["receipt_reviewer"] = rev if isinstance(rev, dict) else {"raw": rev}
    if isinstance(rev, dict):
        rid = str(rev.get("reviewer_id") or "")
        mech = (rev.get("verdict") == "PASS" and rev.get("independent") is True)
        rep["receipt_closure_mechanical"] = mech
        if doc.get("state") == "SUCCESS" and mech:
            ident = rid.lower()
            if (uid.lower() in ident or ident.startswith(("probe", "tool", "schema-resolver"))
                    or "probe2" in ident or "probe1" in ident):
                rep["reviewer_identity_class"] = "probe-or-tool-identity (self-certification risk)"
            elif "openai/" in ident or rev.get("vendor") not in (None, "claude-code", "custom"):
                rep["reviewer_identity_class"] = "external-vendor"
            else:
                rep["reviewer_identity_class"] = "other"
        else:
            fail("receipt lacks mechanically-valid closure (state=SUCCESS + reviewer PASS + independent)")

    rep["verdict"] = "PASS" if not fails else "FAIL"
    return rep


def main():
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    units = {u["id"]: u for u in cat["work_units"]}
    out = []
    for uid in UIDS:
        r = review_unit(uid, units)
        out.append(r)
        print("[%s] %s schema=%s probes=%s prim_sha=%s stale=%d"
              % (r["verdict"], uid, r["checks"].get("schema_class"),
                 r["checks"].get("probes_all_exit_zero"),
                 r["checks"].get("manifest_primary_sha_match"),
                 len(r["checks"].get("manifest_stale_rows", []))), flush=True)
        for f in r["fail_reasons"]:
            print("   FAIL:", f[:220], flush=True)
    report = {"generated_at": now_iso(), "reviewer": REVIEWER_ID, "units": out}
    (REPO / "_p2shard7-w2-independent-review" / "review-phaseA.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    np = sum(1 for r in out if r["verdict"] == "PASS")
    print("")
    print("PHASE-A: %d/%d PASS" % (np, len(out)))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Independent reviewer battery, wave 3 shard 9, round 2 (2026-10-26).

Written from scratch by the r2 reviewer; does not import or re-run the 05:56
battery. Five binding checks per unit, per the unit contract:

  1. artifact_ok          - receipt at catalog output_path exists, non-empty,
                            parses as JSON, state not BLOCKED/FAILED.
  2. manifest_sha_row     - probes/<id>/UNIT-ARTIFACT-MANIFEST.json has a row
                            for output_path whose sha256 == live artifact hash
                            (CRLF normalized to LF before hashing). Raw hash
                            agreement recorded too.
  3. probes_rerun_exit0   - every executable command recorded in the receipt
                            (evidence probes, downstream_consumer probes,
                            tests) is re-run under pinned Git Bash + Python
                            3.14; binding requirement: exit 0 AND non-empty
                            output (an exit-0 no-op proves nothing and is
                            recorded as NOOP-FAIL).
  4. output_schema_valid  - estate-canonical resolver
                            (ast-integrate platform/lib/schema_resolver.
                            validate_artifact) returns [] for the receipt
                            against the unit's DECLARED output_schema string.
  5. closure_valid        - state==SUCCESS requires reviewer.verdict==PASS and
                            reviewer.independent is True (receipt_core rule).

Runs read-only against receipts. Verdicts go to r2_results.json.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:/Users/Prekzursil/p2-g1")
OUTDIR = ROOT / "_reviewer-w3s9-r2"
CATALOG = ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
RESOLVER = Path(
    "C:/Users/Prekzursil/source/ast-integrate/platform/lib/schema_resolver.py"
)
BASH = r"C:\Program Files\Git\bin\bash.exe"

IDS = [
    "IMP-0022", "IMP-0031", "IMP-0035", "IMP-0036", "IMP-0037", "IMP-0038",
    "IMP-0041", "IMP-0044", "IMP-0051", "IMP-0068", "IMP-0070", "IMP-0084",
]

# env-assign prefix then python/python3/bash/sh as first word => executable
EXEC_RE = re.compile(
    r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(python3?|bash|sh)\b"
)

TIMEOUT_S = 600


def load_resolver():
    spec = importlib.util.spec_from_file_location("p2r2_schema_resolver", RESOLVER)
    m = importlib.util.module_from_spec(spec)
    sys.modules["p2r2_schema_resolver"] = m
    spec.loader.exec_module(m)
    return m


def live_hash(path: Path):
    b = path.read_bytes()
    lf = hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()
    raw = hashlib.sha256(b).hexdigest()
    return lf, raw, len(b)


def run_pinned(cmd: str):
    """Run one recorded command under pinned Git Bash + Python 3.14."""
    env = dict(os.environ)
    env["PATH"] = "/c/Python314:/usr/bin:/bin:" + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proof = 'echo "RT-PROOF $(command -v python3) $(python3 --version 2>&1)"'
    try:
        p = subprocess.run(
            [BASH, "-c", f"{proof}; {cmd}"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=TIMEOUT_S,
        )
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        rt_proof = out.splitlines()[0] if out.startswith("RT-PROOF") else "?"
        body_out = out[len(rt_proof):].strip() if out.startswith("RT-PROOF") else out
        return {
            "exit": p.returncode,
            "stdout_len": len(body_out),
            "stderr_len": len(err),
            "stdout_head": body_out[:220],
            "stderr_head": err[:220],
            "rt_proof": rt_proof,
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit": None, "stdout_len": 0, "stderr_len": 0,
            "stdout_head": "", "stderr_head": "", "rt_proof": "?",
            "timeout": True,
        }


def collect_commands(doc):
    """Every command string recorded anywhere in the receipt, with its path."""
    found = []

    def walk(o, path):
        if isinstance(o, dict):
            c = o.get("command")
            if isinstance(c, str) and c.strip():
                found.append({"path": path, "role": o.get("role", "?"),
                              "recorded_exit": o.get("exit_code"), "command": c})
            for k, v in o.items():
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(doc, "")
    # dedupe identical command strings, keep first occurrence context
    seen = {}
    for c in found:
        seen.setdefault(c["command"], c)
    return list(seen.values())


def secondary_validation(resolver, uid, receipt, unit):
    """Supplementary: for compound output_schema, validate the identifiable
    secondary doc against the second declared schema. Returns list of strings."""
    declared = unit.get("output_schema") or ""
    parts = [p.strip() for p in declared.split("+") if p.strip()]
    notes = []
    if len(parts) < 2:
        return notes
    second = parts[1]
    second_path = ROOT / second
    if not second_path.is_file():
        notes.append(f"secondary schema missing on disk: {second}")
        return notes
    schema = json.loads(second_path.read_text(encoding="utf-8"))

    # locate the secondary doc
    doc, doc_path = None, None
    if uid == "IMP-0044":
        doc = receipt.get("probe_control")
        doc_path = "<receipt>.probe_control"
    else:
        cands = {
            "IMP-0036": ["command-center/p2-wave/probes/IMP-0036/packets.json"],
            "IMP-0051": ["command-center/p2-wave/probes/IMP-0051/taxonomy-document.json"],
        }.get(uid, [])
        for c in cands:
            p = ROOT / c
            if p.is_file():
                doc = json.loads(p.read_text(encoding="utf-8"))
                doc_path = c
                break
    if doc is None:
        notes.append(f"{uid}: no identifiable secondary doc for {second}")
        return notes
    try:
        from jsonschema import Draft202012Validator
        errs = sorted(
            Draft202012Validator(schema).iter_errors(doc),
            key=lambda e: list(e.absolute_path),
        )
        msgs = []
        for e in errs[:8]:
            loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
            msgs.append(f"{loc}: {e.message}")
        notes.append(
            f"secondary {doc_path} vs {second}: {len(errs)} errors"
            + ("; " + " | ".join(msgs) if msgs else " (VALID)")
        )
    except Exception as exc:  # noqa: BLE001
        notes.append(f"secondary validation errored: {exc!r}")
    return notes


def main():
    cat = json.loads(CATALOG.read_bytes().decode("utf-8"))
    wu = {u["id"]: u for u in cat["work_units"]}
    resolver = load_resolver()
    results = {}

    for uid in IDS:
        unit = wu[uid]
        out_path = ROOT / unit["output_path"]
        rec = {"unit": uid, "output_path": unit["output_path"],
               "declared_schema": unit.get("output_schema")}
        print(f"=== {uid} ===", flush=True)

        # ---- 1. artifact_ok ----
        if not out_path.is_file():
            rec["artifact_ok"] = False
            rec["artifact_fail"] = "missing"
            results[uid] = rec
            continue
        size = out_path.stat().st_size
        try:
            receipt = json.loads(out_path.read_bytes().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            rec["artifact_ok"] = False
            rec["artifact_fail"] = f"unparsable: {exc!r}"[:200]
            results[uid] = rec
            continue
        state = receipt.get("state")
        status = receipt.get("status")
        selfblocked = (
            state in ("BLOCKED", "FAILED")
            or (isinstance(status, str) and status.upper() in ("BLOCKED", "FAILED"))
        )
        rec["artifact_ok"] = (size > 0) and (not selfblocked)
        rec["artifact_state"] = state
        rec["artifact_status"] = status if isinstance(status, str) else None
        if not rec["artifact_ok"]:
            rec["artifact_fail"] = f"size={size} selfblocked={selfblocked}"
            results[uid] = rec
            continue

        # ---- 2. manifest sha row ----
        man_path = ROOT / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        lf, raw, nbytes = live_hash(out_path)
        rec["live_sha_lf"] = lf
        rec["live_sha_raw"] = raw
        rec["live_bytes"] = nbytes
        if not man_path.is_file():
            rec["manifest_sha_row"] = False
            rec["manifest_fail"] = "UNIT-ARTIFACT-MANIFEST.json missing"
        else:
            man = json.loads(man_path.read_text(encoding="utf-8"))
            rows = [a for a in man.get("artifacts", [])
                    if a.get("path") == unit["output_path"]]
            if not rows:
                rec["manifest_sha_row"] = False
                rec["manifest_fail"] = "no row for output_path"
            else:
                row = rows[0]
                rec["manifest_row_sha"] = row.get("sha256")
                rec["manifest_sha_row"] = row.get("sha256") == lf
                rec["manifest_raw_agrees"] = row.get("sha256") == raw

        # ---- 3. probes re-run ----
        cmds = collect_commands(receipt)
        probe_report = []
        probes_ok = True
        for c in cmds:
            entry = {"role": c["role"], "where": c["path"][:60], "command": c["command"][:160]}
            if not EXEC_RE.match(c["command"]):
                entry["class"] = "non-executable-prose"
                entry["exit"] = "SKIP"
                probe_report.append(entry)
                continue
            r = run_pinned(c["command"])
            entry["class"] = "executed"
            entry["exit"] = r["exit"]
            entry["rt_proof"] = r["rt_proof"]
            entry["stdout_len"] = r["stdout_len"]
            entry["stderr_len"] = r["stderr_len"]
            entry["stdout_head"] = r["stdout_head"]
            entry["stderr_head"] = r["stderr_head"]
            entry["timeout"] = r["timeout"]
            if r["timeout"] or r["exit"] != 0:
                probes_ok = False
                entry["verdict"] = "FAIL"
            elif r["stdout_len"] == 0 and r["stderr_len"] == 0:
                probes_ok = False
                entry["verdict"] = "NOOP-FAIL (exit 0, zero output)"
            else:
                entry["verdict"] = "PASS"
            probe_report.append(entry)
        rec["probe_report"] = probe_report
        rec["probes_rerun_exit0"] = probes_ok

        # ---- 4. output_schema ----
        try:
            errs = resolver.validate_artifact(receipt, unit.get("output_schema"))
        except Exception as exc:  # noqa: BLE001
            errs = [f"<resolver error: {exc!r}>"]
        rec["schema_errors"] = errs
        rec["output_schema_validates"] = (len(errs) == 0)

        # ---- supplementary: secondary doc ----
        rec["secondary_notes"] = secondary_validation(resolver, uid, receipt, unit)

        # ---- 5. closure ----
        rev = receipt.get("reviewer") or {}
        rec["closure_state"] = state
        rec["closure_reviewer_verdict"] = rev.get("verdict")
        rec["closure_independent"] = rev.get("independent")
        rec["closure_valid"] = (
            state != "SUCCESS"
            or (rev.get("verdict") == "PASS" and rev.get("independent") is True)
        )

        checks = {
            "artifact_ok": rec["artifact_ok"],
            "manifest_sha_row": rec.get("manifest_sha_row", False),
            "probes_rerun_exit0": rec["probes_rerun_exit0"],
            "output_schema_validates": rec["output_schema_validates"],
            "closure_valid": rec["closure_valid"],
        }
        rec["checks"] = checks
        rec["ALL_HOLD"] = all(checks.values())
        results[uid] = rec
        print(json.dumps(checks), flush=True)

    out = OUTDIR / "r2_results.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("\nwritten:", out)


if __name__ == "__main__":
    main()

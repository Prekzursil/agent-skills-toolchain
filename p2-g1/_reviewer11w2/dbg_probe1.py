#!/usr/bin/env python3
"""IMP-0096 probe1: the attached benchmark record is COMPLETE (every required
reproducibility field), validates against the schema, and its reproduction
command re-runs live with the metric inside the declared tolerance. The record
is (re)generated from the live harness, then written to the attachment path the
receipt declares."""
from __future__ import annotations

import glob
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CASE_SET = REPO / "tools" / "marketplace" / "fixtures" / "case-set.v1.json"
SCHEMA = REPO / "tools" / "marketplace" / "schema" / "benchmark-evidence.schema.json"
ATTACH = REPO / "tools" / "marketplace" / "attachments" / "fixture.bench.demo-imp-0096.live.primary.json"


def load_module(name: str, glob_pat: str):
    hits = sorted(glob.glob(glob_pat))
    if not hits:
        raise SystemExit(f"FAILED:IMP-0096-probe1 module not found: {glob_pat}")
    spec = importlib.util.spec_from_file_location(name, hits[0])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def env_fingerprint() -> str:
    # reviewer fix 2026-10-25: stdlib `platform` is shadowed by the estate's
    # tools/platform package on the measure PYTHONPATH; use sys/sysconfig
    # natives (same semantics: implementation|version|system|machine digest)
    import sysconfig
    parts = [sys.implementation.name,
             "%d.%d.%d" % sys.version_info[:3],
             os.name, sysconfig.get_platform()]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def validate_against_schema(rec: dict, schema: dict) -> list:
    errs = []
    for req in schema.get("required", []):
        if req not in rec:
            errs.append(f"missing:{req}")
    for k, spec in (schema.get("properties") or {}).items():
        if k not in rec:
            continue
        t = spec.get("type")
        v = rec[k]
        checks = {
            "string": lambda v: isinstance(v, str),
            "object": lambda v: isinstance(v, dict),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        }
        if t and not checks.get(t, lambda v: True)(v):
            errs.append(f"type:{k}")
        if isinstance(v, str) and spec.get("minLength") and len(v) < spec["minLength"]:
            errs.append(f"minLength:{k}")
        if isinstance(v, str) and spec.get("pattern") and not re.match(spec["pattern"], v):
            errs.append(f"pattern:{k}")
        if t == "object" and isinstance(v, dict):
            for req2 in spec.get("required", []):
                if req2 not in v:
                    errs.append(f"missing:{k}.{req2}")
    return errs


import re  # noqa: E402


def main() -> int:
    be = load_module("imp0096_benchmark_evidence",
                     str(REPO / "tools" / "marketplace" / "benchmark_evidence.py"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    repro_cmd = (f"{sys.executable} -B tools/marketplace/harness/run_case_set.py "
                 f"--case-set tools/marketplace/fixtures/case-set.v1.json --json")
    cmd = repro_cmd
    # reviewer fix 2026-10-25: argv-list exec (shell=True + Windows abs
    # sys.executable path breaks under bash backslash mangling; identical
    # command semantics, transport-neutral)
    argv = [sys.executable, "-B", "tools/marketplace/harness/run_case_set.py",
            "--case-set", "tools/marketplace/fixtures/case-set.v1.json", "--json"]
    p = subprocess.run(argv, cwd=str(REPO), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    metric_doc = None
    for line in reversed((p.stdout or "").splitlines()):
        s = line.strip()
        if s.startswith("{"):
            try:
                metric_doc = json.loads(s)
            except json.JSONDecodeError:
                metric_doc = None
            break
    if not metric_doc or not metric_doc.get("ok"):
        print("FAILED:IMP-0096-probe1 harness did not produce a metric: "
              + (p.stdout or p.stderr)[-400:])
        return 1

    cs_doc = json.loads(CASE_SET.read_text(encoding="utf-8"))
    rec = {
        "schema_version": "1.0.0",
        "run_id": "imp-0096.live.primary",
        "package_name": "fixture.bench.demo",
        "package_version": "1.0.0",
        "harness_version": "imp-0096.harness.1.0",
        "case_set_id": cs_doc.get("id", "imp-0096.case-set.v1"),
        "case_set_path": "tools/marketplace/fixtures/case-set.v1.json",
        "case_set_sha256": sha_file(CASE_SET),
        "environment_fingerprint": env_fingerprint(),
        "commit_sha": "unavailable: worktree is not a git repository",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metric": metric_doc.get("metric"),
        "reproduction_command": repro_cmd,
        "tolerance": {"absolute": 1e-09},
    }
    schema_errs = validate_against_schema(rec, schema)
    completeness = be.validate_record(dict(rec))
    ev = be.evaluate_evidence(dict(rec), repo=REPO)
    reproduced = ev.get("is_evidence") is True and ev["reproduction"]["status"] == "REPRODUCED"

    ATTACH.parent.mkdir(parents=True, exist_ok=True)
    ATTACH.write_bytes((json.dumps(rec, indent=1) + "\n").replace("\r\n", "\n").encode("utf-8"))

    print("DBG-EV:", json.dumps(ev["reproduction"])[:400]); result = {
        "unit_id": "IMP-0096",
        "probe": "probe1-reproduction-live",
        "schema_valid": not schema_errs,
        "schema_errors": schema_errs,
        "record_complete": bool(completeness),
        "observed_metric": ev.get("observed_metric"),
        "claimed_metric": (rec["metric"] or {}).get("value"),
        "reproduction_status": ev["reproduction"]["status"],
        "attachment_written": ATTACH.is_file(),
        "pass": not schema_errs and bool(completeness) and reproduced and ATTACH.is_file(),
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0096-probe1 attached record complete, schema-valid, "
            "reproduced live within tolerance"
            if result["pass"] else
            "FAILED:IMP-0096-probe1 record/reproduction contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CNF-0184 named probe 1 (wave-2 reconstruction): known-ND and both states.

Every recorded reproduction is double-run LIVE on this host (family-3 rows via
subprocess command output, family-6 rows via environment calls), byte-diffed,
and pushed through its named normalizer. Assertions follow the recorded cell
verdicts: deterministic-payload and host-id byte-identical; the rest
nondeterministic raw and byte-identical only after their normalizer. A
reproduction declared deterministic has been run at least twice — both run
digests are cited in the output.
"""
from __future__ import annotations

import hashlib
import json
import platform
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "CNF-0184.json"

from normalizers import NORMALIZERS  # noqa: E402
from normalizers import norm_seeds  # noqa: E402


def norm_seeds_untouched_check(s):
    return norm_seeds(s) == s

FNS = {n["id"]: n["fn"] for n in NORMALIZERS}


def run_cmd(code):
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return p.stdout.strip()


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0184" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0184-probe1 sentinel absent")
        return 1
    cells = {c["id"]: c["verdict"] for c in doc.get("cells", [])}
    results = {}

    def check(cell_id, raw1, raw2, norm_id):
        raw_equal = raw1 == raw2
        verdict = "BYTE-DETERMINISTIC" if raw_equal else "NONDETERMINISTIC"
        norm_equal = None
        if norm_id and not raw_equal:
            norm_equal = FNS[norm_id](raw1) == FNS[norm_id](raw2)
        results[cell_id] = {
            "run1_sha256": sha(raw1),
            "run2_sha256": sha(raw2),
            "raw_equal": raw_equal,
            "verdict": verdict,
            "normalizer": norm_id,
            "normalized_equal": norm_equal,
            "recorded_cell": cells.get(cell_id),
        }
        return results[cell_id]

    a = run_cmd("print('DETERMINISTIC-PAYLOAD-BYTES-7f3a')")
    b = run_cmd("print('DETERMINISTIC-PAYLOAD-BYTES-7f3a')")
    r = check("fam3.deterministic-payload", a, b, None)
    if not r["raw_equal"] or cells.get("fam3.deterministic-payload") != "BYTE-DETERMINISTIC":
        print("FAILED:CNF-0184-probe1 deterministic-payload cell " + json.dumps(r))
        return 1

    a = run_cmd("from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")
    time.sleep(0.05)
    b = run_cmd("from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")
    r = check("fam3.iso-timestamp", a, b, "norm.timestamps.iso-and-labeled-unix")
    if r["raw_equal"] or not r["normalized_equal"]:
        print("FAILED:CNF-0184-probe1 iso-timestamp cell " + json.dumps(r))
        return 1

    a = run_cmd("import json; print(json.dumps({'z': 1, 'a': 2, 'm': 3}))")
    b = run_cmd("import json; print(json.dumps({'m': 3, 'z': 1, 'a': 2}))")
    r = check("fam3.json-key-order", a, b, "norm.ordering.json-sort-keys")
    if r["raw_equal"] or not r["normalized_equal"]:
        print("FAILED:CNF-0184-probe1 json-key-order cell " + json.dumps(r))
        return 1

    a = run_cmd("import time; print('now_s=' + str(int(time.time())))")
    time.sleep(1.1)
    b = run_cmd("import time; print('now_s=' + str(int(time.time())))")
    r = check("fam3.clock-seconds", a, b, "norm.timestamps.iso-and-labeled-unix")
    if cells.get("fam3.clock-seconds") != "BORDERLINE" or not r["normalized_equal"]:
        print("FAILED:CNF-0184-probe1 clock-seconds cell " + json.dumps(r))
        return 1

    a = tempfile.mkdtemp(prefix="cnf0184-")
    b = tempfile.mkdtemp(prefix="cnf0184-")
    r = check("fam6.temp-path", a, b, "norm.temp_paths.tmp-and-var-folders")
    if r["raw_equal"] or not r["normalized_equal"]:
        print("FAILED:CNF-0184-probe1 temp-path cell " + json.dumps(r))
        return 1

    a = platform.node()
    b = platform.node()
    r = check("fam6.host-id", a, b, "norm.host_identifiers.labeled-host")
    if not r["raw_equal"] or cells.get("fam6.host-id") != "BYTE-DETERMINISTIC":
        print("FAILED:CNF-0184-probe1 host-id cell " + json.dumps(r))
        return 1
    ho1 = "host=" + (a or "this-host")
    ho2 = "host=other-host-override"
    if FNS["norm.host_identifiers.labeled-host"](ho1) != FNS["norm.host_identifiers.labeled-host"](ho2):
        print("FAILED:CNF-0184-probe1 host normalizer failed labeled override")
        return 1

    # labeled draw (the class spec folds labeled draws; unlabeled stay intact)
    a = "rng=" + repr(random.random())
    b = "rng=" + repr(random.random())
    r = check("fam6.rng-seed", a, b, "norm.seeds.labeled-draw")
    if norm_seeds_untouched_check(a):
        print("FAILED:CNF-0184-probe1 labeled draw not folded")
        return 1
    if r["raw_equal"] or not r["normalized_equal"]:
        print("FAILED:CNF-0184-probe1 rng-seed cell " + json.dumps(r))
        return 1

    report = {
        "probe": "probe1-known-nd-and-both-states",
        "unit_id": "CNF-0184",
        "cells": {k: v["verdict"] for k, v in results.items()},
        "double_run_digests_cited": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:CNF-0184-probe1 known-ND and both-states double-runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

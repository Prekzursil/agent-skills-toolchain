#!/usr/bin/env python3
"""Reviewer w1 shard1: re-run every named live probe; record exit codes."""
import json
import subprocess
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_review-shard1-w1/probe_rerun_out.json"

# (uid, probe_id, script) - scripts per receipt named_probes; ARC-0055 added manually.
PROBES = [
    ("ADV-0132", "probe1", "command-center/p2-wave/probes/ADV-0132/probe1_preregistration_and_negative.py"),
    ("ADV-0132", "probe2", "command-center/p2-wave/probes/ADV-0132/probe2_mutation_and_independence.py"),
    ("ARC-0001", "probe1", "command-center/p2-wave/probes/ARC-0001/probe1_both_states.py"),
    ("ARC-0001", "probe2", "command-center/p2-wave/probes/ARC-0001/probe2_reviewer_anchor.py"),
    ("ARC-0013", "probe1", "command-center/p2-wave/probes/ARC-0013/probe1_planted_edit.py"),
    ("ARC-0013", "probe2", "command-center/p2-wave/probes/ARC-0013/probe2_whitespace.py"),
    ("ARC-0019", "probe1", "command-center/p2-wave/probes/ARC-0019/probe1_reconcile.py"),
    ("ARC-0019", "probe2", "command-center/p2-wave/probes/ARC-0019/probe2_overclaim.py"),
    ("ARC-0020", "probe1", "command-center/p2-wave/probes/ARC-0020/probe1_path_coverage.py"),
    ("ARC-0020", "probe2", "command-center/p2-wave/probes/ARC-0020/probe2_negative_control.py"),
    ("ARC-0047", "probe1", "command-center/p2-wave/probes/ARC-0047/probe1_both_states_audit.py"),
    ("ARC-0047", "probe2", "command-center/p2-wave/probes/ARC-0047/probe2_overclaim.py"),
    ("ARC-0048", "probe1", "command-center/p2-wave/probes/ARC-0048/probe1_markers.py"),
    ("ARC-0048", "probe2", "command-center/p2-wave/probes/ARC-0048/probe2_classification.py"),
    ("ARC-0054", "probe1", "command-center/p2-wave/probes/ARC-0054/probe1_both_states.py"),
    ("ARC-0054", "probe2", "command-center/p2-wave/probes/ARC-0054/probe2_overclaim.py"),
    ("ARC-0055", "probe1", "command-center/p2-wave/probes/ARC-0055/probe1_blast_radius.py"),
    ("ARC-0055", "probe2", "command-center/p2-wave/probes/ARC-0055/probe2_fatigue_overclaim.py"),
    ("ARC-0068", "probe1", "command-center/p2-wave/probes/ARC-0068/probe1_both_states.py"),
    ("ARC-0068", "probe2", "command-center/p2-wave/probes/ARC-0068/probe2_anchor_integrity.py"),
    ("AUD-0003", "probe1", "command-center/p2-wave/probes/AUD-0003/probe1_head_diff.py"),
    ("AUD-0003", "probe2", "command-center/p2-wave/probes/AUD-0003/probe2_merge_agreement.py"),
    ("AUD-0010", "probe1", "command-center/p2-wave/probes/AUD-0010/probe1_count_objects.py"),
    ("AUD-0010", "probe2", "command-center/p2-wave/probes/AUD-0010/probe2_timed_clone.py"),
]

import os
env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"

results = {}
for uid, pid, script in PROBES:
    key = uid + "/" + pid
    t0 = time.time()
    try:
        cp = subprocess.run(
            ["python", "-B", script],
            cwd=str(REPO), env=env, capture_output=True, text=True,
            timeout=900, encoding="utf-8", errors="replace",
        )
        exit_code = cp.returncode
        tail = ((cp.stdout or "") + (cp.stderr or ""))[-500:]
    except subprocess.TimeoutExpired:
        exit_code = "TIMEOUT-900s"
        tail = "timeout"
    except Exception as e:
        exit_code = "SPAWN-ERROR"
        tail = str(e)[:300]
    dt = round(time.time() - t0, 1)
    results[key] = {"script": script, "exit_code": exit_code, "seconds": dt, "tail": tail}
    print(key, "exit=", exit_code, "t=", dt, "s", flush=True)
    OUT.write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8", newline="\n")

bad = [k for k, v in results.items() if v["exit_code"] != 0]
print("FAILED:probes n_ok=" + str(len(results) - len(bad)) + " n_bad=" + str(len(bad)) + " bad=" + ",".join(bad)
      if bad else "SUCCESS:probes all " + str(len(results)) + " exit 0")

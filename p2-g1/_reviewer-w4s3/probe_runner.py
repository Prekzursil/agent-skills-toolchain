#!/usr/bin/env python3
"""w4s3 reviewer phase 2: live probe re-run battery.

For each unit, re-run the unit's OWN named probes (probe1_*/probe2_* scripts
registered in the receipt's evidence + the program's delivered-measure) with
cwd=repo root, capturing exit codes. Records results to probe_results.json.
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IDS = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
       "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]

# probe script per unit, taken verbatim from each receipt's evidence[].probes[].command
BATTERY = {
    "ARC-0055": ["command-center/p2-wave/probes/ARC-0055/probe1_blast_radius.py",
                 "command-center/p2-wave/probes/ARC-0055/probe2_fatigue_overclaim.py",
                 "command-center/p2-wave/_measure_one_delivered.py ARC-0055"],
    "ARC-0056": ["command-center/p2-wave/probes/ARC-0056/probe1_totality.py",
                 "command-center/p2-wave/probes/ARC-0056/probe2_alias_roundtrip.py",
                 "command-center/p2-wave/_measure_one_delivered.py ARC-0056"],
    "ARC-0076": ["command-center/p2-wave/probes/ARC-0076/probe1_order_effect.py",
                 "command-center/p2-wave/probes/ARC-0076/probe2_independence_and_weak.py",
                 "command-center/p2-wave/_measure_one_delivered.py ARC-0076"],
    "AUD-0003": ["command-center/p2-wave/probes/AUD-0003/probe1_head_diff.py",
                 "command-center/p2-wave/probes/AUD-0003/probe2_merge_agreement.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0003"],
    "AUD-0005": ["command-center/p2-wave/probes/AUD-0005/probe1_tag_deref.py",
                 "command-center/p2-wave/probes/AUD-0005/probe2_release_assets.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0005"],
    "AUD-0008": ["PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0008/probe1_ancestor.py",
                 "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0008/probe2_path_surface.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0008"],
    "AUD-0010": ["command-center/p2-wave/probes/AUD-0010/probe1_count_objects.py",
                 "command-center/p2-wave/probes/AUD-0010/probe2_timed_clone.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0010"],
    "AUD-0026": ["command-center/p2-wave/probes/AUD-0026/probe1_declared_split.py",
                 "command-center/p2-wave/probes/AUD-0026/probe2_shipped_import_graph.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0026"],
    "AUD-0032": ["command-center/p2-wave/probes/AUD-0032/probe1_ast_refs.py",
                 "command-center/p2-wave/probes/AUD-0032/probe2_dynamic_reach.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0032"],
    "AUD-0033": ["command-center/p2-wave/probes/AUD-0033/probe1_extract_existence.py",
                 "command-center/p2-wave/probes/AUD-0033/probe2_git_log_missing.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0033"],
    "AUD-0042": ["command-center/p2-wave/probes/AUD-0042/probe1_exit_codes.py",
                 "command-center/p2-wave/probes/AUD-0042/probe2_result_summaries.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0042"],
    "AUD-0043": ["command-center/p2-wave/probes/AUD-0043/probe1_source_pytest.py",
                 "command-center/p2-wave/probes/AUD-0043/probe2_installed_console.py",
                 "command-center/p2-wave/_measure_one_delivered.py AUD-0043"],
}

results = {}
for uid in IDS:
    cmds = BATTERY.get(uid)
    if cmds is None:
        # AUD-0008: derive from the receipt's evidence probes
        rdoc = json.loads((REPO / "command-center/receipts" / f"{uid}.json").read_text(encoding="utf-8"))
        cmds = []
        for e in rdoc.get("evidence") or []:
            for p in e.get("probes") or []:
                c = p.get("command") or ""
                if c and "_measure_one_delivered" not in c and c not in cmds:
                    cmds.append(c)
    results[uid] = {}
    for c in cmds:
        t0 = time.time()
        argv = c.split()
        if argv[0] in ("PYTHONDONTWRITEBYTECODE=1",):
            argv = argv[1:]
        if argv and argv[0].startswith("PYTHONDONTWRITEBYTECODE="):
            argv = argv[1:]
        if argv and argv[0] in ("python3", "python"):
            argv[0] = sys.executable
        elif argv and argv[0].endswith(".py"):
            argv = [sys.executable, "-B"] + argv
        if "-B" in argv[1:]:
            argv.remove("-B")
        env = {"PYTHONDONTWRITEBYTECODE": "1", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
               "PATH": __import__("os").environ.get("PATH", ""), "HOME": __import__("os").environ.get("HOME", ""),
               "GIT_TERMINAL_PROMPT": "0"}
        try:
            cp = subprocess.run(argv, cwd=str(REPO), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800, env=env)
            rc, tail = cp.returncode, (cp.stdout or "")[-400:] + " ||ERR|| " + (cp.stderr or "")[-400:]
        except subprocess.TimeoutExpired:
            rc, tail = -999, "TIMEOUT after 1800s"
        except Exception as e:  # noqa: BLE001
            rc, tail = -998, f"{type(e).__name__}: {e}"
        results[uid][c] = {"exit_code": rc, "seconds": round(time.time() - t0, 1), "tail": tail[-600:]}
        print(f"{uid} rc={rc} {round(time.time()-t0,1)}s :: {c}")
        sys.stdout.flush()

(Path(__file__).parent / "probe_results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
print("WROTE probe_results.json")

#!/usr/bin/env python3
"""Shard6 wave-2 resume driver: live probes -> SUBAGENT-RETURN -> measure.

For each unit: run probe1 then probe2 (both must exit 0), write
probes/<id>/SUBAGENT-RETURN.json via _shard6lib.write_return (which also
rewrites the deterministic per-unit manifest), then run
command-center/p2-wave/_measure_one_delivered.py and require SUCCESS.

Receipts are NEVER rewritten: all 8 receipts carry pre-existing independent
reviewer closures (verdict=PASS, independent=true) that still verify live;
write_return quotes those closures verbatim and claims none of its own.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
from _shard6lib import write_return  # noqa: E402

PROBES = {
    "BLD-0016": ["probe1_planted_controls.py", "probe2_independent_stat.py"],
    "BLD-0027": ["probe1_runner_fault_matrix.py", "probe2_reducer_harvester_audit.py"],
    "BLD-0028": ["probe1_harvester.py", "probe2_verify_census.py"],
    "BLD-0032": ["probe1_controls.py", "probe2_reviewer.py"],
    "BLD-0033": ["probe1_planted_duplicate.py", "probe2_independent_queries.py"],
    "BLD-0035": ["probe1_salvage_model.py", "probe2_live_walk_recheck.py"],
    "BLD-0040": ["probe1_oracle_predicate.py", "probe2_live_regrade.py"],
    "BLD-0042": ["probe1_census_predicate.py", "probe2_live_ast_recheck.py"],
}

NOTES = {
    "BLD-0016": (
        "Resume 2026-10-25: prior builder wrote both probes (planted-controls "
        "classifier + PowerShell Get-Item two-instrument recheck) then died "
        "before manifest/return. Both probes re-ran live this session exit 0; "
        "manifest + return written on resume. Receipt keeps its pre-existing "
        "independent closure (29/29 Final-Deliverables items unbound-ABSENT, "
        "byte-size+sha256 read off disk per row). No owner gate."
    ),
    "BLD-0027": (
        "Resume 2026-10-25: prior builder wrote both probes (runner fault "
        "matrix: timeout/SIGKILL/partition/quiet-active/old-finished/"
        "missing-exit0; reducer-harvester AND-gate audit) then died before "
        "manifest/return. Both re-ran live exit 0 (6/6 fault scenarios match "
        "receipt; exit-zero mutant blindspot reproduced). Receipt keeps its "
        "pre-existing independent closure. No owner gate."
    ),
    "BLD-0028": (
        "Resume 2026-10-25: prior builder wrote both probes (uncontrolled-zero "
        "harvester self-test incl. use-vs-mention; whole-program census "
        "consistency 74+7071=7145, requeue 216, corpus 466, lanes 99) then "
        "died before manifest/return. Both re-ran live exit 0. Receipt keeps "
        "its pre-existing independent closure. No owner gate."
    ),
    "BLD-0032": (
        "Resume 2026-10-25: prior builder wrote both probes (ungrounded/"
        "flagged-drop controls incl. qualified twins clean; reviewer hand "
        "trace of 6 evidence rows to cited lines) then died before manifest/"
        "return. Both re-ran live exit 0. Receipt keeps its pre-existing "
        "independent closure. No owner gate."
    ),
    "BLD-0033": (
        "Resume 2026-10-25: prior builder died mid-probe1, leaving a corrupted "
        "vocab_overlap line and a shape-shingle(w=24) classifier that diverged "
        "from the receipt's own method. Repair (2 probe-fix cycles): rebuilt "
        "probe1 on the receipt method verbatim - identifier-normalized w=5 "
        "shingles Jaccard - which reproduces the recorded planted score 1.0 "
        "exactly and keeps the novel fixture at 0.05 (< threshold 0.52 and "
        "< novel_ceiling 0.34); probe2 authored fresh on the receipt reviewer's "
        "three instruments (pickaxe --diff-filter=D, inventory globs with "
        "empty-root silence, host live walk of ~/.claude + ~/.agents). Both "
        "live exit 0. Receipt keeps its pre-existing independent closure. "
        "No owner gate."
    ),
    "BLD-0035": (
        "Resume 2026-10-25: no probe dir survived the dead builder; both "
        "probes authored fresh. probe1 rebuilds the recoverable-git salvage "
        "model (plant->delete->recover by rev) and re-derives counts "
        "(1+2+91+15=109 surfaces; 77 deleted paths; 5 trees; NC-ABSENT "
        "both-states). probe2 walks the live worktree: 77/77 deleted paths "
        "still absent; 31/91 PRESERVED rows verified live; 60 rows cite "
        "production-worktree artifacts absent here (tools/lib/hooks/"
        "pre-tool.json, tools/lib/tests/test_salvage.mjs) - surfaced as "
        "worktree drift, not folded: the receipt's own answer scopes those "
        "retentions to the Linux worktree (worktree_git=False, tools_lib="
        "True) and carries residual_unknowns + recovery_route for exactly "
        "this; 3 LOST rows carry no retained_path and their synthetic symbol "
        "appears nowhere under live tools//platform trees. Receipt keeps its "
        "pre-existing independent closure. No owner gate."
    ),
    "BLD-0040": (
        "Resume 2026-10-25: no probe dir survived the dead builder; both "
        "probes authored fresh. probe1 re-derives distribution "
        "(811+372+23+0+30+16=1252; 1305=1252+53; 46 weak rows all "
        "wrong_output_can_pass), requires NC1 both-states, and re-executes "
        "the discrimination live (exact assert red on wrong non-None value, "
        "no-crash assert green). probe2 re-grades 3 sampled weak rows from "
        "the live source ASTs (hooks/_shared/test_hookrun.py) and byte-"
        "compares the manifest. Census artifact + control fixtures are "
        "production-worktree files (oracle-census.json sha recorded in the "
        "receipt); absent here - surfaced as notes. Receipt keeps its "
        "pre-existing independent closure. No owner gate."
    ),
    "BLD-0042": (
        "Resume 2026-10-25: no probe dir survived the dead builder; both "
        "probes authored fresh. probe1 re-derives the partition (70+65+58+1+0"
        "=194; 135=70+65; 137=135+2 findings) with per-kind finding semantics "
        "(135 function/dataclass/constructor rows at 0 default-exercising "
        "callers; 2 cli rows unexercised-in-shipped-ci with empty "
        "ci_bare_invocations), condition_11 green, NEG both-states. probe2 "
        "re-verifies 3 sampled function-default findings in live source ASTs "
        "(platform/lib/foundry/bench.py) + call-site lower bound + manifest "
        "byte-compare. census.json + raw outputs are production-worktree "
        "files; absent here - surfaced as notes. Receipt keeps its "
        "pre-existing independent closure. No owner gate."
    ),
}


def run_probe(uid: str, name: str) -> dict:
    path = REPO / "command-center" / "p2-wave" / "probes" / uid / name
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run(
        [sys.executable, "-B", str(path)],
        cwd=str(REPO), capture_output=True, text=True, timeout=2700, env=env,
    )
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return {
        "id": name.replace(".py", ""),
        "name": name,
        "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B "
                   f"command-center/p2-wave/probes/{uid}/{name}",
        "exit_code": r.returncode,
        "raw_output": out[:8000],
    }


def main() -> int:
    ids = sys.argv[1:] or list(PROBES)
    bad = []
    for uid in ids:
        names = PROBES[uid]
        results = []
        ok = True
        for name in names:
            res = run_probe(uid, name)
            results.append(res)
            if res["exit_code"] != 0:
                print(f"{uid} {name} rc={res['exit_code']}: "
                      f"{res['raw_output'][-300:]}")
                ok = False
                break
        if not ok:
            bad.append(uid)
            continue
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        supporting = [(pdir / n, "supporting") for n in names]
        write_return(uid, results, NOTES[uid], supporting=supporting)

        m = subprocess.run(
            [sys.executable, "command-center/p2-wave/_measure_one_delivered.py", uid],
            cwd=str(REPO), capture_output=True, text=True, timeout=2700,
        )
        tail = (m.stdout or "").strip().splitlines()[-1:] or [""]
        print(f"{uid}: measure rc={m.returncode} {tail[-1]}")
        if m.returncode != 0:
            bad.append(uid)
    if bad:
        print("NOT-GREEN:", ",".join(bad))
        return 1
    print("ALL-GREEN:", ",".join(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

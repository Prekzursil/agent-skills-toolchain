#!/usr/bin/env python3
"""AUD-0091 named probe 2: run `npm test` fresh in THIS in-place checkout
(pre-existing node_modules, pre-existing ~/.npm cache -- the opposite
conditions from probe1's clean room) and byte-compare the result against
probe1's clean-clone `npm test` result.

Purpose (catalog evidence_requirement): distinguish an ENVIRONMENT-ONLY
difference (e.g. a stale cache masking a real failure, or a flaky test)
from a genuine DOCUMENTATION defect. If the two runs produce the same
pass/fail/exit_code, whatever the clean-clone run measured is not an
artifact of missing local caches -- it is what the documented sequence
itself does.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT_JSON = HERE / "probe2-inplace-baseline-compare.json"
OUT_RAW = HERE / "probe2-inplace-baseline-compare.raw.txt"
PROBE1_JSON = HERE / "probe1-clean-clone-run.json"


def run_inplace_npm_test() -> dict:
    try:
        r = subprocess.run(
            ["npm", "test"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
        )
        combined = (r.stdout or "") + (r.stderr or "")
        summary = {"pass": None, "fail": None, "exit_code": r.returncode}
        # SUMMED across all workspaces, not overwritten by the last one --
        # npm --workspaces prints one "# pass N" / "# fail N" TAP summary
        # PER workspace (see probe1's same fix for why this matters).
        pass_total = 0
        fail_total = 0
        saw_any = False
        for line in combined.splitlines():
            line = line.strip()
            if line.startswith("# pass "):
                pass_total += int(line.split()[-1])
                saw_any = True
            elif line.startswith("# fail "):
                fail_total += int(line.split()[-1])
                saw_any = True
        if saw_any:
            summary["pass"] = pass_total
            summary["fail"] = fail_total
        return {
            "summary": summary,
            "stdout_tail": r.stdout[-8000:],
            "stderr_tail": r.stderr[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "summary": {
                "pass": None,
                "fail": None,
                "exit_code": None,
                "timed_out": True,
            },
            "stdout_tail": (exc.stdout or "")[-8000:] if exc.stdout else "",
            "stderr_tail": (exc.stderr or "")[-8000:] if exc.stderr else "",
        }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines = [
        "AUD-0091 NAMED PROBE 2: in-place npm test vs clean-clone npm test comparator",
        f"started_at={started}",
    ]

    probe1_available = PROBE1_JSON.is_file()
    clean_clone_summary = None
    if probe1_available:
        p1 = json.loads(PROBE1_JSON.read_text(encoding="utf-8"))
        clean_clone_summary = p1.get("npm_test_summary")
        raw_lines.append(
            f"clean_clone_npm_test_summary={json.dumps(clean_clone_summary)}"
        )
    else:
        raw_lines.append("probe1 JSON not found -- cannot compare")

    inplace = run_inplace_npm_test()
    raw_lines.append(f"inplace_npm_test_summary={json.dumps(inplace['summary'])}")
    raw_lines.append("---- in-place npm test stdout tail ----")
    raw_lines.append(inplace["stdout_tail"][-3000:])

    same_result = (
        probe1_available
        and clean_clone_summary is not None
        and clean_clone_summary.get("exit_code") == inplace["summary"].get("exit_code")
        and clean_clone_summary.get("pass") == inplace["summary"].get("pass")
        and clean_clone_summary.get("fail") == inplace["summary"].get("fail")
    )
    environment_only_diff = probe1_available and not same_result

    ok = probe1_available and inplace["summary"].get("exit_code") is not None

    doc = {
        "started_at": started,
        "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": ok,
        "probe1_available": probe1_available,
        "clean_clone_npm_test_summary": clean_clone_summary,
        "inplace_npm_test_summary": inplace["summary"],
        "results_identical": same_result,
        "environment_only_diff": environment_only_diff,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines.append(
        f"results_identical={same_result} environment_only_diff={environment_only_diff} ok={ok}"
    )
    raw_lines.append(f"{'SUCCESS' if ok else 'FAILED'}:AUD-0091-probe2")
    OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    print(f"unit=AUD-0091 probe2 results_identical={same_result} ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

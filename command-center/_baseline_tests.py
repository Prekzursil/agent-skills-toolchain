"""Run the repo's python test suites and record VERBATIM pass/fail counts.

Deviation from CI, disclosed: CI uses the venv `pytest` CONSOLE SCRIPT after a
`pip install -e`. This runner uses `python -m pytest` and performs NO installs,
because installing would mutate the shared interpreter. `-m pytest` prepends CWD
to sys.path, so it is a BROKEN DETECTOR for packaging/import-path regressions --
it measures TEST OUTCOMES only, not CI's packaging gate. Suites that cannot
import without an editable install are recorded NOT-CHECKED with the exact error.
"""
import json
import os
import re
import subprocess
import sys
import time

REPO = r"C:\Users\Prekzursil\source\ast-integrate"
PER_SUITE_TIMEOUT = 420

# (label, working_dir_relative_to_repo, pytest args list)
SUITES = [
    ("mcp-manager", "tools/mcp-manager", ["-q", "-p", "no:cacheprovider"]),
    ("scholarly-access-mcp", "tools/scholarly-access-mcp", ["-q", "-p", "no:cacheprovider"]),
    ("taskwatch_monitor", "tools/taskwatch_monitor", ["-q", "-p", "no:cacheprovider"]),
    ("monitorcore", "tools/monitorcore", ["-q", "-p", "no:cacheprovider"]),
    ("wfmon-adapter", "skills/workflow-monitor", ["tests/test_source.py", "-q", "-p", "no:cacheprovider"]),
    ("mcpctl", "tools/mcpctl", ["-q", "-p", "no:cacheprovider"]),
    ("mcpapply", "tools/mcpapply", ["-m", "not live", "-q", "-p", "no:cacheprovider"]),
    ("stdin-server", "tools/stdin-server", ["-q", "-p", "no:cacheprovider"]),
    ("harness-drift", "tools/harness-drift", ["-q", "-p", "no:cacheprovider"]),
    ("command-center", ".", ["tools/command-center/tests", "-q", "-p", "no:cacheprovider"]),
    ("agentspec", "tools/agentspec", ["-m", "not live", "-q", "-p", "no:cacheprovider"]),
    ("agentrail", "tools/agentrail", ["-m", "not live", "-q", "-p", "no:cacheprovider"]),
    ("agent-self-harness", ".", ["agent-self/harness/tests", "-q", "-p", "no:cacheprovider"]),
    ("cmd-rewrite-hooks", "hooks/cmd-rewrite",
     ["test_updated_input_preservation.py", "-q", "--import-mode=importlib", "-p", "no:cacheprovider"]),
    ("search-expansion", "tools/search-expansion", ["-q", "-p", "no:cacheprovider"]),
    ("program-b-register", ".", ["ci/tests/test_program_b_register.py", "-q", "-p", "no:cacheprovider"]),
    ("plugin-cache-reaper", "tools/plugin-cache-reaper", ["-q", "-p", "no:cacheprovider"]),
    ("emit-hook-manifest", ".", ["ci/tests/test_emit_hook_manifest.py", "-q", "-p", "no:cacheprovider"]),
    ("rules-scope", ".", ["ci/tests/test_rules_scope.py", "-q", "-p", "no:cacheprovider"]),
    ("plan-lint-stage0", ".", ["ci/tests/test_plan_lint_stage0.py", "-q", "-p", "no:cacheprovider"]),
    ("ci-tests-all", ".", ["ci/tests", "-q", "-p", "no:cacheprovider"]),
    ("crcp", "tools/crcp", ["tests", "-q", "-p", "no:cacheprovider"]),
    ("codex-dbx-fanout", "skills/codex-databricks-fanout/scripts",
     ["tests", "-q", "-p", "no:cacheprovider"]),
    ("workflow-authoring-lint", "skills/workflow-authoring/scripts", ["-q", "-p", "no:cacheprovider"]),
    ("git-hygiene", ".", ["hooks/git-hygiene/test_git_hygiene.py", "-q", "-p", "no:cacheprovider"]),
    ("hooks-regression", ".", ["hooks/", "-q", "--import-mode=importlib", "-p", "no:cacheprovider"]),
    ("harness-corpus", "tools/harness-corpus", ["-q", "-p", "no:cacheprovider"]),
    ("cloud-hub", "tools/mcp/cloud-hub", ["-q", "-p", "no:cacheprovider"]),
]

COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|error|errors|skipped|deselected|xfailed|xpassed|warning|warnings)"
)


def parse_counts(text):
    """Parse pytest's terminal summary line into a dict."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    tail = "\n".join(lines[-6:])
    counts = {}
    # Only trust the LAST summary-shaped line (pytest's final '=== N passed ===').
    for ln in reversed(lines):
        if ("passed" in ln or "failed" in ln or "error" in ln
                or "no tests ran" in ln.lower()):
            for n, kind in COUNT_RE.findall(ln):
                kind = kind.rstrip("s")
                counts[kind] = counts.get(kind, 0) + int(n)
            if counts or "no tests ran" in ln.lower():
                counts["_summary_line"] = ln.strip()
                break
    return counts, tail


def main():
    results = []
    t_all = time.time()
    for label, wd, args in SUITES:
        cwd = os.path.normpath(os.path.join(REPO, wd))
        cmd = [sys.executable, "-m", "pytest"] + args
        rec = {
            "label": label,
            "cwd": cwd.replace("\\", "/"),
            "command": " ".join(cmd),
            "cwd_exists": os.path.isdir(cwd),
        }
        if not rec["cwd_exists"]:
            rec["verdict"] = "NOT-CHECKED"
            rec["reason"] = "working directory does not exist"
            results.append(rec)
            continue
        t0 = time.time()
        try:
            p = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True,
                timeout=PER_SUITE_TIMEOUT, errors="replace",
            )
            out = (p.stdout or "") + (("\n[STDERR]\n" + p.stderr) if p.stderr else "")
            rec["exit_code"] = p.returncode
            counts, tail = parse_counts(out)
            rec["counts"] = counts
            rec["verbatim_tail"] = tail
            if p.returncode == 0:
                rec["verdict"] = "PASS"
            elif p.returncode == 5:
                rec["verdict"] = "NO-TESTS-COLLECTED"
            elif "ModuleNotFoundError" in out or "ImportError while loading conftest" in out:
                rec["verdict"] = "NOT-CHECKED"
                rec["reason"] = "import failure (needs editable install); see verbatim_tail"
            else:
                rec["verdict"] = "FAIL"
        except subprocess.TimeoutExpired:
            rec["exit_code"] = None
            rec["verdict"] = "NOT-CHECKED"
            rec["reason"] = "timeout after %ss" % PER_SUITE_TIMEOUT
        rec["seconds"] = round(time.time() - t0, 1)
        results.append(rec)
        print("[%s] %s exit=%s %s" % (
            rec["verdict"], label, rec.get("exit_code"),
            rec.get("counts", {}).get("_summary_line", rec.get("reason", ""))),
            flush=True)

    agg = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "deselected": 0}
    for r in results:
        for k in agg:
            agg[k] += r.get("counts", {}).get(k, 0)
    out = {
        "runner_note": __doc__.strip(),
        "python": sys.version,
        "total_seconds": round(time.time() - t_all, 1),
        "suite_count": len(results),
        "verdict_tally": {
            v: sum(1 for r in results if r["verdict"] == v)
            for v in sorted({r["verdict"] for r in results})
        },
        "aggregate_test_counts": agg,
        "suites": results,
    }
    with open(os.path.join(REPO, "command-center", "_baseline_tests_out.json"),
              "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("\nTALLY:", json.dumps(out["verdict_tally"]))
    print("AGG:", json.dumps(agg))


if __name__ == "__main__":
    main()

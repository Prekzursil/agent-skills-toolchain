#!/usr/bin/env python3
r"""B3: prove the gate's test suite can go RED. A green suite is not evidence until it has.

single-signal-verification 3b: before a probe's silence counts as "fixed", run it against the
KNOWN-BROKEN state and confirm it FIRES. Applied to a test suite that discipline is mutation
testing -- and this repo has already measured a suite that stayed green through a reverted bug,
because every test passed the parameter explicitly and the default was never exercised.

Each mutation below re-introduces a defect that was ACTUALLY made while building
`hook_predeploy_gate.py` (or by one of its four ancestor probes). A mutation the suite fails to
catch is a hole in the tests, reported as SURVIVED.

Method: copy the gate, its test file and the vendor-constants module into a temp dir, apply one
textual mutation to the copy, run pytest there. Nothing in the real tree is modified.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "hook_predeploy_gate.py"
TESTS = HERE / "test_hook_predeploy_gate.py"
VENDOR = HERE / "_g5_vendorcaps.py"
OUT = HERE / "B3-MUTATION.json"

#: (id, why it matters, old, new). `old` must appear EXACTLY once in the gate, else the mutation
#: is ambiguous and the run reports NOT-APPLIED rather than a misleading SURVIVED/CAUGHT.
MUTATIONS = [
    (
        "M1-manifest-dict-keys",
        "read the event DICT instead of its checks list -- the false parity that survived four probes",
        'items = node if isinstance(node, list) else (node.get("checks") or [])',
        'items = node if isinstance(node, list) else [{"name": k} for k in node]',
    ),
    (
        "M2-direction-loses-live",
        "call a file with live-only content REPO-AHEAD -- the exact data-loss direction of C4",
        'if not live_only:\n        return "REPO-AHEAD"',
        'if not repo_only:\n        return "REPO-AHEAD"',
    ),
    (
        "M3-regex-as-path",
        "classify a regex as a lost PATH by testing path-ness first",
        "    if _REGEX_META.search(value):\n        return f\"RE:{value[:80]}\" if len(value) >= 12 else \"\"\n",
        "",
    ),
    (
        "M4-wired-not-hazard",
        "downgrade a wired live hook from HAZARD to WARN",
        'return "HAZARD", "WIRED LIVE -- the live harness runs this file today"',
        'return "WARN", "WIRED LIVE -- the live harness runs this file today"',
    ),
    (
        "M5-control-always-true",
        "make the plausibility control unfalsifiable, so an unreadable live tree reports clean",
        'isinstance(found, int) and found >= MIN_PLAUSIBLE_CHECKS',
        'True',
    ),
    (
        "M6-command-leaks-full-line",
        "return the whole command line, which can carry a token in an env prefix",
        '            return os.path.basename(posix)\n    return os.path.basename(tokens[-1].replace("\\\\", "/")) if tokens else ""',
        '            return os.path.basename(posix)\n    return command',
    ),
    (
        "M7-settings-reads-everything",
        "return the whole settings document instead of only its hooks subtree",
        '    doc = json.loads(path.read_text(encoding="utf-8"))\n    out: dict[str, list[dict]] = {}',
        '    doc = json.loads(path.read_text(encoding="utf-8"))\n    out: dict[str, list[dict]] = {"_leak": [doc]}',
    ),
    (
        "M8-if-lint-inverted",
        "fire the `if` lint on tool events and stay silent on the events where `if` is inert",
        "if event in vendor.IF_EVALUATED_EVENTS:",
        "if event not in vendor.IF_EVALUATED_EVENTS:",
    ),
    # The first version of this case dropped the `.replace("\r\n", "\n")` in `sig_lines` and
    # SURVIVED. That was not a hole in the tests: `rstrip()` on the next line already removes the
    # trailing CR, so the replace is redundant and the mutant is EQUIVALENT -- measured directly,
    # both variants return identical line sets for CRLF and LF input. Reporting an equivalent
    # mutant as a test hole would have sent the next reader to patch tests that are already
    # correct, so the case was re-pointed at `rstrip`, which genuinely carries the behaviour.
    (
        "M9-crlf-counted-as-drift",
        "drop the rstrip, so trailing whitespace reads as drift and floods the report",
        "        stripped = raw.rstrip()",
        "        stripped = raw",
    ),
    (
        "M11-promise-config-only",
        "raise a promise hazard from the config signal alone -- the event-ledger false positive",
        "            age = age_of(root)\n            if age is None:",
        "            age = None\n            if age is None:",
    ),
    (
        "M12-file-artifact-reads-absent",
        "walk a FILE artifact, which yields nothing and reports an existing file as absent",
        "    if base.is_file():",
        "    if False:",
    ),
    (
        "M10-wiredness-union",
        "take wiredness from both trees, so the gate asserts the live harness runs an undeployed file",
        "    axis_manifest(report)  # emits the manifest findings; its own union is not the live set\n    live: set[str] = set()",
        "    live: set[str] = axis_manifest(report)",
    ),
]


def run_case(mutation_id: str, old: str, new: str) -> dict:
    source = GATE.read_text(encoding="utf-8")
    occurrences = source.count(old)
    if occurrences != 1:
        return {"id": mutation_id, "outcome": "NOT-APPLIED",
                "detail": f"anchor appears {occurrences} times, expected exactly 1"}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copy2(VENDOR, work / VENDOR.name)
        shutil.copy2(TESTS, work / TESTS.name)
        (work / GATE.name).write_text(source.replace(old, new), encoding="utf-8", newline="")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(work / TESTS.name), "-q", "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=work, timeout=300,
        )
    caught = proc.returncode != 0
    tail = [ln for ln in proc.stdout.splitlines() if ln.strip()][-1:] or ["<no output>"]
    return {"id": mutation_id, "outcome": "CAUGHT" if caught else "SURVIVED",
            "returncode": proc.returncode, "tail": tail[0][:160]}


def main() -> int:
    baseline = subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS), "-q", "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=HERE, timeout=300,
    )
    if baseline.returncode != 0:
        print("FAILED:b3-mutation baseline suite is already red -- fix that first")
        print(baseline.stdout[-2000:])
        return 2

    rows = [dict(run_case(mid, old, new), why=why) for mid, why, old, new in MUTATIONS]
    survived = [r for r in rows if r["outcome"] == "SURVIVED"]
    unapplied = [r for r in rows if r["outcome"] == "NOT-APPLIED"]
    result = {
        "baseline": "green",
        "mutations": len(rows),
        "caught": sum(1 for r in rows if r["outcome"] == "CAUGHT"),
        "survived": len(survived),
        "not_applied": len(unapplied),
        "rows": rows,
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
    for row in rows:
        print(f"  {row['outcome']:<11} {row['id']:<28} {row['why']}")
    if unapplied:
        print(f"FAILED:b3-mutation {len(unapplied)} mutation(s) could not be applied")
        return 2
    if survived:
        print(f"FAILED:b3-mutation {len(survived)} mutation(s) SURVIVED -- the tests have a hole")
        return 1
    print(f"SUCCESS:b3-mutation {len(rows)}/{len(rows)} mutations caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

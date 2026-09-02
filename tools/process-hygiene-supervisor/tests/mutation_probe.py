"""Mutation probe: revert each safety rule in turn; the suite MUST go red.

A green suite after a reverted guard is a suite that does not protect the
behaviour it claims to (the both-states rule). Each mutation below re-introduces
a leak or a hazard the 02.09.2026 measurement or the estate incidents already
paid for.

Run: ``python tests/mutation_probe.py hygiene.py`` (exit 0 = every mutation killed).
"""

import pathlib
import subprocess
import sys

TARGET = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "hygiene.py").resolve()
ORIGINAL = TARGET.read_text(encoding="utf-8")

MUTATIONS = [
    (
        "orphan reaps active processes (drop the whole-tree-idle gate)",
        "            if not self._all_idle(tree, observations):\n                continue",
        "            if False:\n                continue",
    ),
    (
        "protected allowlist disabled (auth2api / daemons / Windows get reaped)",
        'return any(token in haystack for token in self.policy["protected"]["tokens"])',
        "return False",
    ),
    (
        "cursor-agent orphans reaped directly instead of via the reaper",
        "            if self._is_parentless(proc, snapshot):\n                for pid in self._descendants(proc.pid, snapshot):",
        "            if False:\n                for pid in self._descendants(proc.pid, snapshot):",
    ),
    (
        "singleton port owner is killed instead of kept",
        "                if pid == keeper or pid in claimed:",
        "                if pid in claimed:",
    ),
    (
        "orphan age gate dropped (a just-detached process is reaped immediately)",
        "            if snapshot.taken_unix - proc.created_unix < min_age:\n                continue",
        "            if False:\n                continue",
    ),
    (
        "apply ignores the tier gate (elevated/critical actions fire at normal)",
        '        elif not gate_ok:\n            planned, deferred = "deferred", deferred + 1',
        '        elif False:\n            planned, deferred = "deferred", deferred + 1',
    ),
]

failures = []
try:
    for label, old, new in MUTATIONS:
        if old not in ORIGINAL:
            failures.append(f"ANCHOR-MISS: {label!r} -- pattern not found")
            print(f"[ANCHOR-MISS] {label}")
            continue
        TARGET.write_text(ORIGINAL.replace(old, new, 1), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header", "-x"],
            cwd=TARGET.parent,
            capture_output=True,
            text=True,
        )
        killed = proc.returncode != 0
        print(f"[{'KILLED ' if killed else 'SURVIVED'}] {label}")
        if not killed:
            failures.append(f"SURVIVED: {label}")
finally:
    TARGET.write_text(ORIGINAL, encoding="utf-8")

print()
if failures:
    print("MUTATION PROBE FAILED:")
    for line in failures:
        print("  -", line)
    raise SystemExit(1)
print(f"MUTATION PROBE PASSED: all {len(MUTATIONS)} mutations killed by the suite")

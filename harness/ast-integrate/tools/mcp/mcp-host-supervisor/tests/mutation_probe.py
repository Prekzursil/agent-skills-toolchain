"""Mutation probe: revert each safety rule in turn; the suite MUST go red.

A suite that stays green is not protecting the behaviour it claims to protect
(the both-states rule). Each mutation below re-introduces a failure this estate
actually suffered.
"""

import pathlib
import subprocess
import sys

TARGET = pathlib.Path(sys.argv[1])
ORIGINAL = TARGET.read_text(encoding="utf-8")

MUTATIONS = [
    (
        "AND-gate -> CPU only (a busy-but-unanswering host gets killed)",
        "    if cpu_advanced or requests_advanced:",
        "    if cpu_advanced:",
    ),
    (
        "drop the startup grace (kills cold-starting children, the agent-mail bug)",
        '    if current.uptime_sec < startup_grace_sec:\n        return "STARTING"',
        '    if False:\n        return "STARTING"',
    ),
    (
        "machine-wide reap (kills sibling sessions' MCP children)",
        "        if ppid == supervisor_pid or ppid not in live_pids:",
        "        if True:",
    ),
    (
        "allow reserved ports (would bind over live basic-memory / agent-mail)",
        "        owner = RESERVED_PORTS.get(spec.port)",
        "        owner = None",
    ),
    (
        "accept an empty reap signature (matches every process on the box)",
        "    if not signature or not signature.strip():",
        "    if False:",
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
        tag = "KILLED " if killed else "SURVIVED"
        print(f"[{tag}] {label}")
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

"""Mutation probe: revert each safety rule in turn; the suite MUST go red.

A suite that stays green after a reverted guard is not protecting the behaviour it
claims to (the both-states rule). Each mutation re-introduces a leak or a hazard
the 02.09.2026 measurement or the estate incidents already paid for. Mutations
may target any module in the tool (``file`` field); the probe restores every
file it touched even if pytest crashes.

Run from the tool root: ``python tests/mutation_probe.py``
(a legacy positional target path is accepted and ignored for compatibility).
Exit 0 = every mutation killed.
"""

import pathlib
import subprocess
import sys

TOOL_ROOT = pathlib.Path(__file__).resolve().parents[1]

# (label, file, old, new)
MUTATIONS = [
    (
        "orphan reaps active processes (drop the whole-tree-idle gate)",
        "hygiene.py",
        "            if not self._all_idle(tree, observations):\n                continue",
        "            if False:\n                continue",
    ),
    (
        "protected allowlist disabled (auth2api / daemons / Windows get reaped)",
        "hygiene.py",
        'return any(token in haystack for token in self.policy["protected"]["tokens"])',
        "return False",
    ),
    (
        "cursor-agent orphans reaped directly instead of via the reaper",
        "hygiene.py",
        "            if self._is_parentless(proc, snapshot):\n                for pid in self._descendants(proc.pid, snapshot):",
        "            if False:\n                for pid in self._descendants(proc.pid, snapshot):",
    ),
    (
        "singleton port owner is killed instead of kept",
        "hygiene.py",
        "                if pid == keeper or pid in claimed:",
        "                if pid in claimed:",
    ),
    (
        "orphan age gate dropped (a just-detached process is reaped immediately)",
        "hygiene.py",
        "            if snapshot.taken_unix - proc.created_unix < min_age:\n                continue",
        "            if False:\n                continue",
    ),
    (
        "apply ignores the tier gate (elevated/critical actions fire at normal)",
        "hygiene.py",
        '        elif not gate_ok:\n            planned, deferred = "deferred", deferred + 1',
        '        elif False:\n            planned, deferred = "deferred", deferred + 1',
    ),
    (
        "empty-executable fail-closed removed (unidentifiable processes become killable)",
        "hygiene.py",
        "        if not proc.executable:\n            return True",
        "        if False:\n            return True",
    ),
    (
        "PID-reuse child-predates-parent guard dropped",
        "hygiene.py",
        "                if snapshot.by_pid[child].created_unix < parent_created:\n                    continue",
        "                if False:\n                    continue",
    ),
    (
        "tier de-escalates immediately (hysteresis dropped)",
        "hygiene.py",
        '        if streak >= self.policy["pressure"]["deescalate"]:',
        "        if True:",
    ),
    (
        "IDE-owned agent treated as a stale session",
        "hygiene.py",
        "            if current.name.lower() in IDE_NAMES:",
        "            if False:",
    ),
    (
        "orphan rule ignores reaper delegation (delegated cursor reaped inline)",
        "hygiene.py",
        "            if proc.pid in claimed or proc.pid in delegate_pids:",
        "            if proc.pid in claimed:",
    ),
    (
        "actuator kills without identity revalidation",
        "hygiene_actuate.py",
        "        if not self._identity_matches(member, identity):",
        "        if False:",
    ),
    (
        "actuator skips graceful stop and goes straight to /F",
        "hygiene_actuate.py",
        "        if graceful_seconds > 0:",
        "        if False:",
    ),
    (
        "singleton grace dropped (a warming relaunch is killed)",
        "hygiene.py",
        "                if snapshot.taken_unix - proc.created_unix <= grace:",
        "                if False:",
    ),
    (
        "daemon carve-out dropped (port-owning orphans reaped)",
        "hygiene.py",
        "            if owned_port is not None:",
        "            if False:",
    ),
    (
        "protected members pulled into kill trees",
        "hygiene.py",
        "            if self._is_protected(proc, snapshot):\n                protected.append(pid)",
        "            if False:\n                protected.append(pid)",
    ),
]

originals: dict[pathlib.Path, str] = {}
failures = []
try:
    for label, filename, old, new in MUTATIONS:
        target = TOOL_ROOT / filename
        original = originals.setdefault(target, target.read_text(encoding="utf-8"))
        if old not in original:
            failures.append(
                f"ANCHOR-MISS: {label!r} -- pattern not found in {filename}"
            )
            print(f"[ANCHOR-MISS] {label}")
            continue
        target.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header", "-x"],
                cwd=TOOL_ROOT,
                capture_output=True,
                text=True,
            )
        finally:
            target.write_text(original, encoding="utf-8")
        killed = proc.returncode != 0
        print(f"[{'KILLED ' if killed else 'SURVIVED'}] {label}")
        if not killed:
            failures.append(f"SURVIVED: {label}")
finally:
    for target, original in originals.items():
        target.write_text(original, encoding="utf-8")

print()
if failures:
    print("MUTATION PROBE FAILED:")
    for line in failures:
        print("  -", line)
    raise SystemExit(1)
print(f"MUTATION PROBE PASSED: all {len(MUTATIONS)} mutations killed by the suite")

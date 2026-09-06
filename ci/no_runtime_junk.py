#!/usr/bin/env python3
"""Fail if git tracks runtime junk or nested estate dumps.

Extracted from .github/workflows/no-runtime-junk.yml so the rule can be
run locally and covered by a both-states self-test. The workflow is a
thin caller of this module.

Banned:
  - directory segments: .venv, venv, node_modules, __pycache__, caches
  - basenames: installed.json (harness install manifest)
  - path prefixes: harness/ast-integrate/  (nested full-estate dump;
    measured in PRs #316/#319 at ~45k files / +14M lines)
  - gitlinks (mode 160000)
"""
from __future__ import annotations

import subprocess
import sys

BAD_DIR_SEGMENTS = {
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
BAD_BASENAMES = {"installed.json"}
# Full-repo checkouts accidentally committed under harness/ (PRs #316/#319).
BAD_PATH_PREFIXES = ("harness/ast-integrate/",)


def tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "-z"])
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def gitlinks() -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "-s", "-z"])
    found: list[str] = []
    for rec in out.decode("utf-8", "replace").split("\0"):
        if not rec:
            continue
        meta, _, path = rec.partition("\t")
        if meta.split(" ", 1)[0] == "160000":
            found.append(path)
    return found


def find_violations(paths: list[str], links: list[str]) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for path in paths:
        segments = path.split("/")
        if BAD_DIR_SEGMENTS.intersection(segments):
            violations.append(("runtime-dir", path))
        elif segments[-1] in BAD_BASENAMES:
            violations.append(("runtime-file", path))
        elif any(path.startswith(prefix) for prefix in BAD_PATH_PREFIXES):
            violations.append(("nested-estate-dump", path))
    for path in links:
        violations.append(("nested-git-gitlink", path))
    return violations


def self_test() -> int:
    """Both-states control: clean fixture silent, poisoned fixture fires."""
    clean = find_violations(["docs/README.md", "ci/no_runtime_junk.py"], [])
    if clean:
        print(f"FAIL:self-test clean fixture produced {clean}")
        return 1
    poisoned_paths = [
        "harness/ast-integrate/README.md",
        "foo/node_modules/x",
        "hooks/installed.json",
    ]
    poisoned_links = ["vendor/nested-repo"]
    hits = find_violations(poisoned_paths, poisoned_links)
    kinds = {k for k, _ in hits}
    expected = {"nested-estate-dump", "runtime-dir", "runtime-file", "nested-git-gitlink"}
    if kinds != expected:
        print(f"FAIL:self-test kinds={kinds} want={expected} hits={hits}")
        return 1
    # Control: a path that merely mentions the banned name as a filename suffix must NOT fire.
    control = find_violations(["docs/notes-on-ast-integrate.md"], [])
    if control:
        print(f"FAIL:self-test over-match on suffix-only path: {control}")
        return 1
    print("SUCCESS:no-runtime-junk self-test 4/4 poisoned kinds fired, clean+suffix controls silent")
    return 0


def main(argv: list[str]) -> int:
    if argv[1:] == ["--self-test"]:
        return self_test()
    violations = find_violations(tracked_files(), gitlinks())
    if violations:
        print("Tracked runtime junk detected (must be gitignored / removed):")
        for kind, path in sorted(violations):
            print(f"  [{kind}] {path}")
        return 1
    print("OK: no tracked runtime junk.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

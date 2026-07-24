"""Both-states probe: does the test suite actually FIRE on known-broken code?

A green suite proves nothing until each real behaviour has been reverted and the
suite has been observed going RED. Every mutation below is a bug that was either
actually written during development or is the obvious naive implementation.

Run:  python mutation_probe.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = HERE / "browser_rail.py"
TESTS = HERE / "test_browser_rail.py"

# (name, original snippet, mutated snippet)
MUTATIONS: list[tuple[str, str, str]] = [
    (
        "M1 domain_matches -> naive substring",
        'return host == target or host.endswith(f".{target}")',
        "return target in page_url",
    ),
    (
        "M2 normalize_domain -> always prepend '//' (the about:blank bug)",
        '    if "://" in raw:\n        host = urlsplit(raw).hostname or ""',
        '    if True:\n        host = urlsplit(raw if "//" in raw else f"//{raw}").hostname or ""',
    ),
    (
        "M3 classify_auth -> check logged-IN before logged-OUT (bias flipped)",
        'hit = _first_containing(joined, signals.logged_out_names)\n    if hit is not None:\n        return AuthVerdict(False, "logged-out-control", hit)',
        'hit = _first_containing(joined, signals.logged_in_names)\n    if hit is not None:\n        return AuthVerdict(True, "logged-in-control", hit)',
    ),
    (
        "M4 both_states_ready -> OR instead of AND (one direction passes)",
        "return has_out and bool(self.logged_in_names)",
        "return has_out or bool(self.logged_in_names)",
    ),
    (
        "M5 assert_payload_not_inlined -> guard disabled",
        "if len(text) >= MIN_SCANNED_PAYLOAD_LEN and text in js_source:",
        "if False and text in js_source:",
    ),
    (
        "M6 classify_auth -> UNKNOWN collapsed into False",
        'return AuthVerdict(None, "no-signal-fired", "")',
        'return AuthVerdict(False, "no-signal-fired", "")',
    ),
]


def run_suite(workdir: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "test_browser_rail.py", "-q", "--no-header"],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip().splitlines()[-1]


def main() -> int:
    source = MODULE.read_text(encoding="utf-8")
    survivors: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copy2(TESTS, work / TESTS.name)

        # Baseline: the suite must be GREEN before any mutation is meaningful.
        (work / MODULE.name).write_text(source, encoding="utf-8")
        code, tail = run_suite(work)
        print(f"[baseline] rc={code} {tail}")
        if code != 0:
            print("FAILED:mutation-probe baseline suite is not green")
            return 1

        for name, original, mutated in MUTATIONS:
            if original not in source:
                print(f"[{name}] ANCHOR NOT FOUND -- probe is broken, not the code")
                survivors.append(f"{name} (anchor missing)")
                continue
            (work / MODULE.name).write_text(
                source.replace(original, mutated, 1), encoding="utf-8"
            )
            code, tail = run_suite(work)
            verdict = "RED (caught)" if code != 0 else "GREEN (SURVIVED)"
            print(f"[{name}] rc={code} -> {verdict} :: {tail}")
            if code == 0:
                survivors.append(name)

    print()
    if survivors:
        print(f"FAILED:mutation-probe {len(survivors)} mutation(s) survived:")
        for item in survivors:
            print(f"  - {item}")
        return 1
    print(f"SUCCESS:mutation-probe all {len(MUTATIONS)} mutations caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

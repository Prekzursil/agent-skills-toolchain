#!/usr/bin/env python3
"""TST-0338 probe2: two-project isolation and dead-command control.

Mechanically independent of probe1: rebuilds its OWN scratch copy of the
two-project fixture tree, then proves a command transplanted from alpha is
DEAD in beta (never touches beta marker), that markers never cross, and
that the resolver carries no default/hardcoded command.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
from coverage_resolver import THRESHOLDS_NAME, executable_command, resolve_project  # noqa: E402

SENTINEL = "SUCCESS:TST-0338-probe2"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0338.json"


def fail(msg):
    print("FAILED:TST-0338-probe2 " + msg)
    return 1


def rebuild_tree(root):
    """Fresh two-project tree authored by THIS probe, not copied from probe1."""
    (root / "project-alpha").mkdir(parents=True)
    (root / "project-beta").mkdir(parents=True)
    (root / "project-alpha" / THRESHOLDS_NAME).write_text(
        json.dumps({"thresholds": {"lines": 80, "branches": 70},
                    "enforcement": {"command": "python3 -B gate_alpha.py"}}),
        encoding="utf-8")
    (root / "project-beta" / THRESHOLDS_NAME).write_text(
        json.dumps({"thresholds": {"lines": 50, "branches": 40},
                    "enforcement": {"command": "python3 -B gate_beta.py"}}),
        encoding="utf-8")
    (root / "project-alpha" / "gate_alpha.py").write_text(
        "import pathlib\n"
        "pathlib.Path('alpha-marker.txt').write_text('x', encoding='utf-8')\n",
        encoding="utf-8")
    (root / "project-beta" / "gate_beta.py").write_text(
        "import pathlib\n"
        "pathlib.Path('beta-marker.txt').write_text('x', encoding='utf-8')\n"
        "raise SystemExit(3)\n",
        encoding="utf-8")


def main():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="tst0338-probe2-") as tmp:
        root = Path(tmp) / "two-project"
        rebuild_tree(root)
        alpha = root / "project-alpha"
        beta = root / "project-beta"

        ra = resolve_project(alpha)
        rb = resolve_project(beta)
        checks = [
            ("alpha-ran-0", ra["exit_code"] == 0 and bool(ra["enforcement_ran"])),
            ("beta-ran-3", rb["exit_code"] == 3 and bool(rb["enforcement_ran"])),
            ("commands-differ", ra["declared_command"] != rb["declared_command"]),
            ("exit-codes-differ", ra["exit_code"] != rb["exit_code"]),
            ("alpha-marker-in-alpha", (alpha / "alpha-marker.txt").is_file()),
            ("beta-marker-in-beta", (beta / "beta-marker.txt").is_file()),
            ("alpha-marker-NOT-in-beta", not (beta / "alpha-marker.txt").exists()),
            ("beta-marker-NOT-in-alpha", not (alpha / "beta-marker.txt").exists()),
        ]

        # Wrong-project control: transplant alpha declared command into beta
        # root. The gate script is absent there, so the interpreter cannot
        # open the file (exit 2) and beta marker state must be untouched.
        executed = executable_command(ra["declared_command"])
        dead = subprocess.run(executed, cwd=str(beta), shell=True,
                              capture_output=True, text=True, timeout=120)
        checks += [
            ("transplant-dead-exit2", dead.returncode == 2),
            ("transplant-marker-absent", not (beta / "alpha-marker.txt").exists()),
            ("transplant-no-beta-touch", (beta / "beta-marker.txt").is_file()),
        ]

    src = (PROBE_DIR / "coverage_resolver.py").read_text(encoding="utf-8")
    checks += [
        ("resolver-absent-is-not-checked", "NOT-CHECKED" in src),
        ("resolver-no-hardcoded-gate", ("gate_alpha" not in src) and ("gate_beta" not in src)),
        ("resolver-declared-verbatim", "declared_command(project)" in src),
    ]

    iso = receipt["fixture_proof"]["isolation"]
    checks += [
        ("receipt-transplant-dead", iso["transplant_alpha_command_into_beta"]["dead"] is True),
        ("receipt-commands-differ", iso["commands_differ"] is True),
        ("receipt-resolver-no-default", iso["resolver_has_no_default_command"] is True),
    ]

    for name, ok in checks:
        print(("  ok " if ok else "  RED ") + name)
        if not ok:
            return fail("check " + name + " RED")
    print(json.dumps({
        "probe": "probe2-wrong-project", "unit_id": "TST-0338", "pass": True,
        "alpha_exit": 0, "beta_exit": 3, "transplant_exit": dead.returncode,
        "transplant_dead": True,
    }))
    print(SENTINEL + " wrong-project transplant is dead (exit 2); markers never cross; resolver has no default command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

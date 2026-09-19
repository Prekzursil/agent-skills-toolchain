#!/usr/bin/env python3
"""P2 cloud-loop recipe dispatcher. One entry point; recipes as code.

apply_recipe.py <gate>          -> applies the known recipe, verifies locally,
                                   exit 0 only on verified green.
Known signatures only. An unknown failure signature exits 3 (UNRESOLVED) so
cloud_loop.py reports it instead of guessing. Recipes are the session-proven
ones from 2026-09-19 (see FIXPLAYBOOK.json provenance notes).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNRESOLVED = 3


def run(cmd: list[str] | str, shell: bool = False) -> tuple[int, str]:
    p = subprocess.run(
        cmd if not shell else cmd, cwd=ROOT, capture_output=True, text=True, shell=shell
    )
    return p.returncode, (p.stdout + p.stderr)


def verified(cmd: str) -> bool:
    rc, out = run(cmd, shell=True)
    print(out[-1500:])
    return rc == 0


def regen_render() -> int:
    run("python tools/command-center/render.py", shell=True)
    return (
        0 if verified("python tools/command-center/render.py --check") else UNRESOLVED
    )


def regen_manifest() -> int:
    run("python tools/command-center/unit_manifest.py --write", shell=True)
    return (
        0
        if verified("python tools/command-center/unit_manifest.py --check")
        else UNRESOLVED
    )


def ruff_all() -> int:
    run("uvx ruff@0.15.17 check --fix --quiet .", shell=True)
    run("uvx ruff@0.15.17 format --quiet .", shell=True)
    if not verified("uvx ruff@0.15.17 check ."):
        return UNRESOLVED
    return 0 if verified("uvx ruff@0.15.17 format --check .") else UNRESOLVED


def junk_untrack() -> int:
    rc, out = run("git ls-files", shell=True)
    bad = [
        p
        for p in out.splitlines()
        if re.search(
            r"(^|/)(node_modules|__pycache__|\.pytest_cache|\.ruff_cache|\.venv|venv)(/|$)",
            p,
        )
        or p.endswith("installed.json")
        or p.startswith(".worktrees/")
    ]
    if not bad:
        return 0 if _junkscan_clean() else UNRESOLVED
    print(f"untracking {len(bad)} paths (plain staged-index commit)")
    rc, _ = run(["git", "rm", "-r", "-q", "--cached", *bad])
    return 0 if rc == 0 else UNRESOLVED


def _junkscan_clean() -> bool:
    rc, out = run("git ls-files -s", shell=True)
    return not any(ln.startswith("160000") for ln in out.splitlines())


def quality_layers() -> int:
    """Run the command-center step battery in CI order; apply known sub-recipes."""
    battery = [
        ("install", "pip install pytest numpy jsonschema --quiet"),
        ("pytest-cc", "python -m pytest tools/command-center/tests -q"),
        ("validate", "python tools/command-center/validate.py --require-complete"),
        ("render", "python tools/command-center/render.py --check"),
        ("casualty", "python -m pytest command-center/casualty/tests -q"),
        ("casualty-guard", "python command-center/casualty/casualty_guard.py"),
        ("measure-pytest", "python -m pytest tools/measure-guard/tests -q"),
        (
            "suitefloor-cc",
            "python tools/measure-guard/suitefloor.py --suite command-center",
        ),
        ("suitefloor-cas", "python tools/measure-guard/suitefloor.py --suite casualty"),
        ("refcheck", "python tools/measure-guard/refcheck.py"),
        ("wudeps", "python tools/measure-guard/wudeps.py"),
        ("jsonparse", "python tools/measure-guard/jsonparse.py"),
        ("receipt-gate", "python command-center/receipt_ci_gate.py"),
        ("unitgate", "python tools/measure-guard/unitgate.py"),
    ]
    for name, cmd in battery:
        rc, out = run(cmd, shell=True)
        if rc != 0:
            print(f"[layer {name}] FAILED:\n{out[-1200:]}", flush=True)
            if name == "render":
                return regen_render()
            if "unitgate" in name and "manifest" in out:
                return regen_manifest()
            return UNRESOLVED
        print(f"[layer {name}] ok", flush=True)
    return 0


def generic_probe(gate_cmd: str) -> int:
    return 0 if verified(gate_cmd) else UNRESOLVED


GATES: dict[str, callable] = {
    "gate-tests-coverage (python packages)": quality_layers,
    "gate-unit-artifact-manifest": regen_manifest,
    "gate-lint-format (ruff)": ruff_all,
    "gate-no-runtime-junk": junk_untrack,
    "gate-mcp-audit": lambda: generic_probe(
        "python command-center/mcp-audit/ci_gate.py"
    ),
    "gate-interpreter-floor": lambda: generic_probe(
        "python command-center/ci/interpreter_floor_gate.py"
    ),
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_recipe.py <gate>")
        return 2
    gate = sys.argv[1]
    fn = GATES.get(gate)
    if fn is None:
        print(f"UNRESOLVED: no recipe for {gate}")
        return UNRESOLVED
    return fn()


if __name__ == "__main__":
    sys.exit(main())

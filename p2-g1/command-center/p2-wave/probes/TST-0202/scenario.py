"""TST-0202 scenario: a junction alias whose RESOLVED length exceeds the budget.

Builds, under this probe dir:
  deep/alias-target/a<40>/b<40>/...   resolved length > WINDOWS_MAX_PATH (260)
  alias -> junction to deep/alias-target

Both probe scripts import :func:`build` and exercise the production writer in
tools/command-center/artifact_writer.py through the alias and through the
direct (non-alias) deep path.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

SCENARIO = HERE / "fixtures" / "scenario"


def _deep_root() -> Path:
    root = SCENARIO / "deep" / "alias-target"
    node = root
    component = "l" * 40
    for i in range(8):
        node = node / f"{component}{i}"
    return node


def build() -> dict:
    import ntpath

    if SCENARIO.exists():
        shutil.rmtree(SCENARIO)
    deep = _deep_root()
    deep.mkdir(parents=True, exist_ok=True)
    alias = SCENARIO / "alias"
    if sys.platform == "win32":
        cmd = ["cmd", "/c", "mklink", "/J", str(alias), str(deep)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"junction creation failed: {proc.stdout} {proc.stderr}")
    else:
        alias.symlink_to(deep, target_is_directory=True)
    alias_str = str(alias)
    resolved_str = str(alias_str)
    if sys.platform == "win32":
        resolved_str = ntpath.realpath(alias_str)
    else:
        import posixpath

        resolved_str = posixpath.realpath(alias_str)
    from artifact_writer import WINDOWS_MAX_PATH, resolved_length, alias_length

    return {
        "alias": alias,
        "deep": deep,
        "alias_len": alias_length(alias),
        "resolved_len": resolved_length(alias),
        "resolved_via_independent_api": resolved_str,
        "independent_len": len(resolved_str),
        "budget": WINDOWS_MAX_PATH,
        "over_budget": resolved_length(alias) > WINDOWS_MAX_PATH,
    }


def teardown() -> None:
    if SCENARIO.exists():
        shutil.rmtree(SCENARIO, ignore_errors=True)

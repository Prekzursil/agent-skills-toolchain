"""Both-states coverage for ci/no_runtime_junk.py (nest-dump ban)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "ci" / "no_runtime_junk.py"


def test_no_runtime_junk_self_test_both_states() -> None:
    """Poisoned fixtures must fire; clean + suffix-only controls must stay silent."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SUCCESS:no-runtime-junk self-test" in proc.stdout


def test_live_tree_has_no_ast_integrate_prefix() -> None:
    """Current index must not already carry the banned nest (control for the ban)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: no tracked runtime junk" in proc.stdout

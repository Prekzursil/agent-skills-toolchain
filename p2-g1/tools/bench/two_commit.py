"""Two-commit snapshot runner (TST-0313).

The oracle is EXECUTED against the snapshot subject (staged into a temp
subject root), so the outcome is derived from the snapshot's code and never
from which side is running it. Swapping the snapshots therefore inverts the
polarity of the pair (pre-side on the post snapshot PASSES, post-side on the
pre snapshot FAILS), which is the both-states control the closure gate is
built on. A text-scan shortcut cannot honour that control and was the defect
this runner exists to prevent.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

_ORACLE_TIMEOUT_S = 120


def _snapshot_files(snapshot: Path) -> list[Path]:
    if snapshot.is_file():
        return [snapshot]
    return sorted(p for p in snapshot.rglob("*") if p.is_file())


def _stage(snapshot: Path, subject_root: Path) -> None:
    """Copy the snapshot subject into a bare subject root."""
    for f in _snapshot_files(snapshot):
        rel = f.relative_to(snapshot) if snapshot.is_dir() else Path(f.name)
        dest = subject_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)


def run_oracle(
    case: dict[str, Any],
    side: str,
    ledger: Any,
    snapshot_override: str | Path | None = None,
) -> dict[str, Any]:
    key = "pre_snapshot" if side == "pre-fix" else "post_snapshot"
    if snapshot_override is not None:
        snap = Path(str(snapshot_override))
    else:
        snap = Path(str(case.get(key) or ""))
    oracle = str(case.get("oracle") or "")

    outcome: str | None = None
    executed = False
    if oracle and Path(oracle).is_file() and snap.exists():
        with tempfile.TemporaryDirectory(prefix="tst0313-stage-") as td:
            root = Path(td) / "subject"
            tmp = Path(td) / "oracle-tmp"
            root.mkdir()
            tmp.mkdir()
            _stage(snap, root)
            env = os.environ.copy()
            env["SUBJECT_ROOT"] = str(root)
            env["ORACLE_TMP"] = str(tmp)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            try:
                proc = subprocess.run(
                    [sys.executable, "-B", oracle],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=_ORACLE_TIMEOUT_S,
                )
                outcome = "PASS" if proc.returncode == 0 else "FAIL"
                executed = True
            except subprocess.TimeoutExpired:
                outcome = "FAIL"
                executed = True
    if outcome is None:
        # Fail-closed: an unrunnable oracle is a failing, non-executed run,
        # never a silent pass.
        outcome = "FAIL"

    row = {
        "run_id": f"run-{uuid4().hex[:12]}",
        "case_id": case.get("id"),
        "side": side,
        "outcome": outcome,
        "executed": executed,
        "commit": str(snap),
        "oracle": case.get("oracle"),
    }
    if hasattr(ledger, "append"):
        ledger.append(row)
    return row


def run_pair(case: dict[str, Any], ledger: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    pre = run_oracle(case, "pre-fix", ledger)
    post = run_oracle(case, "post-fix", ledger)
    return pre, post


__all__ = ["run_oracle", "run_pair"]

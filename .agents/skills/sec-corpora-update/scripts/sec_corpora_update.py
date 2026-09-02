#!/usr/bin/env python3
"""Refresh the local security-knowledge corpora (git pull --depth 1 each).

Cross-platform Python twin of ``sec-corpora-update.ps1``. Idempotent and
FAIL-OPEN per repo: each corpus is pulled inside its own try/except, a failure on
one repo never aborts the rest, and the script always exits 0. Shallow
(``--depth 1``) so the clones stay small. HackTricks is intentionally skipped
here - it is a sparse, nested (``hacktricks/`` + ``hacktricks-cloud/``) checkout
refreshed by its own ``htk_update.ps1``.

The corpus list is kept in sync with ``sec-corpora-update.ps1``; the test suite
(``tests/test_sec_corpora_update.py``) asserts the two lists match. This script
only refreshes clones that already exist under ``--root``; it never clones, and a
directory without a ``.git`` is reported ``SKIP``, not fetched.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

CORPORA: tuple[str, ...] = (
    "payloadsallthethings",
    "gtfobins",
    "lolbas",
    "owasp-wstg",
    "owasp-cheatsheets",
    "atomic-red-team",
    # Added 2026-09-02 (W-corpus): blue / purple / CTI corpora.
    "seclists",
    "exploitdb",
    "attack-stix-data",
    "misp-galaxy",
    "misp-warninglists",
    "signature-base",
    "adversary-emulation-library",
    "control-validation-compass",
    "sysmon-modular",
    "loldrivers",
)


def _default_root() -> str:
    return os.environ.get("SEC_CORPORA_ROOT") or r"D:\knowledge"


def _last_line(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def update_corpora(root: str) -> tuple[int, int, int]:
    """Pull each corpus under ``root``; return (ok, failed, skipped) counts.

    Fail-open: any per-repo error is caught and reported, never raised.
    """
    os.environ["GIT_TERMINAL_PROMPT"] = "0"  # never block on credential prompts
    ok = fail = skip = 0
    for name in CORPORA:
        path = Path(root) / name
        if not (path / ".git").exists():
            print(f"SKIP   {name} (not a git clone at {path})")
            skip += 1
            continue
        try:
            proc = subprocess.run(
                ["git", "-C", str(path), "pull", "--depth", "1", "--no-edit"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = _last_line((proc.stdout or "") + (proc.stderr or ""))
            if proc.returncode == 0:
                print(f"OK     {name} : {out}")
                ok += 1
            else:
                print(f"FAILED {name} : {out}")
                fail += 1
        # Fail-open by contract: one repo (missing git, OSError, ...) never aborts the rest.
        except Exception as exc:
            print(f"FAILED {name} : {exc}")
            fail += 1
    print(
        f"sec-corpora-update done: ok={ok} failed={fail} skipped={skip} "
        "(HackTricks uses htk_update.ps1)"
    )
    return ok, fail, skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh the local security corpora (shallow, fail-open, exit 0)."
    )
    parser.add_argument(
        "--root",
        default=_default_root(),
        help="Corpora root directory (default: $SEC_CORPORA_ROOT or D:\\knowledge).",
    )
    args = parser.parse_args(argv)
    update_corpora(args.root)
    return 0  # always fail-open: the refresher never breaks a caller


if __name__ == "__main__":
    raise SystemExit(main())

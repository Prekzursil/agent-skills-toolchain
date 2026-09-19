#!/usr/bin/env python3
"""Ensure jsonschema is importable for TST-0329 condition-4 measurement.

Condition 4 of the shared completion predicate is NOT-CHECKED when jsonschema
is absent. A battery that claims healthy COMPLETE / independence without C4
being measurable is a false green (adversarial FAIL 2026-09-08).

This helper:
  1. Imports jsonschema if already present.
  2. Otherwise attempts a user-site pip install and prepends the user site.
  3. Exits non-zero if still unavailable (fail closed — never claim green).
"""

from __future__ import annotations

import importlib
import site
import subprocess
import sys


def _prepend_user_site() -> None:
    """Make a just-installed --user package importable even under python -s."""
    try:
        user_site = site.getusersitepackages()
    except Exception:
        return
    if user_site and user_site not in sys.path:
        sys.path.insert(0, user_site)


def ensure() -> str:
    """Return jsonschema version string; raise SystemExit if unavailable."""
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--break-system-packages",
            "--user",
            "jsonschema>=4.0",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(
                "TST-0329 requires jsonschema for condition 4; pip install failed:\n"
                + (proc.stdout or "")
                + (proc.stderr or "")
            )
        _prepend_user_site()
        importlib.invalidate_caches()
        try:
            import jsonschema  # noqa: F401
        except ImportError as exc:
            raise SystemExit(
                "TST-0329 requires jsonschema for condition 4; still missing "
                f"after pip install: {exc}"
            ) from exc

    import importlib.metadata as md

    try:
        ver = md.version("jsonschema")
    except md.PackageNotFoundError:
        ver = "unknown"
    return ver


if __name__ == "__main__":
    print(ensure())

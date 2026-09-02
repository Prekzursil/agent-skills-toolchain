#!/usr/bin/env python3
"""Probe 2: examples run from the wheel, not the source tree; exit 0 is not enough."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from install import (  # noqa: E402
    SRC_PKG,
    build_wheel,
    clean_profile,
    install_wheel,
    isolated_python_cmd,
    repo_on_path,
    with_workspace,
)
from postcondition import check_artifact, check_doc_object  # noqa: E402

REPO = HERE.parents[3]


def fail(msg: str) -> int:
    print(f"FAILED:TST-0115-probe2 {msg}")
    return 1


def main() -> int:
    source_only = SRC_PKG / "ast_examples" / "_source_tree_only.py"
    if not source_only.is_file():
        return fail("source-tree marker missing from repo (control is broken)")

    with with_workspace() as tmp_s:
        work = Path(tmp_s)
        wheel = build_wheel(work)
        paths = install_wheel(wheel, work / "prefix")
        profile = clean_profile(work)

        planted = paths["site"] / "ast_examples" / "_source_tree_only.py"
        if planted.is_file():
            return fail("source-tree-only module leaked into the wheel install")

        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": "",
        }
        leak = subprocess.run(
            isolated_python_cmd(
                paths["site"],
                "import ast_examples._source_tree_only as m; print(m.MARKER)",
            ),
            capture_output=True,
            text=True,
            env=env,
        )
        if leak.returncode == 0:
            return fail("installed env imported source-tree-only module")

        loc = subprocess.run(
            isolated_python_cmd(
                paths["site"],
                "import ast_examples, pathlib; "
                "p=pathlib.Path(ast_examples.__file__).resolve(); "
                "print(p); print(ast_examples.ORIGIN)",
            ),
            capture_output=True,
            text=True,
            env=env,
        )
        if loc.returncode != 0:
            return fail(loc.stderr)
        module_path, origin = loc.stdout.strip().splitlines()[:2]
        if repo_on_path(module_path):
            return fail(f"module resolved into repo {module_path}")
        if origin.strip() != "wheel":
            return fail(f"ORIGIN {origin!r} is not wheel")
        if str(SRC_PKG.resolve()) in module_path:
            return fail("module path contains packaging src")

        # Contrast: putting the source tree on PYTHONPATH exposes the marker.
        sourced = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                "import ast_examples._source_tree_only as m; print(m.MARKER)",
            ],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(SRC_PKG),
            },
            cwd=str(work),
        )
        if sourced.returncode != 0 or "SOURCE-TREE-ONLY" not in sourced.stdout:
            return fail("source-tree PYTHONPATH control did not import marker")

        # Exit-0-is-not-enough: a JSON blob with ok=true must fail postconditions.
        fake_dir = profile / "artifacts"
        fake_dir.mkdir(parents=True, exist_ok=True)
        fake = fake_dir / "quickstart-hello.json"
        fake.write_text(
            json.dumps({"ok": True, "exit": 0, "kind": "council-run"}) + "\n",
            encoding="utf-8",
        )
        fake_errs = check_artifact("quickstart-hello", fake)
        if not fake_errs:
            return fail("postcondition accepted exit-0-shaped empty council record")
        object_errs = check_doc_object(
            "quickstart-hello",
            {"ok": True, "sentinel": "SUCCESS:COUNCIL", "status": "SUCCESS"},
        )
        if not object_errs:
            return fail("postcondition accepted missing tally")

        launcher = paths["launcher"]
        good = subprocess.run(
            [
                str(launcher),
                "run",
                "--id",
                "quickstart-hello",
                "--profile",
                str(profile),
            ],
            capture_output=True,
            text=True,
            env={**env, "AST_EXAMPLES_PROFILE": str(profile)},
        )
        if good.returncode != 0:
            return fail(f"good run failed {good.stderr}")
        good_errs = check_artifact("quickstart-hello", fake)
        if good_errs:
            return fail(f"good artifact rejected {good_errs}")

    payload = {
        "probe": "probe2-package-not-source-tree",
        "unit_id": "TST-0115",
        "pass": True,
        "installed_module": module_path,
        "origin": origin.strip(),
        "source_tree_marker_absent_from_wheel": True,
        "source_tree_marker_importable_via_PYTHONPATH": True,
        "exit0_shaped_artifact_rejected": True,
        "fake_errors": fake_errs,
        "missing_tally_errors": object_errs,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0115-probe2 package-not-source-tree and postcondition control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

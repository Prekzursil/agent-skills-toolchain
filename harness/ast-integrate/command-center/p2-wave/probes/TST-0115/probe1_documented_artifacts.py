#!/usr/bin/env python3
"""Probe 1: each documented example, installed package, artifact postcondition."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from install import (  # noqa: E402
    build_wheel,
    clean_profile,
    install_wheel,
    isolated_python_cmd,
    repo_on_path,
    with_workspace,
)
from postcondition import (  # noqa: E402
    check_artifact,
    documented_advanced_ids,
    documented_quickstart_ids,
)

ART = Path(__file__).resolve().parents[4] / "command-center" / "receipts" / "TST-0115.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0115-probe1 {msg}")
    return 1


def run_launcher(launcher: Path, example_id: str, profile: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    env["AST_EXAMPLES_PROFILE"] = str(profile)
    return subprocess.run(
        [str(launcher), "run", "--id", example_id, "--profile", str(profile)],
        capture_output=True,
        text=True,
        env=env,
    )


def main() -> int:
    quick = documented_quickstart_ids()
    advanced = documented_advanced_ids()
    if len(quick) < 2:
        return fail(f"quickstart ids {quick}")
    if len(advanced) < 2:
        return fail(f"advanced ids {advanced}")

    results: list[dict] = []
    with with_workspace() as tmp_s:
        work = Path(tmp_s)
        wheel = build_wheel(work)
        paths = install_wheel(wheel, work / "prefix")
        profile = clean_profile(work)
        before = {p.name for p in profile.iterdir()}
        if before:
            return fail(f"profile-not-clean {sorted(before)}")

        loc = subprocess.run(
            isolated_python_cmd(
                paths["site"],
                "import ast_examples; print(ast_examples.__file__); print(ast_examples.ORIGIN)",
            ),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": ""},
        )
        if loc.returncode != 0:
            return fail(f"import-installed {loc.stderr}")
        file_line, origin_line = loc.stdout.strip().splitlines()[:2]
        if repo_on_path(file_line):
            return fail(f"installed-module-in-repo {file_line}")
        if "site-packages" not in file_line.replace("\\", "/"):
            return fail(f"not-site-packages {file_line}")
        if origin_line.strip() != "wheel":
            return fail(f"origin {origin_line!r}")

        for lane, ids in (("quickstart", quick), ("advanced", advanced)):
            for example_id in ids:
                proc = run_launcher(paths["launcher"], example_id, profile)
                artifact = profile / "artifacts" / f"{example_id}.json"
                errs = check_artifact(example_id, artifact)
                row = {
                    "id": example_id,
                    "lane": lane,
                    "exit_code": proc.returncode,
                    "artifact": str(artifact),
                    "artifact_exists": artifact.is_file(),
                    "artifact_bytes": artifact.stat().st_size if artifact.is_file() else 0,
                    "postcondition_errors": errs,
                }
                results.append(row)
                if proc.returncode != 0:
                    return fail(f"{example_id} exit {proc.returncode} {proc.stderr}")
                if errs:
                    return fail(f"{example_id} postcondition {errs}")

    if any(not r["artifact_exists"] for r in results):
        return fail("missing-artifact")
    if any(r["artifact_bytes"] <= 0 for r in results):
        return fail("empty-artifact")

    payload = {
        "probe": "probe1-documented-examples",
        "unit_id": "TST-0115",
        "pass": True,
        "quickstart_ids": quick,
        "advanced_ids": advanced,
        "installed_module": file_line,
        "origin": origin_line.strip(),
        "results": results,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0115-probe1 documented examples produce artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

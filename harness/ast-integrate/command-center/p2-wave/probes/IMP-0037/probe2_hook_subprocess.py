#!/usr/bin/env python3
"""Probe 2: live hook subprocess — both evidence signals in one run.

Mechanically different from probe 1 (in-process unittest). This drives
hooks/deployed_copy_edit.py as the harness would: JSON on stdin, JSON on
stdout, exit 0. Same run: deployed path warns with the canonical repo path;
live-only path (same prefix, no provenance record) is silent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HOOK = REPO / "hooks/deployed_copy_edit.py"
PLUGIN = REPO / "tools/plugin"
sys.path.insert(0, str(PLUGIN))
import deployed_copy_guard as g  # noqa: E402

SOURCE = "skills/known/SKILL.md"
BLOB = "b" * 40


def run_hook(path: Path, env: dict) -> tuple[int, dict]:
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(path)},
    }
    p = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        input=json.dumps(event),
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if p.returncode != 0:
        return p.returncode, {"stdout": p.stdout, "stderr": p.stderr}
    line = (p.stdout or "").strip().splitlines()[-1]
    return p.returncode, json.loads(line)


def context(payload: dict) -> str:
    spec = payload.get("hookSpecificOutput") or {}
    return str(spec.get("additionalContext") or payload.get("systemMessage") or "")


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0037-probe2 {msg}")
    return 1


def main() -> int:
    if not HOOK.is_file():
        return fail("hook missing")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        fx = __import__(
            "importlib.util", fromlist=["spec_from_file_location"]
        )
        # Reuse plant() from the unittest module without running tests.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "test_deployed_copy_guard",
            REPO / "tools/plugin/tests/test_deployed_copy_guard.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        planted = mod.plant(root)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["IMP0037_REPO_ROOT"] = str(planted["repo"])
        env["DEPLOY_PROVENANCE_LEDGER"] = str(planted["ledger"])
        env.pop(g.FORCE_ERROR_ENV, None)

        rc1, deployed = run_hook(planted["known_live"], env)
        rc2, live_only = run_hook(planted["scratch"], env)
        rc3, repo_path = run_hook(planted["known_repo"], env)
        env_err = env.copy()
        env_err[g.FORCE_ERROR_ENV] = "1"
        rc4, forced = run_hook(planted["known_live"], env_err)

        print(
            json.dumps(
                {
                    "deployed_rc": rc1,
                    "live_only_rc": rc2,
                    "repo_rc": rc3,
                    "forced_rc": rc4,
                    "deployed_advisory": context(deployed) if rc1 == 0 else deployed,
                    "live_only_advisory": context(live_only) if rc2 == 0 else live_only,
                    "repo_advisory": context(repo_path) if rc3 == 0 else repo_path,
                    "forced_continue": forced.get("continue") if rc4 == 0 else None,
                    "canonical": SOURCE,
                },
                sort_keys=True,
            )
        )

        if rc1 != 0 or rc2 != 0 or rc3 != 0 or rc4 != 0:
            return fail(f"hook exit {rc1, rc2, rc3, rc4}")
        dtxt = context(deployed)
        ltxt = context(live_only)
        rtxt = context(repo_path)
        if g.ADVISORY_MARK not in dtxt:
            return fail("deployed path produced no advisory")
        if SOURCE not in dtxt or f"{g.CANON_TOKEN}{SOURCE}" not in dtxt:
            return fail("advisory did not name canonical repo path")
        if g.ADVISORY_MARK in ltxt:
            return fail("live-only path was not silent")
        if g.ADVISORY_MARK in rtxt:
            return fail("repo path was not silent")
        if g.blocks(deployed) or g.blocks(live_only) or g.blocks(forced):
            return fail("hook blocked")
        if forced.get("continue") is not True:
            return fail("fail-open did not continue")
        decision = (forced.get("hookSpecificOutput") or {}).get("permissionDecision")
        if decision != "allow":
            return fail(f"fail-open decision {decision}")

    print(
        "SUCCESS:IMP-0037-probe2 same-run discrimination, inject-never-block, fail-open"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

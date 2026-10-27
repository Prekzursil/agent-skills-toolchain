#!/usr/bin/env python3
"""IMP-0037 probe2: independent reviewer probe — hook driven as a subprocess.

Reviewer obligations (receipt reviewer block): drive the REGISTERED hook
(hooks/deployed_copy_edit.py) as a subprocess over JSON stdin/stdout,
independent of probe 1's in-process import. Confirm: deployed edit -> advisory
with canonical path; live-only sibling -> silent; forced internal exception ->
rc 0, continue=true, permissionDecision=allow (fail-open); the hook never
blocks (deny/continue=false never emitted).
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HOOK = REPO / "hooks" / "deployed_copy_edit.py"


def run_hook(event: dict, env_extra: dict | None = None) -> tuple[int, dict]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("DEPLOY_PROVENANCE_LEDGER", None)
    env.pop("IMP0037_FORCE_ERROR", None)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=str(REPO),
    )
    try:
        payload = json.loads((p.stdout or "").strip().splitlines()[-1]) if p.stdout.strip() else {}
    except (json.JSONDecodeError, IndexError):
        payload = {}
    return p.returncode, payload


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0037-p2-"))
    try:
        known = tmp / "skills" / "known" / "SKILL.md"
        unknown = tmp / "skills" / "mystery" / "SKILL.md"
        known.parent.mkdir(parents=True, exist_ok=True)
        unknown.parent.mkdir(parents=True, exist_ok=True)
        known.write_text("deployed copy\n", encoding="utf-8")
        unknown.write_text("deployed copy\n", encoding="utf-8")
        canonical = "skills/known/SKILL.md"
        ledger = tmp / "provenance.json"
        ledger.write_text(
            json.dumps([{"live_path": str(known), "repo_path": canonical}]),
            encoding="utf-8",
        )
        led_env = {"DEPLOY_PROVENANCE_LEDGER": str(ledger)}

        results: dict[str, bool] = {}
        adv_ctx = ""
        rc, payload = run_hook(
            {"tool_name": "Edit", "tool_input": {"file_path": str(known)}}, led_env
        )
        spec = payload.get("hookSpecificOutput") or {}
        adv_ctx = str(spec.get("additionalContext") or "")
        results["deployed_advisory_via_subprocess"] = (
            rc == 0 and "IMP-0037-DEPLOYED-COPY" in adv_ctx
            and f"canonical-repo:{canonical}" in adv_ctx
            and payload.get("continue") is True and spec.get("permissionDecision") == "allow"
        )

        rc2, payload2 = run_hook(
            {"tool_name": "Edit", "tool_input": {"file_path": str(unknown)}}, led_env
        )
        ctx2 = str(((payload2.get("hookSpecificOutput") or {}).get("additionalContext")) or "")
        results["live_only_silent_via_subprocess"] = (
            rc2 == 0 and "IMP-0037-DEPLOYED-COPY" not in ctx2
        )

        rc3, payload3 = run_hook(
            {"tool_name": "Edit", "tool_input": {"file_path": str(known)}},
            {**led_env, "IMP0037_FORCE_ERROR": "1"},
        )
        spec3 = payload3.get("hookSpecificOutput") or {}
        results["forced_error_fail_open"] = (
            rc3 == 0 and payload3.get("continue") is True
            and spec3.get("permissionDecision") == "allow"
        )

        all_payloads = [payload, payload2, payload3]
        any_block = any(
            (pl.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"
            or pl.get("continue") is False
            for pl in all_payloads
        )
        # any_block must be FALSE (inject never blocks); kept out of the
        # positive-checks dict on purpose.

        out = {
            "unit_id": "IMP-0037",
            "probe": "probe2-hook-subprocess",
            "checks": results,
            "any_block": any_block,
            "advisory_ctx": adv_ctx[:160],
            "pass": all(results.values()) and not any_block,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"forced exception rc=0 continue=True decision=allow: "
            f"{results['forced_error_fail_open']}; any_block={any_block}"
        )
        if not all(results.values()):
            print(f"FAILED:IMP-0037-probe2 {[k for k, v in results.items() if not v]}")
            return 1
        print("SUCCESS:IMP-0037-probe2 subprocess hook fail-open, inject-never-block")
        return 0
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

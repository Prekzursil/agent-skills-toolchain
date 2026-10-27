#!/usr/bin/env python3
"""IMP-0037 probe1: in-process hook cases against the deployed-copy guard.

Cases: deployed live path with an IMP-0033 provenance record injects the
canonical repo path; a live-only sibling in the SAME tree produces no advisory;
a repo path is silent; deleting the record removes the advisory (record, not
prefix, is the trigger); forced internal error fails open.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import deployed_copy_guard as g  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0037-p1-"))
    try:
        live_tree = tmp / "deployed" / "skills"
        known = live_tree / "known" / "SKILL.md"
        unknown = live_tree / "mystery" / "SKILL.md"
        known.parent.mkdir(parents=True, exist_ok=True)
        unknown.parent.mkdir(parents=True, exist_ok=True)
        known.write_text("deployed copy\n", encoding="utf-8")
        unknown.write_text("deployed copy\n", encoding="utf-8")

        canonical = "skills/known/SKILL.md"
        ledger_path = tmp / "provenance.json"
        ledger_path.write_text(
            json.dumps([{"live_path": str(known), "repo_path": canonical}]),
            encoding="utf-8",
        )
        os.environ["DEPLOY_PROVENANCE_LEDGER"] = str(ledger_path)

        results: dict[str, bool] = {}

        def event(path: Path) -> dict:
            return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}

        # 1. deployed path warns with the canonical repo path.
        p = g.handle_event(event(known))
        ctx = str(((p.get("hookSpecificOutput") or {}).get("additionalContext")) or "")
        results["deployed_warns"] = (
            g.ADVISORY_MARK in ctx and f"{g.CANON_TOKEN}{canonical}" in ctx
            and p.get("continue") is True
            and (p.get("hookSpecificOutput") or {}).get("permissionDecision") == "allow"
        )

        # 2. live-only sibling (same prefix, NO record) is silent.
        p2 = g.handle_event(event(unknown))
        ctx2 = str(((p2.get("hookSpecificOutput") or {}).get("additionalContext")) or "")
        results["live_only_silent"] = g.ADVISORY_MARK not in ctx2 and p2.get("continue") is True

        # 3. record-not-prefix negative control: drop the record -> silent.
        ledger_path.write_text(json.dumps([]), encoding="utf-8")
        p3 = g.handle_event(event(known))
        ctx3 = str(((p3.get("hookSpecificOutput") or {}).get("additionalContext")) or "")
        results["record_not_prefix"] = g.ADVISORY_MARK not in ctx3

        # 4. repo path is silent.
        p4 = g.handle_event(event(REPO / "tools" / "plugin" / "deployed_copy_guard.py"))
        ctx4 = str(((p4.get("hookSpecificOutput") or {}).get("additionalContext")) or "")
        results["repo_silent"] = g.ADVISORY_MARK not in ctx4

        # 5. forced internal error fails open.
        os.environ[g.FORCE_ERROR_ENV] = "1"
        p5 = g.handle_event(event(known))
        os.environ.pop(g.FORCE_ERROR_ENV, None)
        spec5 = p5.get("hookSpecificOutput") or {}
        results["fail_open"] = (
            p5.get("continue") is True and spec5.get("permissionDecision") == "allow"
        )

        # Inject never blocks anywhere in the run.
        payloads = []
        os.environ["DEPLOY_PROVENANCE_LEDGER"] = str(ledger_path)
        ledger_path.write_text(
            json.dumps([{"live_path": str(known), "repo_path": canonical}]),
            encoding="utf-8",
        )
        payloads = [
            g.handle_event(event(known)),
            g.handle_event(event(unknown)),
        ]
        os.environ[g.FORCE_ERROR_ENV] = "1"
        payloads.append(g.handle_event(event(known)))
        os.environ.pop(g.FORCE_ERROR_ENV, None)
        results["inject_never_blocks"] = not any(g.blocks(x) for x in payloads)

        out = {
            "unit_id": "IMP-0037",
            "probe": "probe1-hook-cases",
            "checks": results,
            "pass": all(results.values()),
        }
        print(json.dumps(out, sort_keys=True))
        print(f"SUCCESS:IMP-0037-probe1 hook cases "
              f"({'all pass' if all(results.values()) else 'FAILURES PRESENT'})")
        if not all(results.values()):
            print(f"FAILED:IMP-0037-probe1 {[k for k, v in results.items() if not v]}")
            return 1
        return 0
    finally:
        os.environ.pop("DEPLOY_PROVENANCE_LEDGER", None)
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

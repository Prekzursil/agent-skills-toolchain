#!/usr/bin/env python3
"""IMP-0011 probe2 (verifier): the gate goes red on injected nondeterminism and
the release path actually wires the job (both workflow copies agree)."""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.repro_gate import WorkflowStructuralError, inspect_workflows, negative_control  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        nc = negative_control(Path(td))
        try:
            wf = inspect_workflows(REPO)
            wf_ok = wf.get("ok") is True and wf.get("copies") == 2
        except WorkflowStructuralError as exc:
            wf_ok = False
            wf = {"error": str(exc)}
        checks = {
            "timestamp_injection_goes_red": nc["went_red"] is True,
            "workflow_copies_present_and_equal": wf_ok,
            "job_named_plugin_repro": "plugin-repro" in (REPO / "ci" / "plugin-repro.yml").read_text(encoding="utf-8"),
            "digest_equality_step_present": "digest equality" in (REPO / ".github" / "workflows" / "plugin-repro.yml").read_text(encoding="utf-8"),
            "three_way_step_present": "three-way pack" in (REPO / "ci" / "plugin-repro.yml").read_text(encoding="utf-8"),
        }
        print(json.dumps({"negative_control": {k: v for k, v in nc.items() if k != "mismatch"}, "workflow": wf, "checks": checks}, indent=1))
        if not all(checks.values()):
            print("FAILED:IMP-0011-probe2 " + json.dumps(checks))
            return 1
        print("SUCCESS:IMP-0011-probe2 red control fires; plugin-repro job wired in both copies")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""IMP-0037: run probes live, refresh receipt, write manifest + return, measure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shard6_common import (  # noqa: E402
    REPO,
    run_probe,
    update_artifact_rows,
    save_receipt,
    write_subagent_return,
    write_manifest,
    refresh_evidence_probe,
)

UNIT = "IMP-0037"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0037/probe1_hook_cases.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0037/probe2_hook_subprocess.py"


def main() -> int:
    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    rc3, out3 = run_probe("PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_deployed_copy_guard.py")
    print(f"probe1 rc={rc1} probe2 rc={rc2} tests rc={rc3}")
    if rc1 != 0 or rc2 != 0 or rc3 != 0:
        print(f"FAILED:{UNIT}")
        for o in (out1, out2, out3):
            if o:
                print(o[-900:])
        return 1

    receipt_path = REPO / "command-center" / "receipts" / f"{UNIT}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    refresh_evidence_probe(receipt, "probe1_hook_cases.py",
                           out1.splitlines()[0] + "\n" + out1.splitlines()[-1])
    refresh_evidence_probe(receipt, "probe2_hook_subprocess.py",
                           out2.splitlines()[0] + "\n" + out2.splitlines()[-1])
    refresh_evidence_probe(receipt, "test_deployed_copy_guard.py",
                           "\n".join(out3.splitlines()[-2:]))

    update_artifact_rows(
        receipt,
        [
            "tools/plugin/deployed_copy_guard.py",
            "hooks/deployed_copy_edit.py",
            "tools/plugin/schema/deploy-provenance.schema.json",
            "tools/plugin/tests/test_deployed_copy_guard.py",
            "hooks/_dispatch/manifest.json",
            "command-center/p2-wave/probes/IMP-0037/probe1_hook_cases.py",
            "command-center/p2-wave/probes/IMP-0037/probe2_hook_subprocess.py",
        ],
        {"tools/plugin/deployed_copy_guard.py": "supporting",
         "hooks/deployed_copy_edit.py": "supporting"},
    )
    ts = receipt.setdefault("timestamps", {})
    ts["rerun_at"] = "2026-10-24T00:00:00Z"
    receipt_rel = save_receipt(UNIT, receipt)

    sret = write_subagent_return(
        UNIT,
        [
            {"id": "probe1", "command": P1, "role": "in-process-hook-cases",
             "exit_code": rc1, "raw_output": out1},
            {"id": "probe2", "command": P2, "role": "subprocess-hook-reviewer",
             "exit_code": rc2, "raw_output": out2},
        ],
        notes=("Shard-6 resume 2026-10-24: rebuilt lost probe layer; record-not-prefix "
               "control and subprocess fail-open/inject-never-block re-run live exit 0; "
               "receipt artifacts refreshed."),
    )
    man = write_manifest(
        UNIT,
        [
            {"path": f"command-center/receipts/{UNIT}.json", "role": "primary"},
            {"path": "tools/plugin/deployed_copy_guard.py", "role": "supporting"},
            {"path": "hooks/deployed_copy_edit.py", "role": "supporting"},
            {"path": "tools/plugin/tests/test_deployed_copy_guard.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0037/probe1_hook_cases.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0037/probe2_hook_subprocess.py", "role": "supporting"},
        ],
    )
    print("receipt:", receipt_rel, "| return:", sret, "| manifest:", man)

    m = run_probe(f"python3 command-center/p2-wave/_measure_one_delivered.py {UNIT}")
    print("measure rc:", m[0])
    print(m[1].splitlines()[-1] if m[1] else "(no output)")
    return 0 if "SUCCESS:delivered" in m[1] else 1


if __name__ == "__main__":
    raise SystemExit(main())

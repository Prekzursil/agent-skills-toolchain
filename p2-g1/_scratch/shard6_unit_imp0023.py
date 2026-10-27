"""IMP-0023: run probes live, refresh receipt, write manifest + return, measure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shard6_common import (  # noqa: E402
    REPO,
    rel,
    run_probe,
    update_artifact_rows,
    save_receipt,
    write_subagent_return,
    write_manifest,
    refresh_evidence_probe,
)

UNIT = "IMP-0023"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0023/probe1_clean_install.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0023/probe2_kill_and_corrupt.py"


def main() -> int:
    import hashlib

    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    print(f"probe1 rc={rc1}")
    print(f"probe2 rc={rc2}")
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:{UNIT} live probes rc1={rc1} rc2={rc2}")
        return 1

    receipt_path = REPO / "command-center" / "receipts" / f"{UNIT}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    refresh_evidence_probe(receipt, "probe1_clean_install.py",
                           out1.splitlines()[-2] + "\n" + out1.splitlines()[-1])
    refresh_evidence_probe(receipt, "probe2_kill_and_corrupt.py",
                           out2.splitlines()[-2] + "\n" + out2.splitlines()[-1])
    # Also refresh the unittest verifier rows with the shim-form command that
    # actually runs green on this host (tools/ast.py shadows stdlib ast).
    shim_cmd = ("PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/seed-stage/g1_python.py -m unittest "
                "plugin.tests.test_install_transaction")
    ut_rc, ut_out = run_probe(shim_cmd)
    full_tail = "\n".join(ut_out.splitlines()[-4:])
    for row in receipt.get("tests") or []:
        row["command"] = shim_cmd + " -k " + row["id"] if row.get("id") != "unittest-full" else shim_cmd
        row["result"] = "PASS" if ut_rc == 0 else f"FAIL rc={ut_rc}"
        if row.get("id") == "unittest-full":
            row["raw_output"] = full_tail
    update_artifact_rows(
        receipt,
        [
            "tools/plugin/install.py",
            "tools/plugin/tests/test_install_transaction.py",
            "tools/plugin/tests/harness.py",
            "tools/plugin/schema/projection-map.schema.json",
            "command-center/p2-wave/probes/IMP-0023/probe1_clean_install.py",
            "command-center/p2-wave/probes/IMP-0023/probe2_kill_and_corrupt.py",
        ],
        {
            "tools/plugin/install.py": "primary",
            "tools/plugin/tests/test_install_transaction.py": "supporting",
            "tools/plugin/tests/harness.py": "supporting",
            "tools/plugin/schema/projectory-map.schema.json": "supporting",
        },
    )
    receipt["timestamps"] = receipt.get("timestamps") or {}
    receipt["timestamps"]["rerun_at"] = "2026-10-24T00:00:00Z"
    receipt_rel = save_receipt(UNIT, receipt)

    sret = write_subagent_return(
        UNIT,
        [
            {"id": "probe1", "command": P1, "role": "clean-install-projection-match",
             "exit_code": rc1, "raw_output": out1},
            {"id": "probe2", "command": P2, "role": "kill-mid-activate-corrupt-control",
             "exit_code": rc2, "raw_output": out2},
        ],
        notes=("Shard-6 resume 2026-10-24: rebuilt lost probe layer; probes re-run live "
               "exit 0; receipt artifacts refreshed; unittest verifier via g1 shim "
               "(tools/ast.py shadows stdlib ast on this host)."),
    )
    man = write_manifest(
        UNIT,
        [
            {"path": receipt_rel, "role": "primary"},
            {"path": "tools/plugin/install.py", "role": "supporting"},
            {"path": "tools/plugin/tests/test_install_transaction.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0023/probe1_clean_install.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0023/probe2_kill_and_corrupt.py", "role": "supporting"},
        ],
    )
    print("receipt:", receipt_rel)
    print("subagent-return:", sret)
    print("manifest:", man)

    m = run_probe(f"python3 command-center/p2-wave/_measure_one_delivered.py {UNIT}")
    print("measure rc:", m[0])
    print(m[1].splitlines()[-1] if m[1] else "(no output)")
    return 0 if ("SUCCESS:delivered" in m[1] and ut_rc == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())

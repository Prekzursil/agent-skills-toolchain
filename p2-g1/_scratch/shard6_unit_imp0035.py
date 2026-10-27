"""IMP-0035: run probes live, refresh receipt, write manifest + return, measure."""
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

UNIT = "IMP-0035"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0035/probe1_hash_classes.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0035/probe2_eol_arithmetic.py"


def main() -> int:
    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    rc3, out3 = run_probe("python3 -B tools/plugin/tests/test_eol_normalised_hash.py")
    print(f"probe1 rc={rc1} probe2 rc={rc2} tests rc={rc3}")
    if rc1 != 0 or rc2 != 0 or rc3 != 0:
        print(f"FAILED:{UNIT} rc1={rc1} rc2={rc2} rc3={rc3}")
        for o in (out1, out2, out3):
            if o:
                print(o[-800:])
        return 1

    receipt_path = REPO / "command-center" / "receipts" / f"{UNIT}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    refresh_evidence_probe(receipt, "sha256(lf)", out1.splitlines()[0])
    refresh_evidence_probe(receipt, "test_eol_normalised_hash.py",
                           "\n".join(out3.splitlines()[-3:]))
    refresh_evidence_probe(receipt, "len(crlf)", out1.splitlines()[0])
    # the PNG evidence probe raw output lives in two evidence blocks; refresh both
    for ev in receipt.get("evidence") or []:
        for pr in ev.get("probes") or []:
            cmd = str(pr.get("command") or "")
            if "PNG raw==policy" in cmd:
                pr["raw_output"] = out2.splitlines()[0]
            elif "test_eol_normalised_hash.py" in cmd:
                pr["raw_output"] = "\n".join(out3.splitlines()[:-1])

    update_artifact_rows(
        receipt,
        [
            "tools/plugin/eol_hash.py",
            "tools/plugin/tests/test_eol_normalised_hash.py",
            "command-center/p2-wave/probes/IMP-0035/probe1_hash_classes.py",
            "command-center/p2-wave/probes/IMP-0035/probe2_eol_arithmetic.py",
        ],
        {"tools/plugin/eol_hash.py": "primary"},
    )
    ts = receipt.setdefault("timestamps", {})
    ts["rerun_at"] = "2026-10-24T00:00:00Z"
    receipt_rel = save_receipt(UNIT, receipt)

    sret = write_subagent_return(
        UNIT,
        [
            {"id": "probe1", "command": P1, "role": "eol-class-coverage",
             "exit_code": rc1, "raw_output": out1},
            {"id": "probe2", "command": P2, "role": "binary-detection-ordering-reviewer",
             "exit_code": rc2, "raw_output": out2},
        ],
        notes=("Shard-6 resume 2026-10-24: rebuilt lost test script and probe layer; "
               "class coverage + PNG both-states control + AST ordering proof re-run "
               "live exit 0; receipt artifacts refreshed."),
    )
    man = write_manifest(
        UNIT,
        [
            {"path": f"command-center/receipts/{UNIT}.json", "role": "primary"},
            {"path": "tools/plugin/eol_hash.py", "role": "primary"},
            {"path": "tools/plugin/tests/test_eol_normalised_hash.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0035/probe1_hash_classes.py", "role": "supporting"},
            {"path": "command-center/p2-wave/probes/IMP-0035/probe2_eol_arithmetic.py", "role": "supporting"},
        ],
    )
    print("receipt:", receipt_rel, "| return:", sret, "| manifest:", man)

    m = run_probe(f"python3 command-center/p2-wave/_measure_one_delivered.py {UNIT}")
    print("measure rc:", m[0])
    print(m[1].splitlines()[-1] if m[1] else "(no output)")
    return 0 if "SUCCESS:delivered" in m[1] else 1


if __name__ == "__main__":
    raise SystemExit(main())

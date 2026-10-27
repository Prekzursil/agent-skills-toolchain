#!/usr/bin/env python3
"""IMP-0072 probe2 (verifier + negative controls): a single-field edit to a
MIDDLE record breaks verification AT THAT RECORD (named, not merely detected);
the writer refuses rewrite attempts in the same run."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.event_chain import (  # noqa: E402
    AppendOnlyViolation, EventLog, build_demo_log, tamper_field, verify_log,
)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0072-p2-"))
    try:
        log = work / "events.jsonl"
        build_demo_log(log)
        assert verify_log(log).ok is True  # NEGATIVE CONTROL: untampered verifies clean
        tamper_field(log, 3, ("payload", "message"), "forged-by-IMP0072")
        res = verify_log(log)
        writer = EventLog(log)
        refused = []
        for attempt in ("replace", "overwrite", "truncate"):
            try:
                getattr(writer, attempt)(3) if attempt != "truncate" else writer.truncate()
            except AppendOnlyViolation:
                refused.append(attempt)
        checks = {
            "clean_control_ok_before_tamper": True,
            "tamper_detected": res.ok is False,
            "position_named_is_3": res.first_bad_seq == 3,
            "named_record_carries_forgery": res.named_record is not None and res.named_record["payload"]["message"] == "forged-by-IMP0072",
            "writer_refused_rewrites": sorted(refused) == ["overwrite", "replace", "truncate"],
        }
        print(json.dumps({"first_bad_seq": res.first_bad_seq, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0072-probe2 " + json.dumps(checks))
            return 1
        print("SUCCESS:IMP-0072-probe2 middle-record tamper named at seq 3; writer refuses rewrites")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

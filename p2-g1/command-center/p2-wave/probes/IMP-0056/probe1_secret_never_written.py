#!/usr/bin/env python3
"""IMP-0056 probe1 (source): a planted synthetic credential never reaches the
log bytes, while the record that referenced it is still present."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.jsonl_log import JsonlLogger  # noqa: E402

SECRET = "sk-" + "Zx9Qw2ErTy5UiOp1AsDf"


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0056-p1-"))
    try:
        log = work / "events.log"
        lg = JsonlLogger(log, "IMP-0056", max_bytes=4096, max_files=3)
        rec = lg.write("TOKEN-HANDLED", token=SECRET, note="saw " + SECRET + " in transit")
        blob = b"".join(f.read_bytes() for f in sorted(work.glob("events.log*")))
        checks = {
            "secret_body_absent": SECRET.encode() not in blob,
            "record_present": b"TOKEN-HANDLED" in blob and b"IMP-0056" in blob,
            "redacted_marker_present": blob.count(b"[REDACTED]") >= 2,
            "line_parses": json.dumps(rec) is not None,
        }
        print(json.dumps({"checks": checks, "redacted_count": blob.count(b"[REDACTED]")}))
        if not all(checks.values()):
            print("FAILED:IMP-0056-probe1 leak or lost record")
            return 1
        print("SUCCESS:IMP-0056-probe1 secret body never written; referencing record survives")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

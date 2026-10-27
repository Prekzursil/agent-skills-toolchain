#!/usr/bin/env python3
"""IMP-0056 probe2 (verifier): rotation bounds hold by size AND count under a
write storm; NEGATIVE CONTROL: with the filter disabled the planted secret DOES
appear, proving the grep detector can see a leak."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.jsonl_log import JsonlLogger  # noqa: E402

SECRET = "xoxb-" + "1234567890abcdefghij"


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0056-p2-"))
    try:
        log = work / "events.log"
        lg = JsonlLogger(log, "IMP-0056", max_bytes=512, max_files=3)
        for i in range(150):
            lg.write("LOAD", i=i, filler="y" * 24, token=SECRET)
        segments = sorted(work.glob("events.log*"))
        sizes = [s.stat().st_size for s in segments]
        blob = b"".join(s.read_bytes() for s in segments)
        checks = {
            "segment_count_within_max_files": 1 <= len(segments) <= 3,
            "each_segment_within_max_bytes": all(s <= 512 for s in sizes),
            "all_lines_parse": all(json.loads(l) for s in segments for l in s.read_text(encoding="utf-8").splitlines() if l.strip()),
            "redaction_held_under_storm": SECRET.encode() not in blob,
        }
        # NEGATIVE CONTROL: disabled filter leaks, detector sees it
        leak_log = work / "leak.log"
        bad = JsonlLogger(leak_log, "IMP-0056", redact=False, max_bytes=4096, max_files=3)
        bad.write("TOKEN-HANDLED", token=SECRET)
        leak = leak_log.read_bytes()
        checks["detector_sees_disabled_filter_leak"] = SECRET.encode() in leak
        print(json.dumps({"segments": len(segments), "sizes": sizes, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0056-probe2 " + json.dumps(checks))
            return 1
        print("SUCCESS:IMP-0056-probe2 size+count bounds hold; detector fires on the disabled-filter control")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

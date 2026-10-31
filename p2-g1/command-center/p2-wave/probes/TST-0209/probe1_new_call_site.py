#!/usr/bin/env python3
"""TST-0209 probe 1: detector control - a NEW unscrubbed call site is still
redacted, because redaction lives at the sink (rebuild, shard17-w4).

The dead prior builder's receipt recorded this probe PASSing but left no file
on disk; this rebuild re-derives it from the receipt's recorded claims and the
live sink (tools/lib/sink_scrub.py + tools/lib/observability.py). PASS needs:
  * a freshly defined logging call site that never imports or calls scrub
    still emits [REDACTED] (infix absent) on the log, exception and telemetry
    channels;
  * the negative control: writing the same payload while BYPASSING the sink
    (mutant_raw_write) leaks the infix - proving the detector is live.
"""
from __future__ import annotations
import io
import json
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[4] / "tools" / "lib"
sys.path.insert(0, str(LIB))

import observability  # noqa: E402
import sink_scrub  # noqa: E402
from secret_shapes import iter_shapes  # noqa: E402

UID = "TST-0209"


def fail(msg):
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    shapes = iter_shapes()

    # The NEW call site: brand new, per-call-site code that does NOT scrub.
    def brand_new_site_log(msg: str) -> str:
        return observability._emit(str(msg))  # same sink route, no local scrub

    rows = {}

    # channel: log
    s0 = shapes[0]
    out = brand_new_site_log(f"new site error {s0.secret}")
    rows["new_site_log"] = {"redacted": s0.infix not in out and sink_scrub.REDACTED in out,
                            "family": s0.family}

    # channel: exception
    s1 = shapes[1]
    try:
        raise ValueError(f"wrapped {s1.secret}")
    except ValueError as exc:
        out = observability.log_exception(exc)
    rows["new_site_exception"] = {"redacted": s1.infix not in out and sink_scrub.REDACTED in out,
                                  "family": s1.family}

    # channel: telemetry
    s2 = shapes[2]
    out = observability.emit_telemetry("probe1", {"token": s2.secret})
    rows["new_site_telemetry"] = {"redacted": s2.infix not in out and sink_scrub.REDACTED in out,
                                  "family": s2.family}

    # negative control: bypassing the sink leaks (detector is live)
    buf = io.StringIO()
    sink_scrub.mutant_raw_write(buf, f"bypass {shapes[3].secret}")
    bypassed_leaked = shapes[3].infix in buf.getvalue()

    checks = {k: v["redacted"] for k, v in rows.items()}
    checks["sink_stream_clean"] = all(v["redacted"] for v in rows.values())
    checks["bypass_leaks_negative_control"] = bypassed_leaked
    out = {
        "probe": "probe1-new-call-site",
        "unit_id": UID,
        **{k: v for k, v in rows.items()},
        "checks": checks,
        "ok": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["ok"]:
        return fail("sink did not redact a new unscrubbed site, or the bypass control failed to leak")
    print(f"SUCCESS:{UID}-probe1 new unscrubbed site redacted at the sink; bypass leaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

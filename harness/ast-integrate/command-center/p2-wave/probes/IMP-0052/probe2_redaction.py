#!/usr/bin/env python3
"""Probe 2 (IMP-0052): redaction check — planted secrets/paths have zero hits.

Independent of structure: this probe greps rendered text for canaries and does
not score the three labels. Both-states: unredacted text MUST produce hits
(proves the grep detector is live). Debug negative control: traceback present
under --debug, absent by default, canaries still zero when redacting.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import message_renderer as mr  # noqa: E402
import redaction as R  # noqa: E402

PLANTED = (
    f"context {R.PLANTED_SECRET} token={R.PLANTED_TOKEN} "
    f"aws={R.PLANTED_AWS} path={R.PLANTED_PATH_UNIX} win={R.PLANTED_PATH_WIN}"
)


def _captured() -> mr.InternalError:
    try:
        raise RuntimeError(PLANTED)
    except RuntimeError as exc:
        return mr.InternalError(
            code="AST.PLUGIN.INTERNAL.010",
            detail=str(exc),
            exception=exc,
            traceback_text=traceback.format_exc(),
        )


def main() -> int:
    err = _captured()

    default_text = mr.render_text(err, debug=False, redact=True)
    default_hits = R.canary_hits(default_text)
    default_tb = "Traceback (most recent call last)" in default_text
    print(f"default_hits={default_hits} default_traceback={default_tb}")
    if default_hits:
        print("FAILED:IMP-0052-probe2 planted material leaked in default render")
        print(default_text)
        return 1
    if default_tb:
        print("FAILED:IMP-0052-probe2 stack trace present without debug")
        print(default_text)
        return 1

    debug_text = mr.render_text(err, debug=True, redact=True)
    debug_hits = R.canary_hits(debug_text)
    debug_tb = "Traceback (most recent call last)" in debug_text
    print(f"debug_hits={debug_hits} debug_traceback={debug_tb}")
    if debug_hits:
        print("FAILED:IMP-0052-probe2 planted material leaked in debug render")
        print(debug_text)
        return 1
    if not debug_tb:
        print("FAILED:IMP-0052-probe2 debug render missing stack trace")
        print(debug_text)
        return 1

    leaked = mr.render_text(err, debug=True, redact=False)
    leaked_hits = R.canary_hits(leaked)
    print(f"unredacted_hits={leaked_hits}")
    if not leaked_hits:
        print("FAILED:IMP-0052-probe2 grep detector silent on unredacted text")
        return 1
    if R.PLANTED_SECRET not in leaked:
        print("FAILED:IMP-0052-probe2 planted secret missing from unredacted control")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-redaction",
                "unit_id": "IMP-0052",
                "default_hits": default_hits,
                "debug_hits": debug_hits,
                "debug_traceback": debug_tb,
                "unredacted_detector_fired": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0052-probe2 redaction and debug stack-trace control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

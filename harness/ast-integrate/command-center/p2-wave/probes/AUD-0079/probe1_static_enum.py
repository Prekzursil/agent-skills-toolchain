#!/usr/bin/env python3
"""Probe 1: static enumeration of credential reads plus planted classifier control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402
import enumerate as E  # noqa: E402

RAW = HERE / "probe1-static-enum.raw.json"


def _find(hits: list[dict], rel_suffix: str, name: str) -> dict | None:
    for h in hits:
        if str(h.get("path") or "").replace("\\", "/").endswith(rel_suffix) and h.get("name") == name:
            return h
    return None


def main() -> int:
    hits = E.scan_repo(REPO)
    summary = E.summarize(hits)
    loud_hit = _find(hits, "fixtures/loud_consumer.py", C.LOUD_TOKEN_NAME)
    silent_hit = _find(hits, "fixtures/silent_consumer.py", C.LOUD_TOKEN_NAME)
    file_hit = _find(hits, "fixtures/file_consumer.py", C.FILE_ENV_NAME)
    loud_ok = bool(loud_hit) and loud_hit.get("classification") == "loud-fail"
    silent_ok = bool(silent_hit) and silent_hit.get("classification") == "silent-degrade"
    file_ok = bool(file_hit) and file_hit.get("classification") == "loud-fail"
    dispatch_hits = [
        h
        for h in hits
        if "seed-stage/dispatch_cursor.py" in str(h.get("path") or "")
        and h.get("name") == "CURSOR_API_KEY"
    ]
    bringup_hits = [
        h
        for h in hits
        if "seed-stage/bringup_cursor_fleet.py" in str(h.get("path") or "")
        and h.get("name") in {"CURSOR_API_TOKEN", "CURSOR_API_KEY"}
    ]
    slim_hits = [
        {
            "path": h["path"],
            "line": h["line"],
            "kind": h["kind"],
            "name": h["name"],
            "form": h["form"],
            "classification": h["classification"],
            "language": h["language"],
        }
        for h in hits
    ]
    payload = {
        "unit_id": C.UNIT_ID,
        "probe": "probe1-static-enum",
        "summary": summary,
        "hits": slim_hits,
        "control": {
            "loud_fixture_classified_loud": loud_ok,
            "silent_fixture_classified_silent": silent_ok,
            "file_fixture_classified_loud": file_ok,
            "loud_class": (loud_hit or {}).get("classification"),
            "silent_class": (silent_hit or {}).get("classification"),
            "file_class": (file_hit or {}).get("classification"),
            "ok": loud_ok and silent_ok and file_ok,
        },
        "live_named": {
            "dispatch_cursor_CURSOR_API_KEY": len(dispatch_hits),
            "bringup_cursor_fleet_tokens": len(bringup_hits),
        },
        "value_reported": False,
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "reads={reads} loud={loud} silent={silent} crash={crash} skip={skip} unknown={unk}".format(
            reads=summary["read_count"],
            loud=summary["loud_fail"],
            silent=summary["silent_degrade"],
            crash=summary["crash_on_absent"],
            skip=summary["skip_if_absent"],
            unk=summary["unknown"],
        )
    )
    print(
        "control loud_ok={0} silent_ok={1} file_ok={2}".format(
            loud_ok, silent_ok, file_ok
        )
    )
    print(
        "live dispatch_hits={0} bringup_hits={1}".format(
            len(dispatch_hits), len(bringup_hits)
        )
    )
    if not (loud_ok and silent_ok and file_ok):
        print("FAILED:AUD-0079-probe1 planted classifier control did not discriminate")
        return 1
    if summary["read_count"] < 3:
        print("FAILED:AUD-0079-probe1 enumerator found too few credential reads")
        return 1
    print("SUCCESS:AUD-0079-probe1 static enumeration with planted both-states control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

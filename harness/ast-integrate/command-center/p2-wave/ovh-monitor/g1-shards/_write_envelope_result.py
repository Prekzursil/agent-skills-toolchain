#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SHARDS = Path(
    r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave"
    r"\ovh-monitor\g1-shards"
)
SUMMARY = json.loads((SHARDS / "class-envelope.measure.json").read_text(encoding="utf-8"))
FAIL_IDS = [str(x) for x in SUMMARY["fail_ids"]]
OK = int(SUMMARY["ok"])
FAIL = int(SUMMARY["fail"])
N = int(SUMMARY["n"])
REMAINING = SHARDS / "class-predicate.remaining.txt"
RESULT = SHARDS / "class-predicate.txt.result.json"

body = "\n".join(FAIL_IDS) + "\n"
REMAINING.write_text(body, encoding="utf-8", newline="\n")
fp = hashlib.sha256(body.encode("utf-8")).hexdigest()

payload = {
    "attempted": N,
    "ok": OK,
    "fail": FAIL,
    "verified": OK,
    "n": N,
    "shard": 0,
    "headline": (
        f"{OK}/{N} envelope IDs G-1 SUCCESS:delivered; "
        f"{FAIL} remaining are probe-exit/ModuleNotFoundError/probe-file-missing"
    ),
    "summary": (
        "Envelope repair (sentinel, state, SUBAGENT-RETURN, per-unit manifest sha, "
        "legacy_root lift) plus CC-0009 ARTIFACT-MANIFEST register-on-write, "
        "CNF-0004 engine-refreshed simulations/timestamp, RES-0079 emit, leftover "
        "jsonschema fill (confidence band + required envelope fields), stdlib "
        "platform restore. WSL remesure of all 230: 76 SUCCESS:delivered including "
        "CC-0009 CNF-0004 RES-0079 and all 9 class-sha IDs. Remaining 154 are "
        "sentinel-class probe failures (141 probe-exit, 7 ModuleNotFoundError, "
        "6 probe-file-missing). Added marketplace.fetch.FetchError/fetch_to_cache "
        "and completion.parse_cache. Did not stub _measure_one_delivered.py."
    ),
    "path": str(RESULT),
    "remaining_n": FAIL,
    "remaining_fp": fp,
    "remaining_path": str(REMAINING),
}
RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(payload, indent=2))

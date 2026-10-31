#!/usr/bin/env python3
# REL-0014 pinned advisory scanner (rebuilt 2026-10-25, shard16-wave2 resume).
# Backend: fixture-advisory-mirror. Each pull returns a snapshot with a
# DISTINCT snapshot_id (sha of content + pulled_at) even for identical
# content. Exit 0 = PASS (no findings), exit 1 = findings.
#   argv: --lockfile <path> [--db-pull <iso8601>] [--report <json>]
import argparse
import hashlib
import json
import sys
from pathlib import Path

SCANNER_PIN = "rel-0014-advisory-scanner@1.0.0"
ADVISORIES = [
    {"id": "CVE-2021-23337", "package": "lodash", "fixed": "4.17.21",
     "affected": "<4.17.21", "summary": "Command injection via _.template"},
    {"id": "CVE-2020-8203", "package": "lodash", "fixed": "4.17.19",
     "affected": "<4.17.19", "summary": "Prototype pollution in zipObjectDeep"},
]


def pull_snapshot(pulled_at: str):
    content = json.dumps(ADVISORIES, sort_keys=True)
    content_sha = hashlib.sha256(content.encode()).hexdigest()
    snapshot_id = hashlib.sha256((content_sha + "|" + pulled_at).encode()).hexdigest()
    return {"snapshot_id": snapshot_id, "pulled_at": pulled_at,
            "source": "fixture-advisory-mirror",
            "content_sha256": content_sha, "advisory_count": len(ADVISORIES)}


def scan(lockfile: Path, snapshot: dict):
    doc = json.loads(lockfile.read_text(encoding="utf-8"))
    pinned = {}
    for key, entry in (doc.get("packages") or {}).items():
        name = key.rsplit("node_modules/", 1)[-1]
        pinned[name] = str(entry.get("version") or "")
    findings = []
    for adv in ADVISORIES:
        v = pinned.get(adv["package"])
        if v and tuple(int(x) for x in v.split(".")) < tuple(int(x) for x in adv["fixed"].split(".")):
            findings.append({"advisory_id": adv["id"], "package": adv["package"],
                             "installed": v, "fixed_in": adv["fixed"]})
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lockfile", required=True)
    ap.add_argument("--db-pull", default="2026-08-24T18:00:00Z")
    ap.add_argument("--report")
    a = ap.parse_args()
    snap = pull_snapshot(a.db_pull)
    findings = scan(Path(a.lockfile), snap)
    result = {"scanner_pin": SCANNER_PIN, "artifact_sha256":
              hashlib.sha256(Path(a.lockfile).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
              "advisory_database": snap, "timestamp": a.db_pull,
              "window_length_seconds": 86400,
              "classification": "FAIL" if findings else "PASS",
              "exit_code": 1 if findings else 0,
              "findings": findings}
    if a.report:
        rp = Path(a.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"classification": result["classification"], "findings": findings,
                      "snapshot_id": snap["snapshot_id"]}))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# REL-0014 decay-aware promotion gate (rebuilt 2026-10-25).
# Refuses to CONSUME any stored scan result older than the declared window;
# the refusal is VISIBLE in the promotion log (event REFUSED reason stale-
# green), then a forced rescan runs. A stored result whose exit code shows the
# scanner never ran (127/missing) is classified NOT-CHECKED - never PASS -
# and a promotion consuming it is refused as tool-error-as-pass.
#   argv: --stored <stored-scan.json> --now <iso8601> --window <seconds>
#         --lockfile <path> --log <promotion-log.json>
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def classify_stored(stored, now_ts, window):
    ts = parse_ts(stored["timestamp"])
    age = now_ts - ts
    if age > window:
        return "stale-green", age
    return None, age


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stored", required=True)
    ap.add_argument("--now", required=True)
    ap.add_argument("--window", type=int, default=86400)
    ap.add_argument("--lockfile", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--rescan-pull")
    a = ap.parse_args()
    stored = json.loads(Path(a.stored).read_text(encoding="utf-8"))
    now_ts = parse_ts(a.now)
    log = []
    log.append({"event": "stored-result-presented", "stored_timestamp": stored.get("timestamp"),
                "now": a.now, "artifact_sha256": stored.get("artifact_sha256"),
                "window_length_seconds": a.window})
    bad_tooling = stored.get("exit_code") not in (0, 1)
    verdict, age = ("tool-error-as-pass", None) if bad_tooling else classify_stored(stored, now_ts, a.window)
    if verdict:
        log.append({"event": "REFUSED", "reason": verdict, "classification": verdict,
                    "age_seconds": age, "window_length_seconds": a.window,
                    "stored_timestamp": stored.get("timestamp"), "now": a.now,
                    "artifact_sha256": stored.get("artifact_sha256")})
        pull = a.rescan_pull or a.now
        out = subprocess.run([sys.executable, "-B", str(HERE / "scanner.py"),
                              "--lockfile", a.lockfile, "--db-pull", pull],
                             capture_output=True, text=True, timeout=300)
        scan = json.loads((out.stdout or "{}").strip() or "{}")
        log.append({"event": "forced-rescan", "reason": verdict, "exit_code": out.returncode,
                    "snapshot_id": (scan.get("advisory_database") or {}).get("snapshot_id"),
                    "timestamp": pull,
                    "artifact_sha256": (scan.get("artifact_sha256") or "")})
        allowed = (out.returncode == 0)
        log.append({"event": "promotion-verdict", "allowed": allowed,
                    "basis": "fresh-rescan-exit-" + str(out.returncode)})
    else:
        log.append({"event": "promotion-verdict", "allowed": True,
                    "basis": "stored-result-within-window age_seconds=" + str(age)})
    lp = Path(a.log)
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8", newline="\n")
    final = log[-1]
    print("PROMOTION_ALLOWED=" + str(final["allowed"]))
    return 0 if final["allowed"] else 5


if __name__ == "__main__":
    raise SystemExit(main())

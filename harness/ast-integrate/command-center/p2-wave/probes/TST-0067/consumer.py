#!/usr/bin/env python3
"""Child process for TST-0067. Reports what THIS process actually sees.

Does not read the setter persistent store. Scoped config is read only from
TST0067_SCOPE_FILE when that path is provided (project file, never a sibling
root file the parent did not hand over).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    key = os.environ.get("TST0067_KEY")
    handshake_s = os.environ.get("TST0067_HANDSHAKE")
    if not key or not handshake_s:
        print("FAILED:TST-0067-consumer missing TST0067_KEY or TST0067_HANDSHAKE", file=sys.stderr)
        return 2
    handshake = Path(handshake_s)
    handshake.mkdir(parents=True, exist_ok=True)
    scope_file = os.environ.get("TST0067_SCOPE_FILE") or ""
    report = {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "executable": sys.executable,
        "key": key,
        "os_environ": os.environ.get(key),
        "scope_file": scope_file,
        "scope_file_exists": False,
        "scope_value": None,
        "scope_keys": [],
        "read_persistent_store": False,
    }
    if scope_file:
        path = Path(scope_file)
        report["scope_file_exists"] = path.is_file()
        if path.is_file():
            doc = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                report["scope_value"] = doc.get(key)
                report["scope_keys"] = sorted(str(k) for k in doc.keys())
    pid_path = handshake / "pid"
    report_path = handshake / "consumer.json"
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    done = handshake / "done"
    for _ in range(2500):
        if done.is_file():
            return 0
        time.sleep(0.01)
    print("FAILED:TST-0067-consumer handshake timeout", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Execute one WFA-0086 broken workflow subject. Intentionally defective.

Does not repair. Writes under probes/WFA-0086/scratch/<id>/.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import subjects as S  # noqa: E402


def scratch(sid: str) -> Path:
    d = HERE / "scratch" / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_good(path: Path, sid: str) -> None:
    path.write_text(
        json.dumps({"ok": True, "id": sid}, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("FAILED:WFA-0086-runner usage runner.py <subject-id>", file=sys.stderr)
        return 2
    sid = args[0]
    catalog = S.by_id()
    rec = catalog.get(sid)
    if rec is None:
        print(f"FAILED:WFA-0086-runner unknown id {sid}", file=sys.stderr)
        return 2
    defect = rec.get("defect")
    out_dir = scratch(sid)
    artifact = out_dir / "result.json"
    if artifact.exists():
        artifact.unlink()

    if defect == "actually_good":
        write_good(artifact, sid)
        print(f"GOOD {sid} wrote {artifact}")
        return 0

    if defect == "green_not_live":
        print(f"ok {sid}")
        return 0

    if defect == "malformed_json":
        artifact.write_text("{not json\n", encoding="utf-8")
        print(f"wrote malformed {artifact}")
        return 0

    if defect == "wall_clock":
        payload = {"ok": True, "id": sid, "t": time.time()}
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        print(f"wrote wall-clock {payload['t']}")
        return 0

    if defect == "unseeded_random":
        payload = {"ok": True, "id": sid, "r": random.random()}
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        print(f"wrote unseeded {payload['r']}")
        return 0

    if defect == "job_receipt":
        print("job-id: bg-9f3a started in background")
        return 0

    if defect == "no_agent_timeout":
        print("barrier waiting for hung agent; no per-agent timeout")
        return 124

    if defect == "fanin_accepts_invalid":
        payload = {
            "ok": True,
            "id": sid,
            "fan_in": [{"ok": True}, {"totally": "unrelated", "passing_tests": 999999}],
        }
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        print("fan-in accepted schema-invalid sibling")
        return 0

    if defect == "digest_missing_file":
        missing = str(out_dir / "never-written.json")
        payload = {
            "ok": True,
            "id": sid,
            "digest": {
                "path": missing,
                "sha256": hashlib.sha256(b"phantom").hexdigest(),
                "exists": True,
            },
        }
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        print(f"claimed digest for missing {missing}")
        return 0

    if defect == "shared_index":
        lock = HERE / "scratch" / "_shared-index.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(f"{sid}\n", encoding="utf-8")
        payload = {"ok": True, "id": sid, "index": str(lock)}
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        print(f"shared index {lock}")
        return 0

    if defect == "string_interp":
        # Deliberately interpolate an id with a space into a shell-like argv.
        broken_argv = f"tool --id {sid} extra".split()
        payload = {"ok": True, "id": sid, "argv": broken_argv}
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        print(f"interpolated argv={broken_argv}")
        return 0

    if defect == "env_path":
        home = os.environ.get("HOME", "/nonexistent")
        payload = {"ok": True, "id": sid, "path": f"{home}/.wfa0086/{sid}.json"}
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        print(f"env path {payload['path']}")
        return 0

    if defect == "crlf_hash":
        body = '{"ok": true, "id": "%s"}\r\n' % sid
        artifact.write_bytes(body.encode("utf-8"))
        claimed = hashlib.sha256(body.replace("\r\n", "\n").encode("utf-8")).hexdigest()
        print(f"wrote CRLF claimed-LF {claimed}")
        return 0

    if defect == "swallowed_exception":
        try:
            raise RuntimeError(f"subject {sid} exploded")
        except Exception:
            pass
        print("swallowed exception")
        return 0

    if defect == "memory_only_partial":
        _partial = {"ok": True, "id": sid, "partial": True}
        print(f"partial in memory only {_partial}")
        return 0

    if defect == "inline_prompt_overflow":
        huge = "X" * 20000
        print(f"inline prompt bytes={len(huge)} (over platform command-line limit)")
        return 1

    print(f"FAILED:WFA-0086-runner unhandled defect {defect}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
